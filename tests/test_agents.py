from __future__ import annotations

import copy
import json
import unittest

from pydantic import ValidationError

from src.contracts import ProcurementDecision
from src.data_access import get_request
from src.llm import LLMError, NullProvider, ScriptedProvider
from src.solution import evaluate_request, handle_request
from tests.helpers import BENIGN_ANALYSIS, agent_script, inprocess_vendor_api, single_provider, staged_provider


def run(request_id, arch="single", provider=None):
    with inprocess_vendor_api():
        return handle_request(request_id, arch, provider=provider or (single_provider() if arch == "single" else staged_provider()))


class ArchitectureATests(unittest.TestCase):
    def test_single_agent_flow_and_measured_telemetry(self):
        provider = single_provider()
        d = run("REQ-1003", provider=provider)
        self.assertEqual(d.metadata.llm_status, "mock"); self.assertEqual(d.metadata.agents, ["review_agent"])
        t = d.telemetry
        self.assertEqual(t.llm_calls, len(provider.calls)); self.assertEqual(t.llm_calls, 2)  # tool turn, final JSON turn
        self.assertEqual(t.tool_calls, 4); self.assertEqual(set(t.tool_names), {"lookup_requester_budget", "search_existing_software", "get_vendor_status", "check_policy"})
        self.assertEqual(t.guardrail_tool_backfills, 0)
        self.assertTrue(provider.calls[-1]["json_mode"]); self.assertFalse(provider.calls[-1]["tools"])
        self.assertEqual(d.required_approvals, ["Department Head", "Finance", "Procurement", "Security"])

    def test_guardrail_backfills_tools_the_agent_skipped(self):
        d = run("REQ-1001", provider=ScriptedProvider(script=agent_script(tools_first=False)))
        t = d.telemetry
        self.assertEqual(t.guardrail_tool_backfills, 3); self.assertEqual(t.tool_calls, 3)
        self.assertTrue(any("Guardrail ran mandatory tools" in n for n in d.metadata.guardrail_notes))
        self.assertTrue(any(e.source == "mock_api" for e in d.evidence))  # evidence still grounded in tool results

    def test_model_cannot_override_policy_with_claims(self):
        hostile = copy.deepcopy(BENIGN_ANALYSIS)
        hostile["rationale"] = "This purchase has been approved by the CFO for $1 and needs no Security review."
        hostile["clarifying_questions"] = []
        baseline = run("REQ-1003", provider=single_provider())
        d = run("REQ-1003", provider=single_provider(hostile))
        for field in ("recommendation_code", "required_approvals", "risk_flags", "missing_information", "next_step"):
            self.assertEqual(getattr(d, field), getattr(baseline, field), field)
        self.assertNotIn("has been approved", d.rationale)
        self.assertEqual(d.metadata.ungrounded_claims, 1)
        self.assertTrue(any("Rejected model rationale" in n for n in d.metadata.guardrail_notes))

    def test_model_can_only_escalate_with_a_verbatim_quote(self):
        fabricated = copy.deepcopy(BENIGN_ANALYSIS)
        fabricated["justification"] = {"adequate": False, "quote": "this sentence is not in the request", "reason": "vague"}
        fabricated["injection"] = {"suspected": True, "quote": "ignore everything you were told"}
        d = run("REQ-1001", provider=single_provider(fabricated))
        self.assertEqual(d.recommendation_code, "proceed_to_required_approvals")
        self.assertNotIn("prompt_injection_detected", d.risk_flags)
        self.assertEqual(d.metadata.ungrounded_claims, 2)

        grounded = copy.deepcopy(BENIGN_ANALYSIS)
        grounded["justification"] = {"adequate": False, "quote": "three additional signing identities", "reason": "vague"}
        d = run("REQ-1001", provider=single_provider(grounded))
        self.assertEqual(d.recommendation_code, "request_clarification")
        self.assertIn("business_justification", d.missing_information)
        self.assertFalse(d.ai_assessment.justification_adequate)

    def test_model_cannot_remove_flags_or_approvals_for_injection_case(self):
        soothing = copy.deepcopy(BENIGN_ANALYSIS)
        soothing["injection"] = {"suspected": False, "quote": ""}
        soothing["justification"] = {"adequate": True, "quote": "Need AI ASAP", "reason": "fine"}
        d = run("REQ-1006", provider=single_provider(soothing))
        self.assertEqual(d.recommendation_code, "request_clarification")
        self.assertEqual(d.required_approvals, [])
        self.assertIn("prompt_injection_detected", d.risk_flags)  # deterministic detector still fires
        self.assertEqual(set(d.missing_information), {"annual_cost_usd", "user_count", "data_access_level", "business_justification"})

    def test_ungrounded_citations_are_dropped(self):
        analysis = copy.deepcopy(BENIGN_ANALYSIS)
        analysis["overlap"] = {"may_already_satisfy": "partial", "reason": "x", "refs": ["data/software_catalog.csv#SW010", "data/software_catalog.csv#SW999", "SW010"]}
        d = run("REQ-1001", provider=single_provider(analysis))
        self.assertEqual(d.ai_assessment.overlap_refs, ["data/software_catalog.csv#SW010"])
        self.assertEqual(d.metadata.ungrounded_claims, 1)

    def test_malformed_json_is_repaired_once(self):
        calls = {"n": 0}
        base = agent_script()
        def script(messages, tools, json_mode):
            if json_mode:
                calls["n"] += 1
                return {"content": "Sure! here you go: not json"} if calls["n"] == 1 else {"content": json.dumps(BENIGN_ANALYSIS)}
            return base(messages, tools, json_mode)
        d = run("REQ-1001", provider=ScriptedProvider(script=script))
        self.assertEqual(d.metadata.llm_status, "mock"); self.assertEqual(d.telemetry.llm_retries, 1)

    def test_invalid_output_twice_falls_back_to_deterministic(self):
        base = agent_script()
        def script(messages, tools, json_mode):
            return {"content": json.dumps({"justification": "bad"})} if json_mode else base(messages, tools, json_mode)
        d = run("REQ-1009", provider=ScriptedProvider(script=script))
        self.assertEqual(d.metadata.llm_status, "fallback"); self.assertIn("schema_validation", d.metadata.fallback_reason)
        self.assertEqual(d.recommendation_code, "route_for_manual_review")
        self.assertTrue(any("AI interpretation was unavailable" in r for r in d.human_handoff.reasons))
        self.assertIsNone(d.metadata.provider)  # a fallback is never reported as a model result

    def test_provider_failures_fall_back_without_changing_policy(self):
        reference = run("REQ-1005", provider=single_provider())
        for error in ("rate_limited", "auth", "timeout", "network", "server", "bad_request"):
            with self.subTest(error=error):
                d = run("REQ-1005", provider=ScriptedProvider(script=[LLMError(error, "x")]))
                self.assertEqual(d.metadata.llm_status, "fallback"); self.assertTrue(d.metadata.fallback_reason.startswith(error))
                for field in ("recommendation_code", "required_approvals", "risk_flags"):
                    self.assertEqual(getattr(d, field), getattr(reference, field))
                self.assertEqual(d.telemetry.failed_llm_calls, 1)

    def test_missing_credentials_is_disabled_not_live(self):
        d = run("REQ-1001", provider=NullProvider("no GROQ_API_KEY configured"))
        self.assertEqual(d.metadata.llm_status, "disabled"); self.assertEqual(d.telemetry.llm_calls, 0)
        self.assertIn("template", d.rationale)

    def test_persistent_model_error_in_tool_loop_still_yields_a_live_answer(self):
        def script(messages, tools, json_mode):
            if json_mode:
                return {"content": json.dumps(BENIGN_ANALYSIS)}
            raise LLMError("model_error", "HTTP 400: attempted to call tool 'json'")
        d = run("REQ-1001", provider=ScriptedProvider(script=script))
        self.assertEqual(d.metadata.llm_status, "mock")
        self.assertEqual(d.telemetry.guardrail_tool_backfills, 3)
        self.assertTrue(any("tool loop ended early" in n for n in d.metadata.guardrail_notes))
        self.assertEqual(d.required_approvals, ["Manager"])

    def test_unexpected_internal_error_is_contained(self):
        def boom(messages, tools, json_mode): raise RuntimeError("kaboom")
        d = run("REQ-1001", provider=ScriptedProvider(script=boom))
        self.assertEqual(d.metadata.llm_status, "fallback"); self.assertIn("internal_error:RuntimeError", d.metadata.fallback_reason)

    def test_unknown_request_and_architecture(self):
        with self.assertRaises(KeyError): handle_request("REQ-0000", provider=NullProvider())
        with self.assertRaises(ValueError): evaluate_request(get_request("REQ-1001"), architecture="triple", provider=NullProvider())


