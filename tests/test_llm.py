from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import httpx

from src import llm
from src.instrumentation import RunRecorder


def ok_body(content="{}", tool_calls=None):
    message = {"role": "assistant", "content": content}
    if tool_calls:
        message["tool_calls"] = tool_calls
    return {"model": "m", "choices": [{"message": message, "finish_reason": "stop"}], "usage": {"prompt_tokens": 10, "completion_tokens": 3}}


def provider(handler, keys=("k1",), sleeps=None):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    sleeps = [] if sleeps is None else sleeps
    return llm.GroqProvider(list(keys), model="test-model", client=client, sleep=sleeps.append), sleeps


MSG = [{"role": "user", "content": "hi"}]


class GroqProviderTests(unittest.TestCase):
    def test_success_records_real_attempt_and_tokens(self):
        seen = {}
        def handler(request):
            seen["auth"] = request.headers["authorization"]; seen["body"] = json.loads(request.content)
            return httpx.Response(200, json=ok_body("hello"))
        p, _ = provider(handler); rec = RunRecorder()
        result = p.chat(MSG, recorder=rec, agent="a")
        self.assertEqual(result.content, "hello")
        t = rec.to_telemetry()
        self.assertEqual((t.llm_calls, t.failed_llm_calls, t.prompt_tokens, t.completion_tokens), (1, 0, 10, 3))
        self.assertEqual(seen["body"]["temperature"], 0)

    def test_json_mode_and_tools_payload(self):
        bodies = []
        def handler(request):
            bodies.append(json.loads(request.content)); return httpx.Response(200, json=ok_body())
        p, _ = provider(handler); rec = RunRecorder()
        p.chat(MSG, recorder=rec, agent="a", json_mode=True)
        p.chat(MSG, recorder=rec, agent="a", tools=[{"type": "function", "function": {"name": "t"}}])
        self.assertEqual(bodies[0]["response_format"], {"type": "json_object"}); self.assertNotIn("tools", bodies[0])
        self.assertEqual(bodies[1]["tool_choice"], "auto")

    def test_tool_calls_are_parsed(self):
        calls = [{"id": "c1", "type": "function", "function": {"name": "check_policy", "arguments": "{\"request_id\":\"R\"}"}}]
        p, _ = provider(lambda r: httpx.Response(200, json=ok_body("", calls)))
        result = p.chat(MSG, recorder=RunRecorder(), agent="a")
        self.assertEqual([(c.name, c.arguments) for c in result.tool_calls], [("check_policy", "{\"request_id\":\"R\"}")])
        self.assertEqual(result.raw_message["tool_calls"], calls)

    def test_invalid_key_falls_over_to_next_key_only_on_auth_failure(self):
        keys_seen = []
        def handler(request):
            keys_seen.append(request.headers["authorization"])
            return httpx.Response(401, json={}) if request.headers["authorization"].endswith("bad") else httpx.Response(200, json=ok_body())
        p, _ = provider(handler, keys=("bad", "good")); rec = RunRecorder()
        p.chat(MSG, recorder=rec, agent="a")
        self.assertEqual(keys_seen, ["Bearer bad", "Bearer good"])
        t = rec.to_telemetry(); self.assertEqual((t.llm_calls, t.failed_llm_calls, t.llm_retries), (2, 1, 1))
        p.chat(MSG, recorder=rec, agent="a")
        self.assertEqual(keys_seen[2:], ["Bearer good"])  # dead key is not retried

    def test_all_keys_rejected_is_auth_error(self):
        p, _ = provider(lambda r: httpx.Response(403, json={}), keys=("a", "b"))
        with self.assertRaises(llm.LLMError) as ctx:
            p.chat(MSG, recorder=RunRecorder(), agent="a")
        self.assertEqual(ctx.exception.kind, "auth")

    def test_rate_limit_waits_on_same_key_then_succeeds(self):
        keys_seen = []
        responses = iter([httpx.Response(429, headers={"retry-after": "2"}, json={}), httpx.Response(200, json=ok_body())])
        def handler(request):
            keys_seen.append(request.headers["authorization"]); return next(responses)
        p, sleeps = provider(handler, keys=("k1", "k2")); rec = RunRecorder()
        p.chat(MSG, recorder=rec, agent="a")
        self.assertEqual(keys_seen, ["Bearer k1", "Bearer k1"])  # never rotates to dodge a rate limit
        self.assertEqual(sleeps, [2.5]); self.assertEqual(rec.to_telemetry().rate_limit_wait_ms, 2500.0)

    def test_rate_limit_beyond_cap_surfaces_as_error(self):
        p, sleeps = provider(lambda r: httpx.Response(429, headers={"retry-after": "3600"}, json={}), keys=("k1", "k2"))
        with self.assertRaises(llm.LLMError) as ctx:
            p.chat(MSG, recorder=RunRecorder(), agent="a")
        self.assertEqual((ctx.exception.kind, sleeps), ("rate_limited", []))

    def test_rate_limit_retries_are_bounded(self):
        p, sleeps = provider(lambda r: httpx.Response(429, headers={"retry-after": "1"}, json={}))
        with self.assertRaises(llm.LLMError):
            p.chat(MSG, recorder=RunRecorder(), agent="a")
        self.assertEqual(len(sleeps), llm.MAX_RATE_LIMIT_RETRIES)

    def test_timeout_and_server_errors_retry_once_then_classify(self):
        def timeout(request): raise httpx.ReadTimeout("slow")
        p, _ = provider(timeout); rec = RunRecorder()
        with self.assertRaises(llm.LLMError) as ctx:
            p.chat(MSG, recorder=rec, agent="a")
        t = rec.to_telemetry()
        self.assertEqual((ctx.exception.kind, t.llm_calls, t.timeouts, t.llm_retries), ("timeout", 2, 2, 1))
        p, _ = provider(lambda r: httpx.Response(503, json={}))
        with self.assertRaises(llm.LLMError) as ctx:
            p.chat(MSG, recorder=RunRecorder(), agent="a")
        self.assertEqual(ctx.exception.kind, "server")

    def test_bad_request_and_malformed_body(self):
        p, _ = provider(lambda r: httpx.Response(400, json={"error": {"message": "nope"}}))
        with self.assertRaises(llm.LLMError) as ctx: p.chat(MSG, recorder=RunRecorder(), agent="a")
        self.assertEqual(ctx.exception.kind, "bad_request")
        p, _ = provider(lambda r: httpx.Response(200, json={"unexpected": 1}))
        with self.assertRaises(llm.LLMError) as ctx: p.chat(MSG, recorder=RunRecorder(), agent="a")
        self.assertEqual(ctx.exception.kind, "malformed_output")

    def test_error_text_never_contains_the_key(self):
        secret = "gsk_SECRETVALUE123"
        p, _ = provider(lambda r: httpx.Response(401, json={"error": secret}), keys=(secret,))
        with self.assertRaises(llm.LLMError) as ctx: p.chat(MSG, recorder=RunRecorder(), agent="a")
        self.assertNotIn(secret, str(ctx.exception))

    def test_proactive_pacing_waits_for_token_window(self):
        responses = iter([httpx.Response(200, json=ok_body(), headers={"x-ratelimit-remaining-tokens": "10", "x-ratelimit-reset-tokens": "7s"}),
                          httpx.Response(200, json=ok_body())])
        p, sleeps = provider(lambda r: next(responses)); rec = RunRecorder()
        p.chat(MSG, recorder=rec, agent="a"); p.chat(MSG, recorder=rec, agent="a")
        self.assertEqual(len(sleeps), 1); self.assertGreater(sleeps[0], 5)
        self.assertGreater(rec.to_telemetry().rate_limit_wait_ms, 5000)


