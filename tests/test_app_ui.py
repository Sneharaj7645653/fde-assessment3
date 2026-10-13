from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from src.llm import LLMError, NullProvider, ScriptedProvider
from tests.helpers import agent_script, inprocess_vendor_api, single_provider, staged_provider

ROOT = Path(__file__).resolve().parents[1]


def visible_text(app_test: AppTest) -> str:
    elements = [*app_test.title, *app_test.caption, *app_test.subheader, *app_test.markdown, *app_test.info, *app_test.warning, *app_test.table]
    return "\n".join(str(getattr(element, "value", element)) for element in elements)


def widget(app_test: AppTest, kind: str, label_part: str):
    return next(w for w in getattr(app_test, kind) if label_part in (w.label or ""))


class ProcurementUiTests(unittest.TestCase):
    def _open(self, provider=None) -> AppTest:
        self._patches = [inprocess_vendor_api(), patch("src.solution.default_provider", return_value=provider or single_provider())]
        for p in self._patches:
            p.__enter__()
        self.addCleanup(lambda: [p.__exit__(None, None, None) for p in reversed(self._patches)])
        return AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()

    def test_selected_request_runs_real_pipeline_and_renders_decision(self):
        app = self._open()
        self.assertEqual(app.selectbox[0].value, "REQ-1001")
        app.button[0].click().run()
        self.assertEqual(len(app.exception), 0)
        text = visible_text(app)
        for needle in ("Request details", "Recommendation", "Required approvals", "Risk flags", "Missing information", "Next step", "Supporting evidence",
                       "proceed_to_required_approvals", "Manager", "existing_tool_overlap", "data/requests.json#REQ-1001", "data/software_catalog.csv#SW010",
                       ":green-badge[Verified]", "scripted test provider"):
            self.assertIn(needle, text)
        self.assertTrue(any("Human review is required" in w.value for w in app.warning))
        self.assertEqual(len(app.error), 0)

    def test_vendor_api_503_renders_unavailable_evidence_and_manual_review(self):
        app = self._open()
        app.selectbox[0].select("REQ-1009").run()
        app.button[0].click().run()
        text = visible_text(app)
        self.assertEqual(len(app.exception), 0)
        for needle in ("route_for_manual_review", ":red-badge[Unavailable]", "HTTP 503", "Upstream vendor assessment provider is temporarily unavailable", "Security", "Legal"):
            self.assertIn(needle, text)
        self.assertNotIn(":yellow-badge[Expired]", text)

    def test_incomplete_vendor_assessment_is_badged_missing_not_expired(self):
        app = self._open()
        app.selectbox[0].select("REQ-1002").run()
        app.button[0].click().run()
        text = visible_text(app)
        self.assertIn("not_completed", text); self.assertIn(":orange-badge[Missing]", text); self.assertNotIn(":yellow-badge[Expired]", text)

    def test_incomplete_request_with_injection_asks_for_clarification(self):
        app = self._open()
        app.selectbox[0].select("REQ-1006").run()
        app.button[0].click().run()
        text = visible_text(app)
        self.assertIn("request_clarification", text)
        self.assertIn("No approval tier assigned while required information is missing.", text)
        for field in ("annual_cost_usd", "user_count", "data_access_level", "business_justification"):
            self.assertIn(field, text)
        self.assertIn("prompt_injection_detected", text)
        self.assertEqual(len(app.error), 0)

    def test_expired_conflicting_vendor_shows_conflict_badge(self):
        app = self._open()
        app.selectbox[0].select("REQ-1007").run()
        app.button[0].click().run()
        text = visible_text(app)
        self.assertIn(":red-badge[Conflicting]", text); self.assertIn("vendor_review_expired", text); self.assertIn("conflicting_vendor_evidence", text)

    def test_architecture_selector_runs_the_staged_pipeline(self):
        app = self._open(staged_provider())
        app.radio[0].set_value("staged").run()
        app.button[0].click().run()
        self.assertEqual(len(app.exception), 0)
        details = app.table[-1].value
        self.assertEqual(details["Agents"][0], "evidence_analyst, independent_reviewer")
        self.assertEqual(details["Model calls"][0], 3)

    def test_no_model_configured_is_stated_not_hidden(self):
        app = self._open(NullProvider("no GROQ_API_KEY configured"))
        app.button[0].click().run()
        self.assertTrue(any("No model is configured" in i.value for i in app.info))
        self.assertIn("proceed_to_required_approvals", visible_text(app))

    def test_model_failure_shows_fallback_warning_with_policy_intact(self):
        app = self._open(ScriptedProvider(script=[LLMError("rate_limited", "429")]))
        app.selectbox[0].select("REQ-1003").run()
        app.button[0].click().run()
        warnings = " ".join(w.value for w in app.warning)
        self.assertIn("model was unavailable", warnings); self.assertIn("rate_limited", warnings)
        self.assertIn("Security", visible_text(app))

    def test_backend_errors_show_no_recommendation(self):
        app = self._open()
        with patch("src.solution.evaluate_request", side_effect=RuntimeError("backend connection failed")):
            app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
            app.button[0].click().run()
        self.assertEqual(len(app.exception), 0); self.assertEqual(len(app.error), 1)
        self.assertIn("No recommendation was generated", app.error[0].value); self.assertIn("backend connection failed", app.error[0].value)
        self.assertNotIn("Recommendation", [s.value for s in app.subheader]); self.assertEqual(len(app.warning), 0)

    def test_custom_request_with_unknown_cost_requests_clarification(self):
        app = self._open()
        app.selectbox[0].select("Custom request").run()
        widget(app, "text_input", "Product name").set_value("Acme Notes")
        widget(app, "text_input", "Vendor name").set_value("Acme")
        widget(app, "text_area", "Business justification").set_value("Engineering wants shared meeting notes for sprint reviews.")
        app.button[0].click().run()
        text = visible_text(app)
        self.assertEqual(len(app.exception), 0)
        self.assertIn("request_clarification", text); self.assertIn("annual_cost_usd", text); self.assertIn("user_count", text)


if __name__ == "__main__":
    unittest.main()