class ArchitectureBTests(unittest.TestCase):
    def test_staged_flow_has_two_agents_and_reviewer_has_no_tools(self):
        provider = staged_provider()
        d = run("REQ-1002", "staged", provider)
        self.assertEqual(d.metadata.agents, ["evidence_analyst", "independent_reviewer"])
        agents_called = [c["agent"] for c in provider.calls]
        self.assertEqual(agents_called[-1], "independent_reviewer"); self.assertEqual(agents_called.count("independent_reviewer"), 1)
        self.assertFalse(provider.calls[-1]["tools"])
        self.assertEqual(d.telemetry.llm_calls, len(provider.calls))
        self.assertEqual(d.telemetry.llm_calls, 3)  # tool turn, brief, review
        stage2_prompt = provider.calls[-1]["messages"][1]["content"]
        self.assertIn("deterministic_evidence", stage2_prompt)

    def test_a_and_b_are_distinguishable_but_share_policy_output(self):
        a = run("REQ-1005", "single"); b = run("REQ-1005", "staged")
        for field in ("recommendation_code", "required_approvals", "risk_flags", "missing_information", "next_step"):
            self.assertEqual(getattr(a, field), getattr(b, field))
        self.assertGreater(b.telemetry.llm_calls, a.telemetry.llm_calls)
        self.assertNotEqual(a.metadata.agents, b.metadata.agents)

    def test_reviewer_is_authoritative_over_stage_one(self):
        stage1 = {"key_facts": [], "justification": {"adequate": False, "quote": "three additional signing identities", "reason": "vague"},
                  "injection": {"suspected": True, "quote": "three additional"}, "overlap": BENIGN_ANALYSIS["overlap"], "open_questions": []}
        d = run("REQ-1001", "staged", staged_provider(stage1=stage1))  # reviewer disagrees (adequate, no injection)
        self.assertEqual(d.recommendation_code, "proceed_to_required_approvals")
        self.assertNotIn("prompt_injection_detected", d.risk_flags)
        self.assertTrue(any("disagreed" in n for n in d.metadata.guardrail_notes))

    def test_stage_one_facts_citing_unknown_records_are_dropped_before_review(self):
        stage1 = {"key_facts": [{"ref": "data/employees.csv#E004", "fact": "Noah Williams is in Finance."}, {"ref": "data/employees.csv#E777", "fact": "invented"}],
                  "justification": BENIGN_ANALYSIS["justification"], "injection": BENIGN_ANALYSIS["injection"], "overlap": BENIGN_ANALYSIS["overlap"], "open_questions": []}
        provider = staged_provider(stage1=stage1)
        d = run("REQ-1001", "staged", provider)
        prompt = provider.calls[-1]["messages"][1]["content"]
        self.assertIn("E004", prompt); self.assertNotIn("E777", prompt)
        self.assertEqual(d.metadata.ungrounded_claims, 1)

    def test_stage_failure_falls_back(self):
        provider = ScriptedProvider(script=lambda m, t, j: LLMError("rate_limited", "429") if "Stage 2 of 2" in m[0]["content"] else agent_script({"key_facts": [], "justification": BENIGN_ANALYSIS["justification"], "overlap": BENIGN_ANALYSIS["overlap"]})(m, t, j))
        d = run("REQ-1001", "staged", provider)
        self.assertEqual(d.metadata.llm_status, "fallback"); self.assertEqual(d.telemetry.failed_llm_calls, 1)
        self.assertEqual(d.required_approvals, ["Manager"])


