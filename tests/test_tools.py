from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import requests

from src import tools, vendor_client
from src.data_access import get_request
from src.instrumentation import RunRecorder
from src.vendor_client import VendorRiskResult
from tests.helpers import inprocess_vendor_api


def executor(request_id="REQ-1002"):
    rec = RunRecorder()
    return tools.ToolExecutor(get_request(request_id), rec), rec


class ToolTests(unittest.TestCase):
    def test_requester_budget_lookup(self):
        ex, _ = executor("REQ-1005")
        out = ex.dispatch("lookup_requester_budget", {"request_id": "REQ-1005"}, "agent")
        self.assertEqual(out["employee"]["name"], "Elena Garcia")
        self.assertEqual(out["department_budget"]["available_usd"], 18000)
        self.assertTrue(out["budget_arithmetic_consistent"])
        self.assertIn("data/employees.csv#E003", out["refs"])

    def test_unknown_requester(self):
        ex, _ = executor()
        ex.request = {**ex.request, "requester_id": "E999"}
        ex.gathered.request = ex.request
        out = ex.dispatch("lookup_requester_budget", {}, "agent")
        self.assertIsNone(out["employee"]); self.assertFalse(ex.gathered.requester_found)

    def test_catalog_search_reports_match_basis_without_claiming_capacity(self):
        ex, _ = executor("REQ-1002")
        out = ex.dispatch("search_existing_software", {"request_id": "REQ-1002"}, "agent")
        self.assertEqual({r["software_id"] for r in out["catalog_matches"]}, {"SW001", "SW002"})
        self.assertTrue(all(r["match_basis"] == ["same category"] for r in out["catalog_matches"]))
        self.assertIn("not proof", out["note"])

    def test_vendor_status_ok_not_found_and_outage(self):
        with inprocess_vendor_api():
            for rid, state in (("REQ-1002", "not_completed"), ("REQ-1009", "unavailable")):
                ex, rec = executor(rid)
                out = ex.dispatch("get_vendor_status", {"request_id": rid}, "agent")
                self.assertEqual(out["vendor_risk_api"]["assessment_state"], state)
            self.assertEqual(out["vendor_risk_api"]["http_status"], 503)
            self.assertIn("temporarily unavailable", out["vendor_risk_api"]["error"])
            self.assertEqual(len(rec.tool_calls), 2)  # one retry after the 503
            self.assertTrue(rec.tool_calls[1].is_retry)
            self.assertFalse(rec.tool_calls[1].ok)
            ex, _ = executor("REQ-1002"); ex.request["vendor_name"] = "NoSuchVendor"; ex.gathered.request = ex.request
            out = ex.dispatch("get_vendor_status", {}, "agent")
            self.assertEqual(out["vendor_risk_api"]["status"], "not_found")
            self.assertEqual(out["vendor_risk_api"]["assessment_state"], "missing")

    def test_dispatch_never_raises_and_records_failures(self):
        ex, rec = executor()
        self.assertFalse(ex.dispatch("drop_tables", {}, "agent")["ok"])
        self.assertFalse(ex.dispatch("check_policy", "{not json", "agent")["ok"])
        self.assertFalse(ex.dispatch("check_policy", {"request_id": "REQ-9999"}, "agent")["ok"])
        self.assertEqual(rec.to_telemetry().failed_tool_calls, 3)

    def test_duplicate_tool_calls_are_suppressed(self):
        ex, rec = executor()
        ex.dispatch("search_existing_software", {}, "agent"); ex.dispatch("search_existing_software", {}, "agent")
        self.assertEqual(len(rec.tool_calls), 1); self.assertEqual(ex.duplicate_calls_suppressed, 1)

    def test_check_policy_runs_prerequisites_and_is_deterministic(self):
        with inprocess_vendor_api():
            ex, rec = executor("REQ-1003")
            out = ex.dispatch("check_policy", {}, "agent")
        self.assertEqual(out["required_approvals"], ["Department Head", "Finance", "Procurement", "Security"])
        self.assertEqual({c.name for c in rec.tool_calls}, set(tools.TOOL_NAMES))
        self.assertIn("deterministic", out["authority"])

    def test_ensure_all_backfills_only_missing_tools(self):
        with inprocess_vendor_api():
            ex, rec = executor()
            ex.dispatch("lookup_requester_budget", {}, "agent")
            self.assertEqual(ex.ensure_all(), ["search_existing_software", "get_vendor_status"])
        self.assertEqual(rec.to_telemetry().guardrail_tool_backfills, 2)

    def test_model_facing_output_is_bounded_json(self):
        text = tools.tool_output_for_model({"ok": True, "blob": "x" * 9000})
        self.assertLess(len(text), 2700)


class VendorClientTests(unittest.TestCase):
    def _http_error(self, code, detail="boom"):
        return requests.HTTPError(f"HTTP {code}: {detail}", response=type("R", (), {"status_code": code})())

    def test_status_classification(self):
        with patch("src.vendor_client._sleep"):
            with patch("src.vendor_client.get_vendor_risk", side_effect=self._http_error(404, "none")):
                self.assertEqual(vendor_client.fetch_vendor_risk("X").status, "not_found")
            with patch("src.vendor_client.get_vendor_risk", side_effect=self._http_error(503)) as call:
                result = vendor_client.fetch_vendor_risk("X")
                self.assertEqual((result.status, result.http_status, result.attempts), ("unavailable", 503, 2)); self.assertEqual(call.call_count, 2)
            with patch("src.vendor_client.get_vendor_risk", side_effect=self._http_error(400)) as call:
                self.assertEqual(vendor_client.fetch_vendor_risk("X").attempts, 1)  # client errors are not retried
            with patch("src.vendor_client.get_vendor_risk", side_effect=requests.Timeout("slow")):
                result = vendor_client.fetch_vendor_risk("X"); self.assertTrue(result.timed_out); self.assertEqual(result.status, "unavailable")
            with patch("src.vendor_client.get_vendor_risk", side_effect=requests.ConnectionError("refused")):
                self.assertEqual(vendor_client.fetch_vendor_risk("X").status, "unavailable")
            with patch("src.vendor_client.get_vendor_risk", side_effect=ValueError("not json")):
                self.assertIn("valid JSON", vendor_client.fetch_vendor_risk("X").error)

    def test_malformed_records_are_unavailable_not_trusted(self):
        with patch("src.vendor_client.get_vendor_risk", return_value={"security_review_status": "approved"}):
            result = vendor_client.fetch_vendor_risk("X")
        self.assertEqual(result.status, "unavailable"); self.assertIn("Malformed", result.error)
        with patch("src.vendor_client.get_vendor_risk", return_value=["x"]):
            self.assertEqual(vendor_client.fetch_vendor_risk("X").status, "unavailable")

    def test_recovers_after_transient_failure(self):
        good = {"risk_level": "low", "security_review_status": "approved", "last_review_date": "2026-06-01",
                "processes_personal_data": False, "stores_data_outside_region": False}
        with patch("src.vendor_client._sleep"), patch("src.vendor_client.get_vendor_risk", side_effect=[self._http_error(503), good]):
            result = vendor_client.fetch_vendor_risk("X")
        self.assertEqual((result.status, result.attempts), ("ok", 2))


if __name__ == "__main__":
    unittest.main()
