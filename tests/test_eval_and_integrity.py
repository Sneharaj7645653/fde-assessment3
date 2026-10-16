from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evals"))

import compare_architectures as harness  # noqa: E402
from src.llm import NullProvider  # noqa: E402
from tests.helpers import inprocess_get_vendor_risk, inprocess_vendor_api, single_provider, staged_provider  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


class _Resp:
    def __init__(self, status, body=None):
        self.status_code, self._body = status, body

    def json(self):
        return self._body


def served_get(url, timeout=3):
    vendor = url.rsplit("/", 1)[-1].replace("%20", " ")
    try:
        return _Resp(200, inprocess_get_vendor_risk(vendor))
    except Exception as exc:  # noqa: BLE001
        return _Resp(exc.response.status_code)


class HarnessTests(unittest.TestCase):
    def setUp(self):
        self.stack = [inprocess_vendor_api(), patch.object(harness, "http_get", served_get)]
        for p in self.stack:
            p.__enter__()
        self.addCleanup(lambda: [p.__exit__(None, None, None) for p in reversed(self.stack)])

    def test_both_architectures_see_identical_case_sets(self):
        cases = harness.load_cases(["public", "extended"])
        self.assertEqual(len(cases), 15)
        self.assertEqual([c["case_id"] for c in cases[:6]], [f"PUB-0{i}" for i in range(1, 7)])
        rows = [harness.run_one(c, a, NullProvider(), 1) for c in cases for a in ("single", "staged")]
        by_arch = {a: [r["case_id"] for r in rows if r["architecture"] == a] for a in ("single", "staged")}
        self.assertEqual(by_arch["single"], by_arch["staged"])

    def test_deterministic_floor_fails_only_the_ai_dependent_case(self):
        rows = [harness.run_one(c, "single", NullProvider(), 1) for c in harness.load_cases(["public", "extended"])]
        self.assertEqual([r["case_id"] for r in rows if not r["automated_pass"]], ["SYN-03"])

    def test_metrics_are_measured_and_cross_checked(self):
        case = next(c for c in harness.load_cases(["public"]) if c["case_id"] == "PUB-06")
        provider = single_provider()
        row = harness.run_one(case, "single", provider, 1)
        self.assertEqual(row["llm_calls"], len(provider.calls))
        self.assertEqual(row["independent_vendor_attempts"], 2)  # 503 + one retry, counted independently of telemetry
        self.assertTrue(row["telemetry_consistent"])
        self.assertTrue(row["automated_pass"], row["failures"])
        self.assertGreater(row["latency_ms"], 0)

    def test_summary_and_outputs(self):
        cases = [c for c in harness.load_cases(["public"]) if c["case_id"] in {"PUB-01", "PUB-05"}]
        rows = [harness.run_one(c, a, provider, run) for run in (1, 2) for c in cases for a, provider in (("single", single_provider()), ("staged", staged_provider()))]
        summary = harness.summarize(rows)
        self.assertGreater(summary["staged"]["mean_llm_calls"], summary["single"]["mean_llm_calls"])
        self.assertEqual(summary["single"]["runs"], 4); self.assertEqual(summary["single"]["unstable_cases"], [])
        with tempfile.TemporaryDirectory() as tmp, patch.object(harness, "RESULTS_DIR", Path(tmp)):
            paths = harness.write_outputs("t", rows, summary, {"provider_mode": "mock", "model": "scripted", "sets": ["public"], "cases": 2, "runs": 2, "generated": "now"})
            self.assertEqual(len(list(csv.DictReader(paths[0].open()))), 8)
            self.assertIn("A - single agent", paths[2].read_text())

    def test_audit_catches_fabricated_evidence(self):
        case = next(c for c in harness.load_cases(["public"]) if c["case_id"] == "PUB-01")
        from src.solution import handle_request
        decision = handle_request("REQ-1001", provider=NullProvider())
        request = harness.case_request(case)
        self.assertEqual(harness.audit_evidence(decision, request, None), [])
        decision.evidence[3].finding = "Finance has $99,999 available budget."
        self.assertTrue(harness.audit_evidence(decision, request, None))

    def test_classification_maps_failures_to_dimensions(self):
        ok = harness.classify(["required approval missing: security", "recommendation expected x", "required risk flag missing: y"])
        self.assertFalse(ok["approvals"]); self.assertFalse(ok["recommendation"]); self.assertFalse(ok["risk_flags"]); self.assertTrue(ok["missing_information"])

    def test_public_cases_are_unchanged_and_extended_cases_are_valid(self):
        harness.load_cases(["public", "extended"])  # raises if the instructor schema or request references break
        for case in json.loads((ROOT / "evals" / "extended_cases.json").read_text()):
            self.assertEqual(set(case["expectations"]), harness.instructor.EXPECTATION_FIELDS)


class StarterIntegrityTests(unittest.TestCase):
    def test_protected_starter_evidence_is_byte_identical_to_baseline(self):
        result = subprocess.run([sys.executable, str(ROOT / "scripts" / "check_starter_integrity.py")], capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("violations: 0", result.stdout)


if __name__ == "__main__":
    unittest.main()


class DeliverableTests(unittest.TestCase):
    def test_decision_memo_is_at_most_500_words(self):
        words = (ROOT / "docs" / "architecture_decision_memo.md").read_text().split()
        self.assertLessEqual(len(words), 500)

    def test_no_secrets_in_tracked_candidates(self):
        import re
        pattern = re.compile(r"gsk_[A-Za-z0-9]{20,}")
        skip = {".venv", ".git", "__pycache__", ".pytest_cache"}
        for path in ROOT.rglob("*"):
            if path.is_file() and not (set(path.parts) & skip) and path.name != ".env" and path.suffix in {".py", ".md", ".json", ".csv", ".txt", ".example", ".sh", ".toml", ""}:
                self.assertIsNone(pattern.search(path.read_text(errors="ignore")), f"possible API key in {path}")
        self.assertIn(".env", (ROOT / ".gitignore").read_text().split())
        self.assertNotIn("gsk_", (ROOT / ".env.example").read_text())