class ConfigTests(unittest.TestCase):
    def test_key_discovery_forms(self):
        env = {"GROQ_API_KEY": "a", "GROQ_API_KEY_2": "b", "GROQ_API_KEY_1": "c", "GROQ_API_KEYS": "d, e,a", "OTHER": "z", "GROQ_API_KEY_3": " "}
        self.assertEqual(llm.groq_keys_from_env(env), ["d", "e", "a", "c", "b"])

    def test_provider_selection(self):
        with patch.dict("os.environ", {"LLM_PROVIDER": "none"}, clear=True):
            self.assertIsInstance(llm.get_provider(), llm.NullProvider)
        with patch.dict("os.environ", {"LLM_PROVIDER": "groq"}, clear=True):
            self.assertIsInstance(llm.get_provider(), llm.NullProvider)
        with patch.dict("os.environ", {"LLM_PROVIDER": "groq", "GROQ_API_KEY_1": "k"}, clear=True):
            self.assertIsInstance(llm.get_provider(), llm.GroqProvider)
        with patch.dict("os.environ", {"LLM_PROVIDER": "bogus", "GROQ_API_KEY_1": "k"}, clear=True):
            self.assertIsInstance(llm.get_provider(), llm.NullProvider)

    def test_null_provider_reports_missing_credentials_without_counting_a_call(self):
        rec = RunRecorder()
        with self.assertRaises(llm.LLMError) as ctx:
            llm.NullProvider().chat(MSG, recorder=rec, agent="a")
        self.assertEqual((ctx.exception.kind, rec.to_telemetry().llm_calls), ("missing_credentials", 0))

    def test_duration_parser(self):
        self.assertEqual(llm._parse_duration("1m3.5s"), 63.5); self.assertEqual(llm._parse_duration("250ms"), 0.25); self.assertIsNone(llm._parse_duration("x"))


if __name__ == "__main__":
    unittest.main()
