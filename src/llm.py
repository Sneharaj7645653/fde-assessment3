"""Model-provider boundary.

``LLMProvider.chat`` is the only place a model is called. Providers record every HTTP
attempt on the run's ``RunRecorder``, classify failures into ``LLMError.kind``, and never
log credentials.

Credential policy (Groq): several keys may be configured (GROQ_API_KEY, GROQ_API_KEY_1..N,
or comma-separated GROQ_API_KEYS). Only the *first working* key is used. A later key is
tried only when the active key is rejected as invalid (HTTP 401/403). Keys are never rotated
to get around rate limits: a 429 is waited out on the same key (bounded) and then surfaces as
``rate_limited``, at which point the caller falls back to deterministic policy output.
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import httpx

from src.instrumentation import RunRecorder

DEFAULT_GROQ_MODEL = "qwen/qwen3.8-27b"
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
MAX_RATE_LIMIT_WAIT_S = 65.0
MAX_RATE_LIMIT_RETRIES = 4


class LLMError(Exception):
    """kind: missing_credentials | auth | rate_limited | timeout | network | server | model_error | bad_request | malformed_output | schema_validation"""

    def __init__(self, kind: str, message: str, retry_after: float | None = None):
        super().__init__(f"{kind}: {message}")
        self.kind = kind
        self.message = message
        self.retry_after = retry_after


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str


@dataclass
class ChatResult:
    content: str | None
    tool_calls: list[ToolCall]
    raw_message: dict[str, Any]
    model: str
    finish_reason: str | None = None


class LLMProvider:
    name = "base"
    mode = "live"  # "live" | "mock"
    model = ""

    def chat(self, messages: list[dict], *, recorder: RunRecorder, agent: str, tools: list[dict] | None = None,
             json_mode: bool = False, max_tokens: int = 900, is_retry: bool = False) -> ChatResult:
        raise NotImplementedError


class NullProvider(LLMProvider):
    """No credentials configured: every call fails with ``missing_credentials`` (and is not counted as a call)."""

    name, mode, model = "none", "live", ""

    def __init__(self, reason: str = "no model credentials configured"):
        self.reason = reason

    def chat(self, messages, **kwargs):
        raise LLMError("missing_credentials", self.reason)


def groq_keys_from_env(env: dict[str, str] | None = None) -> list[str]:
    env = os.environ if env is None else env
    keys: list[str] = []
    keys += [k.strip() for k in env.get("GROQ_API_KEYS", "").split(",") if k.strip()]
    keys += [env[name].strip() for name in sorted(env, key=lambda n: (len(n), n)) if re.fullmatch(r"GROQ_API_KEY(_\d+)?", name) and env[name].strip()]
    return list(dict.fromkeys(keys))


def _parse_duration(value: str | None) -> float | None:
    """'6.5s', '1m3.2s', '250ms' -> seconds."""
    if not value:
        return None
    total, found = 0.0, False
    for number, unit in re.findall(r"(\d+(?:\.\d+)?)(ms|s|m|h)", value):
        found = True
        total += float(number) * {"ms": 0.001, "s": 1, "m": 60, "h": 3600}[unit]
    return total if found else None


class GroqProvider(LLMProvider):
    name = "groq"

    def __init__(self, api_keys: list[str], model: str | None = None, base_url: str | None = None,
                 timeout_s: float = 45.0, client: httpx.Client | None = None, sleep: Callable[[float], None] = time.sleep):
        if not api_keys:
            raise LLMError("missing_credentials", "no Groq API key configured")
        self._keys = list(api_keys)
        self._active = 0
        self._dead: set[int] = set()
        self.model = model or os.getenv("GROQ_MODEL") or DEFAULT_GROQ_MODEL
        self._url = (base_url or os.getenv("GROQ_BASE_URL") or GROQ_BASE_URL).rstrip("/") + "/chat/completions"
        self._client = client or httpx.Client(timeout=timeout_s)
        self._sleep = sleep
        self._remaining_tokens: float | None = None
        self._reset_at = 0.0

    @property
    def key_failovers(self) -> int:
        return len(self._dead)

    def _pace(self, estimate: int, recorder: RunRecorder) -> None:
        """Wait for the token window to refill instead of provoking a 429."""
        if self._remaining_tokens is not None and self._remaining_tokens < estimate:
            wait = min(max(self._reset_at - time.monotonic(), 0.0) + 0.5, MAX_RATE_LIMIT_WAIT_S)
            if wait > 0:
                self._sleep(wait)
                recorder.add_wait(wait * 1000)
            self._remaining_tokens = None

    def _body(self, messages, tools, json_mode, max_tokens) -> dict[str, Any]:
        body: dict[str, Any] = {"model": self.model, "messages": messages, "temperature": 0, "max_tokens": max_tokens}
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto" if not json_mode else "none"
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        if self.model.startswith("openai/gpt-oss"):
            body["reasoning_effort"] = "low"
            body["include_reasoning"] = False
        elif self.model.startswith("qwen/"):
            body["reasoning_effort"] = "none"  # qwen "thinking" tokens otherwise exhaust the output-tokens-per-minute limit
        return body

    def chat(self, messages, *, recorder, agent, tools=None, json_mode=False, max_tokens=900, is_retry=False) -> ChatResult:
        body = self._body(messages, tools, json_mode, max_tokens)
        estimate = int(len(json.dumps(body)) / 3.2) + max_tokens // 2
        rate_retries = transient_retries = 0
        while True:
            self._pace(estimate, recorder)
            while self._active in self._dead and self._active + 1 < len(self._keys):
                self._active += 1
            started = time.perf_counter()
            try:
                result, usage, headers = self._post(body)
            except LLMError as exc:
                elapsed = (time.perf_counter() - started) * 1000
                recorder.record_llm(agent=agent, provider=self.name, model=self.model, ok=False, latency_ms=elapsed, is_retry=is_retry,
                                    timed_out=exc.kind == "timeout", error_kind=exc.kind)
                is_retry = True
                if exc.kind == "auth":
                    self._dead.add(self._active)
                    if len(self._dead) < len(self._keys):
                        self._active = next(i for i in range(len(self._keys)) if i not in self._dead)
                        continue
                    raise LLMError("auth", "all configured API keys were rejected") from exc
                if exc.kind == "rate_limited" and rate_retries < MAX_RATE_LIMIT_RETRIES and (exc.retry_after or 5.0) <= MAX_RATE_LIMIT_WAIT_S:
                    rate_retries += 1
                    wait = (exc.retry_after or 5.0) + 0.5
                    self._sleep(wait)
                    recorder.add_wait(wait * 1000)
                    continue
                if exc.kind in {"timeout", "network", "server", "model_error"} and transient_retries < 1:
                    transient_retries += 1
                    self._sleep(0.5)
                    continue
                raise
            elapsed = (time.perf_counter() - started) * 1000
            recorder.record_llm(agent=agent, provider=self.name, model=self.model, ok=True, latency_ms=elapsed, is_retry=is_retry,
                                prompt_tokens=usage.get("prompt_tokens", 0), completion_tokens=usage.get("completion_tokens", 0))
            remaining = headers.get("x-ratelimit-remaining-tokens")
            if remaining is not None:
                try:
                    self._remaining_tokens = float(remaining)
                    self._reset_at = time.monotonic() + (_parse_duration(headers.get("x-ratelimit-reset-tokens")) or 0.0)
                except ValueError:
                    self._remaining_tokens = None
            return result

    def _post(self, body: dict[str, Any]) -> tuple[ChatResult, dict, httpx.Headers]:
        try:
            response = self._client.post(self._url, json=body, headers={"Authorization": f"Bearer {self._keys[self._active]}"})
        except httpx.TimeoutException as exc:
            raise LLMError("timeout", f"request timed out ({type(exc).__name__})") from exc
        except httpx.HTTPError as exc:
            raise LLMError("network", f"{type(exc).__name__}") from exc
        status = response.status_code
        if status in (401, 403):
            raise LLMError("auth", f"provider rejected the credential (HTTP {status})")
        if status == 429:
            raise LLMError("rate_limited", f"provider rate limit (HTTP 429): {_error_text(response)}", retry_after=_retry_after(response))
        if status >= 500:
            raise LLMError("server", f"provider error (HTTP {status})")
        if status >= 400:
            detail = _error_text(response)
            # Groq returns 400 when the *model* emits an unparseable/forbidden tool call or invalid JSON. That is a
            # generation failure (nondeterministic), not a malformed request from us, so it is retried once.
            if any(marker in detail.lower() for marker in ("failed to parse tool call", "tool call validation failed", "failed to generate json",
                                                         "tool choice is none", "parsing failed")):
                raise LLMError("model_error", f"HTTP {status}: {detail}")
            raise LLMError("bad_request", f"HTTP {status}: {detail}")
        try:
            data = response.json()
            message = data["choices"][0]["message"]
            finish = data["choices"][0].get("finish_reason")
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMError("malformed_output", "provider response had no choices/message") from exc
        calls = [ToolCall(id=c.get("id", ""), name=c.get("function", {}).get("name", ""), arguments=c.get("function", {}).get("arguments", "") or "")
                 for c in (message.get("tool_calls") or [])]
        raw = {"role": "assistant", "content": message.get("content") or ""}
        if message.get("tool_calls"):
            raw["tool_calls"] = message["tool_calls"]
        return ChatResult(message.get("content"), calls, raw, data.get("model", self.model), finish), data.get("usage") or {}, response.headers


def _error_text(response: httpx.Response) -> str:
    try:
        body = response.json()
        message = body.get("error", {}).get("message", "") if isinstance(body, dict) else ""
    except ValueError:
        message = ""
    return " ".join(str(message).split())[:300]


def _retry_after(response: httpx.Response) -> float | None:
    header = response.headers.get("retry-after")
    try:
        return float(header) if header else None
    except ValueError:
        return _parse_duration(header)


@dataclass
class ScriptedProvider(LLMProvider):
    """Deterministic test double. ``script`` is a list of responses or a callable(messages, tools, json_mode) -> response.

    A response is a dict ``{"content": str}`` or ``{"tool_calls": [{"name":..., "arguments": {...}}]}``, or an
    ``LLMError`` instance to raise. Reported as mode='mock' so results can never be mistaken for live Groq output.
    """

    script: Any = field(default_factory=list)
    name: str = "scripted-mock"
    mode: str = "mock"
    model: str = "scripted"
    calls: list[dict] = field(default_factory=list)

    def chat(self, messages, *, recorder, agent, tools=None, json_mode=False, max_tokens=900, is_retry=False) -> ChatResult:
        started = time.perf_counter()
        self.calls.append({"agent": agent, "messages": json.loads(json.dumps(messages)), "tools": bool(tools), "json_mode": json_mode})
        step = self.script(messages, tools, json_mode) if callable(self.script) else self.script.pop(0)
        if isinstance(step, LLMError):
            recorder.record_llm(agent=agent, provider=self.name, model=self.model, ok=False, latency_ms=(time.perf_counter() - started) * 1000,
                                is_retry=is_retry, timed_out=step.kind == "timeout", error_kind=step.kind)
            raise step
        calls = [ToolCall(id=f"call_{i}", name=c["name"], arguments=json.dumps(c.get("arguments", {}))) for i, c in enumerate(step.get("tool_calls", []))]
        raw: dict[str, Any] = {"role": "assistant", "content": step.get("content") or ""}
        if calls:
            raw["tool_calls"] = [{"id": c.id, "type": "function", "function": {"name": c.name, "arguments": c.arguments}} for c in calls]
        recorder.record_llm(agent=agent, provider=self.name, model=self.model, ok=True, latency_ms=(time.perf_counter() - started) * 1000, is_retry=is_retry)
        return ChatResult(step.get("content"), calls, raw, self.model, "stop")


def get_provider() -> LLMProvider:
    """Provider from environment. LLM_PROVIDER=none disables the model entirely (deterministic output only)."""
    choice = os.getenv("LLM_PROVIDER", "groq").strip().casefold()
    if choice in {"none", "off", "disabled"}:
        return NullProvider("LLM_PROVIDER is set to none")
    if choice != "groq":
        return NullProvider(f"unsupported LLM_PROVIDER '{choice}'")
    keys = groq_keys_from_env()
    if not keys:
        return NullProvider("no GROQ_API_KEY configured")
    try:
        timeout = float(os.getenv("LLM_TIMEOUT_SECONDS", "45"))
    except ValueError:
        timeout = 45.0
    return GroqProvider(keys, timeout_s=timeout)
