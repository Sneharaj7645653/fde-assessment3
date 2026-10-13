"""The four agent tools. Each does real work and returns structured, source-referenced data.

  lookup_requester_budget   deterministic data lookup  (employees.csv, department_budgets.csv)
  search_existing_software  deterministic search       (software_catalog.csv, purchase_history.csv)
  get_vendor_status         external call + lookup     (vendors.csv + mock vendor-risk API over HTTP)
  check_policy              deterministic policy engine (thresholds, triggers, approvals)

Tools take only ``request_id``; they read the request from the run context, so the
model cannot alter amounts or facts by rewriting arguments.
"""
from __future__ import annotations

import json
import math
import time
from typing import Any, Callable

import pandas as pd

from src import policy
from src.data_access import (
    load_budgets, load_employees, load_purchase_history, load_software_catalog, load_vendors,
)
from src.instrumentation import RunRecorder
from src.vendor_client import VendorRiskResult, fetch_vendor_risk

TOOL_NAMES = ("lookup_requester_budget", "search_existing_software", "get_vendor_status", "check_policy")
DATA_TOOLS = ("lookup_requester_budget", "search_existing_software", "get_vendor_status")

# Overridable for tests / synthetic evaluation cases (e.g. to simulate outages or poisoned vendor text).
VendorFetcher = Callable[[str], VendorRiskResult]
vendor_fetcher: VendorFetcher = fetch_vendor_risk

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {"type": "function", "function": {
        "name": "lookup_requester_budget",
        "description": "Look up the requester (employees.csv) and their department's software budget (department_budgets.csv). Deterministic.",
        "parameters": {"type": "object", "properties": {"request_id": {"type": "string"}}, "required": ["request_id"], "additionalProperties": False}}},
    {"type": "function", "function": {
        "name": "search_existing_software",
        "description": "Search the approved software catalog and purchase history for the same vendor, product or category as the request. Deterministic.",
        "parameters": {"type": "object", "properties": {"request_id": {"type": "string"}}, "required": ["request_id"], "additionalProperties": False}}},
    {"type": "function", "function": {
        "name": "get_vendor_status",
        "description": "Fetch the vendor registry row and call the vendor-risk API for the requested vendor. Reports outages as unavailable, never as safe.",
        "parameters": {"type": "object", "properties": {"request_id": {"type": "string"}}, "required": ["request_id"], "additionalProperties": False}}},
    {"type": "function", "function": {
        "name": "check_policy",
        "description": "Run the deterministic procurement policy engine (spend tier, budget, security/privacy/legal triggers, approvals). Authoritative; cannot be overridden.",
        "parameters": {"type": "object", "properties": {"request_id": {"type": "string"}}, "required": ["request_id"], "additionalProperties": False}}},
]


def records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """DataFrame rows as dicts with NaN normalised to None (empty CSV cells are *absent*, not the text 'nan')."""
    cleaned = frame.astype(object).where(pd.notna(frame), None)
    return cleaned.to_dict(orient="records")


