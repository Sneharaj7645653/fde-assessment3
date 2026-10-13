"""Shared test helpers: in-process vendor-risk API and scripted model providers."""
from __future__ import annotations

import json
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import quote

import requests
from fastapi.testclient import TestClient

from mock_api.app import app as mock_api
from src.llm import ScriptedProvider

_CLIENT = TestClient(mock_api)


def inprocess_get_vendor_risk(vendor_name: str, timeout_seconds: float = 3.0) -> dict:
    """Same contract as src.vendor_client.get_vendor_risk, served by the real mock API app (no network)."""
    response = _CLIENT.get(f"/vendor-risk/{quote(vendor_name, safe='')}")
    if response.status_code >= 400:
        detail = response.json().get("detail", "")
        raise requests.HTTPError(f"HTTP {response.status_code}: {detail}", response=SimpleNamespace(status_code=response.status_code))
    return response.json()


@contextmanager
def inprocess_vendor_api():
    with patch("src.vendor_client.get_vendor_risk", side_effect=inprocess_get_vendor_risk), patch("src.vendor_client._sleep"):
        yield


BENIGN_ANALYSIS = {
    "justification": {"adequate": True, "quote": "", "reason": "concrete"},
    "injection": {"suspected": False, "quote": ""},
    "overlap": {"may_already_satisfy": "unclear", "reason": "unknown", "refs": []},
    "clarifying_questions": [],
    "rationale": "Reviewer should follow the listed approvals.",
}


def agent_script(final: dict | str | None = None, *, tools_first: bool = True):
    """Scripted agent: round 1 calls all four tools, then answers with ``final`` as JSON."""
    answer = final if final is not None else BENIGN_ANALYSIS
    state = {"round": 0}

    def script(messages, tools, json_mode):
        if json_mode:
            return {"content": answer if isinstance(answer, str) else json.dumps(answer)}
        state["round"] += 1
        rid = next((m["content"].split("request_id=")[1].split(")")[0].split(".")[0].strip() for m in messages if "request_id=" in str(m.get("content"))), "")
        if tools_first and state["round"] == 1:
            return {"tool_calls": [{"name": n, "arguments": {"request_id": rid}} for n in
                                   ("lookup_requester_budget", "search_existing_software", "get_vendor_status", "check_policy")]}
        return {"content": "ok"}

    return script


def single_provider(final=None, **kw) -> ScriptedProvider:
    return ScriptedProvider(script=agent_script(final, **kw))


def staged_provider(stage1: dict | None = None, stage2: dict | None = None) -> ScriptedProvider:
    brief = stage1 or {"key_facts": [], "justification": BENIGN_ANALYSIS["justification"], "injection": BENIGN_ANALYSIS["injection"],
                       "overlap": BENIGN_ANALYSIS["overlap"], "open_questions": []}
    verdict = stage2 or {"justification": BENIGN_ANALYSIS["justification"], "injection": BENIGN_ANALYSIS["injection"],
                         "unsupported_fact_indexes": [], "clarifying_questions": [], "rationale": "Reviewer should follow the listed approvals."}
    tool_script = agent_script(brief)

    def script(messages, tools, json_mode):
        if "Stage 2 of 2" in messages[0]["content"]:
            return {"content": json.dumps(verdict)}
        return tool_script(messages, tools, json_mode)

    return ScriptedProvider(script=script)
