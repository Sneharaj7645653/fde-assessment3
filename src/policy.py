"""Deterministic procurement policy engine (the authority on thresholds and triggers).

Pure functions over already-gathered tool results. The model never calls into
this module's decisions to change them: AI signals can only *add* caution
(clarification request, injection flag) and are applied after validation.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from src.data_access import load_policy_text

DEFAULT_REFERENCE_DATE = date(2026, 9, 30)
REVIEW_VALIDITY_DAYS = 365
LEGAL_NEW_VENDOR_THRESHOLD = Decimal("10000")

# Policy section 4 (verified against data/procurement_policy.md by tests).
TIERS: list[tuple[Decimal, list[str]]] = [
    (Decimal("1000"), ["Manager"]),
    (Decimal("10000"), ["Department Head", "Procurement"]),
    (Decimal("25000"), ["Department Head", "Finance", "Procurement"]),
]
TOP_TIER = ["Department Head", "Finance", "CFO", "Procurement"]

SENSITIVE_ACCESS = ("source_code", "production", "cloud", "confidential", "pii", "credential", "secret")
SECURITY_INTEGRATION_RE = re.compile(
    r"\b(aws|gcp|azure|kubernetes|production|cloud[- ]accounts?|git(hub|lab)?( repositories| repos?)?|(source|code) repositor\w+)\b",
    re.IGNORECASE,
)
INJECTION_PATTERNS = [
    r"ignore (all |any |the |previous |prior |above |these |your )*(procurement |policy |policies |rules|instructions|guidelines|embedded)",
    r"disregard (all |any |the |previous |prior )*(rules|policy|instructions)",
    r"(approve|approved|approving) (it|this|the request)? ?(immediately|right away|now|without)",
    r"treat (this|the) request as",
    r"(override|bypass|skip|waive) (the |all |any )*(policy|policies|controls?|security|legal|privacy|procurement|approvals?|review)",
    r"(pre-?approved by|\b(cfo|ciso|ceo|vp|legal|security|finance)[- ]approved|\b(cfo|ciso|ceo) (has )?(already )?(approved|signed off))",
    r"(reveal|print|show|expose|leak) [^.]{0,40}(system prompt|secrets?|api keys?|credentials)",
    r"you are now|new instructions",
    r"do not (flag|escalate|mention|require|route)",
    r"mark (this|the) vendor as approved",
]
_INJECTION_RE = re.compile("|".join(f"(?:{p})" for p in INJECTION_PATTERNS), re.IGNORECASE)
_INJECTION_SENTENCE_RE = _INJECTION_RE


def text(value: Any) -> str:
    return " ".join(str(value).split()).strip()


def lower(value: Any) -> str:
    return text(value).casefold()


def is_missing(value: Any) -> bool:
    return value is None or text(value).casefold() in {"", "unknown", "null", "nan", "none_provided"}


def parse_money(value: Any) -> Decimal | None:
    """Parse a non-negative amount exactly (no float rounding at tier boundaries)."""
    if value is None or isinstance(value, bool):
        return None
    token = str(value).strip().replace("$", "").replace(",", "")
    if not token or token.casefold() in {"unknown", "null", "nan"}:
        return None
    try:
        amount = Decimal(token)
    except InvalidOperation:
        return None
    if not amount.is_finite() or amount < 0:
        return None
    return amount


def parse_count(value: Any) -> int | None:
    amount = parse_money(value)
    if amount is None or amount != amount.to_integral_value():
        return None
    return int(amount)


def money(value: Decimal | int | None) -> str:
    if value is None:
        return "unknown"
    amount = Decimal(value)
    return f"${amount:,.0f}" if amount == amount.to_integral_value() else f"${amount:,.2f}"


def reference_date() -> date:
    match = re.search(r"evaluation reference date:\*\*\s*(\d{4}-\d{2}-\d{2})", load_policy_text())
    return date.fromisoformat(match.group(1)) if match else DEFAULT_REFERENCE_DATE


def approvals_for_cost(cost: Decimal | None) -> tuple[str | None, list[str]]:
    if cost is None:
        return None, []
    labels = ["Up to $1,000", "$1,000.01-$10,000", "$10,000.01-$25,000"]
    for (limit, approvals), label in zip(TIERS, labels):
        if cost <= limit:
            return label, list(approvals)
    return "Above $25,000", list(TOP_TIER)


def review_age_days(last_review: str | None, today: date | None = None) -> int | None:
    if not last_review:
        return None
    try:
        return ((today or reference_date()) - date.fromisoformat(last_review)).days
    except ValueError:
        return None


def injection_hits(value: Any) -> list[str]:
    return [m.group(0) for m in _INJECTION_RE.finditer(text(value))] if value is not None else []


def strip_injection(value: Any) -> str:
    """Business text with instruction-like sentences removed (used to judge purpose adequacy)."""
    sentences = re.split(r"(?<=[.!?])\s+", text(value))
    return " ".join(s for s in sentences if not _INJECTION_RE.search(s))


def vendor_risk_state(risk: dict | None, fetch_status: str | None) -> str:
    """Normalised vendor-assessment state. Outage, absence, incompleteness and expiry stay distinct."""
    if fetch_status == "unavailable":
        return "unavailable"
    if fetch_status == "not_found" or risk is None:
        return "missing"
    status = lower(risk.get("security_review_status") or "unknown")
    review = risk.get("last_review_date")
    if status == "approved":
        if not review:
            return "unknown"
        age = review_age_days(str(review))
        if age is None:
            return "unknown"
        return "expired" if age > REVIEW_VALIDITY_DAYS else "approved"
    if status in {"expired"}:
        return "expired"
    if status in {"not_completed", "pending", "incomplete", "in_progress"}:
        return "not_completed"
    return "unknown"


@dataclass
class Gathered:
    """Everything tools have returned for one request."""

    request: dict[str, Any]
    employee: dict | None = None
    requester_found: bool | None = None
    budget: dict | None = None
    catalog_matches: list[dict] = field(default_factory=list)
    purchase_matches: list[dict] = field(default_factory=list)
    registry: dict | None = None
    registry_checked: bool = False
    vendor_risk: dict | None = None
    vendor_fetch_status: str | None = None
    vendor_error: str | None = None
    tools_done: set[str] = field(default_factory=set)
    notes_hint: str | None = None  # operational note from the agent loop (not policy data)

    def untrusted_texts(self) -> dict[str, str]:
        """Every free-text field from business data (never treated as instructions)."""
        fields: dict[str, str] = {}
        for key in ("business_justification", "product_name", "vendor_name", "category"):
            if self.request.get(key):
                fields[f"request.{key}"] = text(self.request[key])
        for row in self.catalog_matches:
            fields[f"catalog.{row.get('software_id')}.notes"] = text(row.get("notes") or "")
        for row in self.purchase_matches:
            fields[f"purchase.{row.get('purchase_id')}.notes"] = text(row.get("notes") or "")
        if self.registry:
            fields["vendors.notes"] = text(self.registry.get("notes") or "")
        if self.vendor_risk:
            fields["vendor_risk.notes"] = text(self.vendor_risk.get("notes") or "")
        return {k: v for k, v in fields.items() if v}


@dataclass
class AISignals:
    """Validated, grounded model signals. They can only add caution, never remove it."""

    justification_inadequate: bool = False
    injection_suspected: bool = False


@dataclass
class PolicyResult:
    missing_information: list[str]
    risk_flags: set[str]
    required_approvals: list[str]
    recommendation_code: str
    spend_tier: str | None
    cost: Decimal | None
    available_budget: int | None
    shortfall: Decimal | None
    vendor_state: str
    triggers: list[dict[str, str]]
    injection_fields: list[str]
    overlap_kind: str | None  # "vendor", "category", or None
    sections: list[int]


def _budget_available(row: dict | None) -> int | None:
    if not row:
        return None
    annual, committed, stored = (parse_count(row.get(k)) for k in ("annual_software_budget_usd", "committed_usd", "available_usd"))
    if None in (annual, committed, stored) or annual - committed != stored:
        return None
    return stored


def missing_information(g: Gathered, ai: AISignals | None) -> list[str]:
    request = g.request
    missing: list[str] = []
    for field_name in ("requester_id", "product_name", "vendor_name"):
        if is_missing(request.get(field_name)):
            missing.append(field_name)
    if not is_missing(request.get("requester_id")) and g.requester_found is False:
        missing.append("requester_id")
    cost = parse_money(request.get("annual_cost_usd"))
    if is_missing(request.get("annual_cost_usd")) or cost is None:
        missing.append("annual_cost_usd")
    users = parse_count(request.get("user_count"))
    if is_missing(request.get("user_count")) or not users:
        missing.append("user_count")
    if is_missing(request.get("data_access_level")):
        missing.append("data_access_level")
    if "requested_integrations" not in request or request.get("requested_integrations") is None:
        missing.append("requested_integrations")
    justification = request.get("business_justification")
    if is_missing(justification):
        missing.append("business_justification")
    else:
        cleaned = strip_injection(justification)
        meaningful = [w for w in re.findall(r"[A-Za-z0-9']+", cleaned) if w.casefold() not in {"asap", "urgent", "urgently", "need", "needed", "please", "now"}]
        if len(meaningful) < 4 or (ai and ai.justification_inadequate):
            missing.append("business_justification")
    return list(dict.fromkeys(missing))


def evaluate(g: Gathered, ai: AISignals | None = None) -> PolicyResult:
    request = g.request
    access = lower(request.get("data_access_level") or "")
    access_known = not is_missing(request.get("data_access_level"))
    integrations = request.get("requested_integrations") or []
    integration_text = lower(" ".join(integrations) if isinstance(integrations, list) else integrations) + " "
    flags: set[str] = set()
    triggers: list[dict[str, str]] = []
    sections: set[int] = set()

    def trigger(rule: str, section: int, reason: str) -> None:
        triggers.append({"rule": rule, "policy_section": f"section-{section}", "reason": reason})
        sections.add(section)

    missing = missing_information(g, ai)
    if missing:
        flags.add("missing_information")
        sections.update({1, 9})

    injection_fields = [name for name, value in g.untrusted_texts().items() if injection_hits(value)]
    if injection_fields or (ai and ai.injection_suspected):
        flags.add("prompt_injection_detected")
        sections.add(9)

    if g.catalog_matches:
        flags.add("existing_tool_overlap")
    overlap_kind = None
    if g.catalog_matches:
        vendor = lower(request.get("vendor_name"))
        overlap_kind = "vendor" if any(lower(r.get("vendor_name")) == vendor for r in g.catalog_matches) or any(
            lower(r.get("product_name")) == lower(request.get("product_name")) for r in g.catalog_matches) else "category"

    cost = parse_money(request.get("annual_cost_usd"))
    spend_tier, tier_approvals = approvals_for_cost(cost)
    if spend_tier:
        sections.add(4)

    available = _budget_available(g.budget)
    shortfall = None
    if g.budget is None and g.requester_found:
        flags.add("budget_data_unverified")
    if g.budget is not None:
        if available is None:
            flags.add("budget_data_unverified")
        elif cost is not None and cost > available:
            flags.add("budget_insufficient")
            shortfall = cost - available
            sections.add(2)
            trigger("budget", 2, f"{money(cost)} exceeds available {money(available)}")

    state = vendor_risk_state(g.vendor_risk, g.vendor_fetch_status)
    security = False
    if state == "unavailable":
        flags.add("vendor_risk_unavailable")
        security = True
        sections.update({5, 10})
        trigger("security", 10, "vendor-risk evidence unavailable; cannot verify assessment")
    elif state == "expired":
        flags.add("vendor_review_expired")
        security = True
        trigger("security", 5, "vendor security assessment is past the 365-day window")
    elif state in {"missing", "not_completed", "unknown"}:
        security = True
        trigger("security", 5, f"vendor security assessment is {state.replace('_', ' ')}")
    if g.registry is not None and lower(g.registry.get("security_status")) in {"pending", "unknown"}:
        security = True
        trigger("security", 5, "vendor registry shows security status pending/unknown")
    if g.registry is None and g.registry_checked:
        security = True
        trigger("security", 5, "vendor is not in the vendor registry")

    conflict = False
    if g.registry is not None and g.vendor_risk is not None and state != "unavailable":
        reg_status = lower(g.registry.get("security_status"))
        reg_date = g.registry.get("security_review_date")
        risk_date = g.vendor_risk.get("last_review_date")
        if reg_status == "approved" and state in {"not_completed", "expired", "unknown", "missing"}:
            conflict = True
        elif reg_status in {"pending", "unknown"} and state == "approved":
            conflict = True
        elif reg_date and risk_date and str(reg_date) != str(risk_date):
            conflict = True
    if conflict:
        flags.add("conflicting_vendor_evidence")
        security = True
        trigger("security", 5, "vendor registry and vendor-risk service disagree")

    if access_known and any(token in access for token in ("source_code", "production", "cloud", "confidential", "pii", "credential", "secret")):
        security = True
        trigger("security", 5, f"data access level '{request.get('data_access_level')}' is security-sensitive")
    if SECURITY_INTEGRATION_RE.search(integration_text):
        security = True
        trigger("security", 5, "requested integration touches code, production, or cloud accounts")
    if security:
        flags.add("security_review_required")
        sections.add(5)

    sensitive_scope = access_known and any(t in access for t in SENSITIVE_ACCESS)
    outside = bool(g.vendor_risk and g.vendor_risk.get("stores_data_outside_region") is True)
    privacy = access_known and "pii" in access
    if privacy:
        trigger("privacy", 6, "tool will process employee or customer PII")
    elif sensitive_scope and outside:
        privacy = True
        trigger("privacy", 6, "sensitive data may be stored outside the operating region")
    if privacy:
        flags.add("privacy_review_required")
        sections.add(6)

    legal = False
    registry = g.registry or {}
    if cost is not None and lower(registry.get("procurement_status")) == "new" and cost >= LEGAL_NEW_VENDOR_THRESHOLD:
        legal = True
        trigger("legal", 7, f"new vendor with annual spend {money(cost)} (>= $10,000)")
    if g.registry is not None and lower(registry.get("legal_terms_status")) not in {"approved", "standard"}:
        legal = True
        trigger("legal", 7, f"legal terms status is '{registry.get('legal_terms_status')}', not approved/standard")
    elif g.registry is None and g.registry_checked:
        legal = True
        trigger("legal", 7, "vendor is not in the registry, so no approved legal terms are on file")
    if sensitive_scope and outside:
        legal = True
        trigger("legal", 7, "material cross-region data-processing issue")
    if legal:
        flags.add("legal_review_required")
        sections.add(7)

    approvals = list(tier_approvals)
    for flag, role in (("security_review_required", "Security"), ("privacy_review_required", "Privacy"), ("legal_review_required", "Legal")):
        if flag in flags:
            approvals.append(role)
    approvals = list(dict.fromkeys(approvals))

    if missing:
        code = "request_clarification"
    elif "budget_insufficient" in flags:
        code = "route_for_budget_exception"
    elif "vendor_risk_unavailable" in flags or "conflicting_vendor_evidence" in flags:
        code = "route_for_manual_review"
    else:
        code = "proceed_to_required_approvals"

    return PolicyResult(
        missing_information=missing, risk_flags=flags, required_approvals=approvals, recommendation_code=code,
        spend_tier=spend_tier, cost=cost, available_budget=available, shortfall=shortfall, vendor_state=state,
        triggers=triggers, injection_fields=injection_fields, overlap_kind=overlap_kind, sections=sorted(sections),
    )