def _jsonable(value: Any) -> Any:
    if isinstance(value, float) and math.isnan(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


class ToolExecutor:
    """Runs tools against one request, filling ``Gathered`` and recording every dispatch."""

    def __init__(self, request: dict[str, Any], recorder: RunRecorder):
        self.request = request
        self.recorder = recorder
        self.gathered = policy.Gathered(request=request)
        self._cache: dict[str, dict[str, Any]] = {}
        self.duplicate_calls_suppressed = 0

    # ---- dispatch -------------------------------------------------------
    def dispatch(self, name: str, arguments: str | dict | None, caller: str) -> dict[str, Any]:
        """Execute a tool by name. Never raises: failures come back as ``{"ok": False, ...}``."""
        started = time.perf_counter()
        try:
            args = json.loads(arguments) if isinstance(arguments, str) and arguments.strip() else (arguments or {})
            if not isinstance(args, dict):
                raise ValueError("tool arguments must be a JSON object")
        except ValueError as exc:
            return self._failed(name, caller, started, f"invalid arguments: {exc}", status="rejected")
        if name not in TOOL_NAMES:
            return self._failed(name, caller, started, f"unknown tool '{name}'", status="rejected")
        requested = args.get("request_id")
        if requested not in (None, self.request.get("request_id")):
            return self._failed(name, caller, started, f"request_id '{requested}' does not match the request under review; use request_id '{self.request.get('request_id')}'", status="rejected")
        if name in self._cache:  # the same tool is never executed twice for one request
            self.duplicate_calls_suppressed += 1
            return {**self._cache[name], "cached": True}
        try:
            result = getattr(self, f"_{name}")(caller)
        except Exception as exc:  # defensive: a tool bug must not crash the run
            return self._failed(name, caller, started, f"{type(exc).__name__}: {exc}")
        self._cache[name] = result
        if name != "get_vendor_status":  # vendor tool records its own (possibly retried) attempts
            self.recorder.record_tool(name=name, caller=caller, ok=True, status="ok", latency_ms=(time.perf_counter() - started) * 1000)
        self.gathered.tools_done.add(name)
        return result

    def _failed(self, name: str, caller: str, started: float, error: str, status: str = "error") -> dict[str, Any]:
        self.recorder.record_tool(name=name, caller=caller, ok=False, status=status, latency_ms=(time.perf_counter() - started) * 1000, error=error)
        return {"ok": False, "error": error}

    def ensure_all(self, caller: str = "guardrail") -> list[str]:
        """Run any data tool the agent skipped; returns the names it had to backfill."""
        backfilled = []
        for name in DATA_TOOLS:
            if name not in self.gathered.tools_done:
                self.dispatch(name, {"request_id": self.request.get("request_id")}, caller=caller)
                backfilled.append(name)
        return backfilled

    # ---- tools ----------------------------------------------------------
    def _lookup_requester_budget(self, caller: str) -> dict[str, Any]:
        g = self.gathered
        requester_id = self.request.get("requester_id")
        employee = next((r for r in records(load_employees()) if r.get("employee_id") == requester_id), None) if requester_id else None
        g.employee, g.requester_found = employee, employee is not None
        department = employee.get("department") if employee else None
        g.budget = next((r for r in records(load_budgets()) if policy.lower(r.get("department")) == policy.lower(department)), None) if department else None
        refs = ([f"data/employees.csv#{employee['employee_id']}"] if employee else []) + (
            [f"data/department_budgets.csv#{g.budget['department']}"] if g.budget else [])
        return {
            "ok": True,
            "refs": refs,
            "employee": employee,
            "department_budget": g.budget,
            "budget_arithmetic_consistent": g.budget is not None and policy._budget_available(g.budget) is not None,
        }

    def _search_existing_software(self, caller: str) -> dict[str, Any]:
        g, request = self.gathered, self.request
        vendor, product, category = (policy.lower(request.get(k)) for k in ("vendor_name", "product_name", "category"))
        catalog = []
        for row in records(load_software_catalog()):
            if not policy.lower(row.get("status")).startswith("approved"):
                continue
            basis = [label for label, mine, theirs in (
                ("same vendor", vendor, row.get("vendor_name")), ("same product", product, row.get("product_name")),
                ("same category", category, row.get("category"))) if mine and mine == policy.lower(theirs)]
            if basis:
                catalog.append({**row, "match_basis": basis})
        purchases = [
            row for row in records(load_purchase_history())
            if policy.lower(row.get("status")) == "approved"
            and ((vendor and vendor == policy.lower(row.get("vendor_name"))) or (product and product == policy.lower(row.get("product_name"))))
        ]
        g.catalog_matches, g.purchase_matches = catalog, purchases
        refs = [f"data/software_catalog.csv#{r['software_id']}" for r in catalog] + [f"data/purchase_history.csv#{r['purchase_id']}" for r in purchases]
        return {"ok": True, "refs": refs, "catalog_matches": catalog, "purchase_history_matches": purchases,
                "note": "A match shows an existing product, not proof it meets the need or has spare capacity."}

    def _get_vendor_status(self, caller: str) -> dict[str, Any]:
        g = self.gathered
        vendor = policy.text(self.request.get("vendor_name") or "")
        g.registry = next((r for r in records(load_vendors()) if policy.lower(r.get("vendor_name")) == policy.lower(vendor)), None) if vendor else None
        g.registry_checked = True
        started = time.perf_counter()
        result = vendor_fetcher(vendor) if vendor else VendorRiskResult("not_found", error="no vendor name supplied")
        elapsed = (time.perf_counter() - started) * 1000
        for attempt in range(1, max(result.attempts, 1) + 1):
            last = attempt == result.attempts
            failed = not (last and result.status in {"ok", "not_found"})
            self.recorder.record_tool(
                name="get_vendor_status", caller=caller, ok=not failed,
                status=result.status if last else "unavailable", latency_ms=elapsed / max(result.attempts, 1),
                is_retry=attempt > 1, timed_out=failed and result.timed_out and last, error=result.error if failed else None)
        g.vendor_risk, g.vendor_fetch_status, g.vendor_error = result.data, result.status, result.error
        refs = ([f"data/vendors.csv#{g.registry['vendor_id']}"] if g.registry else []) + [f"GET /vendor-risk/{vendor}"]
        return {
            "ok": True,
            "refs": refs,
            "vendor_registry": g.registry,
            "vendor_risk_api": {"status": result.status, "http_status": result.http_status, "error": result.error,
                                "record": result.data, "assessment_state": policy.vendor_risk_state(result.data, result.status)},
            "note": "status 'unavailable' means the assessment could not be verified: it is not favourable, not expired, and not unsafe.",
        }

    def _check_policy(self, caller: str) -> dict[str, Any]:
        for name in DATA_TOOLS:  # prerequisites are run (and recorded) if the caller skipped them
            if name not in self.gathered.tools_done:
                self.dispatch(name, {"request_id": self.request.get("request_id")}, caller=f"{caller}:prerequisite")
        result = policy.evaluate(self.gathered, None)
        return policy_summary(result)


def policy_summary(result: policy.PolicyResult) -> dict[str, Any]:
    return {
        "ok": True,
        "spend_tier": result.spend_tier,
        "annual_cost_usd": None if result.cost is None else float(result.cost),
        "available_budget_usd": result.available_budget,
        "budget_shortfall_usd": None if result.shortfall is None else float(result.shortfall),
        "vendor_assessment_state": result.vendor_state,
        "missing_information": result.missing_information,
        "risk_flags": sorted(result.risk_flags),
        "required_approvals": result.required_approvals,
        "recommendation_code": result.recommendation_code,
        "triggers": result.triggers,
        "authority": "deterministic; the model cannot change these values",
    }


def tool_output_for_model(result: dict[str, Any], limit: int = 2500) -> str:
    """Compact JSON for the model (long free-text is truncated; it is data, not instructions)."""
    text = json.dumps(result, default=_jsonable, separators=(",", ":"))
    return text if len(text) <= limit else text[:limit] + '..."[truncated]"'