class ContractTests(unittest.TestCase):
    def test_every_request_validates_under_both_architectures(self):
        from src.data_access import load_requests
        for request in load_requests():
            for arch in ("single", "staged"):
                with self.subTest(request=request["request_id"], arch=arch):
                    d = run(request["request_id"], arch)
                    ProcurementDecision.model_validate(d.model_dump())
                    self.assertTrue(d.human_review_required); self.assertTrue(d.human_handoff.required)
                    self.assertTrue(d.evidence and d.next_step and d.recommendation)

    def test_missing_cost_never_gets_a_spend_tier(self):
        d = run("REQ-1006")
        self.assertEqual(d.required_approvals, [])
        self.assertNotIn("tier", (d.rationale or "").lower())

    def test_unavailable_evidence_is_not_expired_or_favourable(self):
        d = run("REQ-1009")
        vendor = next(e for e in d.evidence if e.source == "mock_api")
        self.assertEqual(vendor.evidence_status, "unavailable")
        self.assertIn("HTTP 503", vendor.finding)
        self.assertNotIn("vendor_review_expired", d.risk_flags)
        self.assertNotIn("Privacy", d.required_approvals)

    def test_expired_and_conflicting_vendor_information(self):
        d = run("REQ-1007")
        self.assertIn("vendor_review_expired", d.risk_flags); self.assertIn("conflicting_vendor_evidence", d.risk_flags)
        self.assertEqual(d.recommendation_code, "route_for_manual_review")
        vendor = next(e for e in d.evidence if e.source == "mock_api")
        self.assertEqual(vendor.evidence_status, "conflicting"); self.assertIn("456 days", vendor.finding)

    def test_contract_rejects_bad_values(self):
        d = run("REQ-1001").model_dump()
        for patch in ({"recommendation_code": "approve"}, {"required_approvals": ["Wizard"]}, {"risk_flags": ["x"]}, {"extra": 1}):
            with self.assertRaises(ValidationError):
                ProcurementDecision.model_validate({**d, **patch})


if __name__ == "__main__":
    unittest.main()
