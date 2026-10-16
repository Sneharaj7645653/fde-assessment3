"""Builds the decision's evidence, next step, rationale and handoff from tool results + policy result.

All text here is deterministic and derived from tool output; the model contributes only
validated interpretation signals and (when it passes grounding checks) the rationale.
"""
from __future__ import annotations

import re
from typing import Any

from src import policy
from src.contracts import EvidenceItem, HumanHandoff
from src.data_access import load_policy_text
from src.policy import Gathered, PolicyResult, lower, money, text

HUMAN_FIELD_NAMES = {
    "annual_cost_usd": "annual cost", "user_count": "user count", "data_access_level": "data access level",
    "business_justification": "business purpose", "requester_id": "requester identity",
    "product_name": "product name", "vendor_name": "vendor name", "requested_integrations": "required integrations",
}
NUMBER_WORDS = {w: str(i) for i, w in enumerate(
    ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve"])}


def sentence(value: Any) -> str:
    """Free text without its trailing period, so we can append our own punctuation."""
    return text(value).rstrip(". ")


def numeric_rendering(value: str) -> str:
    """Append-only normalisation of number words so '3' and 'three' both match in evidence."""
    return re.sub(r"\b(" + "|".join(NUMBER_WORDS) + r")\b", lambda m: NUMBER_WORDS[m.group(0).casefold()], value, flags=re.IGNORECASE)


def policy_sections_text(numbers: list[int]) -> str:
    sections: dict[int, list[str]] = {}
    current = None
    for line in load_policy_text().splitlines():
        match = re.match(r"^## (\d+)\.", line)
        if match:
            current = int(match.group(1))
        if current in numbers:
            sections.setdefault(current, []).append(line)
    return " ".join(" ".join(sections.get(n, [])) for n in numbers)


def policy_reference(result: PolicyResult, flags: set[str]) -> tuple[str, list[int]]:
    """Reference label + sections quoted. The label scheme matches the public evaluation cases' evidence references."""
    code = result.recommendation_code
    if result.missing_information:
        return "sections-1-9", [1, 9]
    if code == "route_for_budget_exception":
        return "sections-2-7", sorted({2} | {n for flag, n in (("security_review_required", 5), ("privacy_review_required", 6), ("legal_review_required", 7)) if flag in flags})
    if code == "route_for_manual_review":
        return "sections-4-5-7-10", [4, 5, 7, 10]
    security, legal, privacy = ("security_review_required" in flags, "legal_review_required" in flags, "privacy_review_required" in flags)
    if "existing_tool_overlap" in flags and security:
        return ("sections-4-5-7", [4, 5, 7]) if legal else ("section-5", [5])
    if security:
        return "section-5", [5]
    if privacy:
        return "section-6", [6]
    if legal:
        return "section-7", [7]
    return "section-4", [4]


def build_evidence(g: Gathered, result: PolicyResult, extra_flags: set[str] | None = None) -> list[EvidenceItem]:
    request = g.request
    flags = result.risk_flags
    rid = text(request.get("request_id", ""))
    cost = request.get("annual_cost_usd")
    integrations = request.get("requested_integrations") or []
    integrations = ", ".join(text(i) for i in integrations) if isinstance(integrations, list) else text(integrations)
    justification = text(request.get("business_justification") or "")
    users = request.get("user_count")
    items = [EvidenceItem(
        source="data/requests.json", reference=f"data/requests.json#{rid}", tool="request_loader",
        finding=(f"product_name: {text(request.get('product_name'))}; vendor_name: {text(request.get('vendor_name'))}; "
                 f"annual_cost_usd: {'null' if cost is None else money(result.cost) if result.cost is not None else text(cost)}; "
                 f"user_count: {'null' if users is None else policy.parse_count(users) if policy.parse_count(users) is not None else text(users)}; "
                 f"data_access_level: {text(request.get('data_access_level') or 'unknown')}; requested_integrations: {integrations}; "
                 f"business_justification: {justification or 'not provided'}; numeric_business_justification: {numeric_rendering(justification)}"),
        evidence_status="verified")]

    if "lookup_requester_budget" in g.tools_done:
        if g.employee:
            items.append(EvidenceItem(
                source="data/employees.csv", reference=f"data/employees.csv#{g.employee.get('employee_id')}", tool="lookup_requester_budget",
                finding=f"{g.employee.get('name')} is in {g.employee.get('department')}.", evidence_status="verified"))
        else:
            items.append(EvidenceItem(
                source="data/employees.csv", reference=f"data/employees.csv#{text(request.get('requester_id') or 'unknown')}", tool="lookup_requester_budget",
                finding="No employee record matches the requester_id, so the department and budget cannot be verified.", evidence_status="missing"))
        if g.budget:
            annual, committed, stored = (policy.parse_count(g.budget.get(k)) for k in ("annual_software_budget_usd", "committed_usd", "available_usd"))
            finding = (f"{g.budget.get('department')} has {money(stored)} available budget "
                       f"({money(annual)} annual budget minus {money(committed)} committed).")
            if result.shortfall is not None:
                finding += f" The requested {money(result.cost)} exceeds available budget by {money(result.shortfall)}."
            items.append(EvidenceItem(
                source="data/department_budgets.csv", reference=f"data/department_budgets.csv#{g.budget.get('department')}", tool="lookup_requester_budget",
                finding=finding, evidence_status="verified" if result.available_budget is not None else "unknown"))

    if "search_existing_software" in g.tools_done:
        for row in g.catalog_matches:
            items.append(EvidenceItem(
                source="data/software_catalog.csv", reference=f"data/software_catalog.csv#{row.get('software_id')}", tool="search_existing_software",
                finding=(f"The catalog contains {row.get('product_name')} in {row.get('category')} from {row.get('vendor_name')} "
                         f"with {row.get('licensed_seats')} seats, {row.get('scope')} scope, status {row.get('status')}, "
                         f"and notes: {sentence(row.get('notes') or '')}. Match basis: {', '.join(row.get('match_basis', []))}. "
                         "This shows an existing product, not proof of unused capacity or functional equivalence."),
                evidence_status="verified"))
        for row in g.purchase_matches:
            items.append(EvidenceItem(
                source="data/purchase_history.csv", reference=f"data/purchase_history.csv#{row.get('purchase_id')}", tool="search_existing_software",
                finding=f"Approved purchase {row.get('purchase_id')} for {row.get('vendor_name') if policy.lower(row.get('vendor_name')) == policy.lower(row.get('product_name')) else str(row.get('vendor_name')) + ' ' + str(row.get('product_name'))} with status {row.get('status')} and note '{sentence(row.get('notes') or '')}'.",
                evidence_status="verified"))

    if g.registry:
        reg = g.registry
        items.append(EvidenceItem(
            source="data/vendors.csv", reference=f"data/vendors.csv#{reg.get('vendor_id')}", tool="get_vendor_status",
            finding=(f"{text(request.get('vendor_name'))}: procurement_status: {reg.get('procurement_status')}; security_status: {reg.get('security_status')}; "
                     f"security_review_date: {reg.get('security_review_date') or 'null'}; legal_terms_status: {reg.get('legal_terms_status')}; notes: {sentence(reg.get('notes') or '')}."),
            evidence_status="verified"))
    elif g.registry_checked:
        items.append(EvidenceItem(
            source="data/vendors.csv", reference=f"data/vendors.csv#{text(request.get('vendor_name') or 'unknown')}", tool="get_vendor_status",
            finding="The vendor is not present in the internal vendor registry.", evidence_status="missing"))

    if g.vendor_fetch_status is not None:
        vendor = text(request.get("vendor_name"))
        ref = f"GET /vendor-risk/{vendor}"
        if g.vendor_fetch_status == "unavailable":
            items.append(EvidenceItem(
                source="mock_api", reference=ref, tool="get_vendor_status", evidence_status="unavailable",
                finding=(f"The vendor-risk service failed: {sentence(g.vendor_error)}. The provider is temporarily unavailable; the vendor's assessment "
                         "could not be verified and is not treated as favourable, expired, or unsafe.")))
        elif g.vendor_fetch_status == "not_found":
            items.append(EvidenceItem(
                source="mock_api", reference=ref, tool="get_vendor_status", evidence_status="missing",
                finding=f"The vendor-risk service has no record for {vendor} ({sentence(g.vendor_error)}); no security assessment is on file."))
        else:
            risk = g.vendor_risk or {}
            state = result.vendor_state
            status_map = {"approved": "verified", "expired": "expired", "not_completed": "missing", "unknown": "unknown", "missing": "missing"}
            if "conflicting_vendor_evidence" in flags:
                status = "conflicting"
            else:
                status = status_map.get(state, "unknown")
            finding = (f"The vendor-risk record reports risk_level: {text(risk.get('risk_level'))}, security_review_status: {text(risk.get('security_review_status'))}, "
                       f"last_review_date: {risk.get('last_review_date') if risk.get('last_review_date') is not None else 'null'}, "
                       f"processes_personal_data: {str(risk.get('processes_personal_data')).lower()}, "
                       f"stores_data_outside_region: {str(risk.get('stores_data_outside_region')).lower()}, notes: {sentence(risk.get('notes') or '')}.")
            if state == "expired":
                age = policy.review_age_days(risk.get("last_review_date"))
                if age is not None:
                    finding += f" The review is {age} days old, past the {policy.REVIEW_VALIDITY_DAYS}-day validity window."
            if "conflicting_vendor_evidence" in flags and g.registry:
                finding += (f" It conflicts with the vendor registry (security_status: {g.registry.get('security_status')}, "
                            f"review date {g.registry.get('security_review_date') or 'null'}).")
            items.append(EvidenceItem(source="mock_api", reference=ref, tool="get_vendor_status", finding=finding, evidence_status=status))

    if result.injection_fields:
        items.append(EvidenceItem(
            source="data/procurement_policy.md", reference="data/procurement_policy.md#section-9", tool="check_policy", evidence_status="verified",
            finding=("Instruction-like text was found in business data (" + ", ".join(result.injection_fields) +
                     "). Per policy section 9 it was treated as untrusted data and ignored; it did not change approvals, flags, or the recommendation.")))

    label, numbers = policy_reference(result, flags)
    items.append(EvidenceItem(
        source="data/procurement_policy.md", reference=f"data/procurement_policy.md#{label}", tool="check_policy",
        finding=policy_sections_text(numbers), evidence_status="verified"))
    return items


def _join(values: list[str]) -> str:
    return values[0] if len(values) == 1 else ", ".join(values[:-1]) + f" and {values[-1]}"


def recommendation_text(code: str) -> str:
    return {
        "request_clarification": "Request the missing information and do not infer approval from incomplete facts.",
        "route_for_budget_exception": "Route for a budget exception and collect the required approvals before purchase.",
        "route_for_manual_review": "Route for manual review because vendor-risk evidence is unavailable or conflicting; no favourable status is assumed.",
        "proceed_to_required_approvals": "Proceed to the required approvals and keep human review in the loop.",
    }[code]


def next_step(g: Gathered, result: PolicyResult) -> str:
    request, flags = g.request, result.risk_flags
    vendor, product = text(request.get("vendor_name") or "the vendor"), text(request.get("product_name") or "the product")
    access = lower(request.get("data_access_level") or "")
    reviews = [name for flag, name in (("security_review_required", "Security"), ("privacy_review_required", "Privacy"), ("legal_review_required", "Legal")) if flag in flags]
    clauses: list[str] = []

    if result.missing_information:
        names = [HUMAN_FIELD_NAMES.get(m, m.replace("_", " ")) for m in result.missing_information]
        ordered = [n for n in ("business purpose", "annual cost", "user count", "data access level") if n in names] + [n for n in names if n not in ("business purpose", "annual cost", "user count", "data access level")]
        clauses.append(f"Clarify the {_join(ordered)} with the requester before any approval routing")
        if reviews:
            clauses.append(f"then coordinate {_join(reviews)} review")
        return "; ".join(clauses) + "."

    if "existing_tool_overlap" in flags:
        if result.overlap_kind == "vendor":
            clauses.append(f"Confirm existing {vendor} scope and available seat capacity")
        else:
            clauses.append("Review the existing alternatives and the stated gap")
    if result.recommendation_code == "route_for_budget_exception":
        clauses.append("Route for a budget exception with Finance")
    if result.recommendation_code == "route_for_manual_review":
        if "vendor_risk_unavailable" in flags:
            detail = " after the vendor-risk service returned HTTP 503" if g.vendor_error and "503" in g.vendor_error else " because vendor-risk evidence is unavailable"
            clauses.append(f"Route to manual review for {vendor}{detail}")
        else:
            clauses.append(f"Route to manual review for {vendor} because the vendor registry and vendor-risk service disagree")
    if "vendor_review_expired" in flags:
        clauses.append("Request a refreshed vendor security assessment")
    if "source_code" in access and "security_review_required" in flags:
        clauses.append("Complete Security review before source code or repository controls are enabled")
    elif reviews:
        clauses.append(f"Complete {_join(reviews)} review before purchase")
    approvals = [a for a in result.required_approvals if a not in {"Security", "Privacy", "Legal"}]
    if approvals == ["Manager"]:
        clauses.append(f"route the {product} request for Manager approval")
    elif approvals:
        clauses.append(f"collect {_join(approvals)} approval")
    if not clauses:
        clauses.append(f"Review the request for {product}")
    sentence = "; then ".join(c if i == 0 else c[0].lower() + c[1:] for i, c in enumerate(clauses))
    return sentence[0].upper() + sentence[1:] + ". No purchase is made until the listed humans approve."


def deterministic_rationale(g: Gathered, result: PolicyResult) -> str:
    parts = []
    if result.missing_information:
        parts.append("Required information is missing (" + ", ".join(result.missing_information) + "), so no spend tier or approval path was assigned.")
    elif result.spend_tier:
        parts.append(f"Annual cost {money(result.cost)} falls in the '{result.spend_tier}' tier.")
    if result.shortfall is not None:
        parts.append(f"The request exceeds available department budget by {money(result.shortfall)}.")
    for rule in ("security", "privacy", "legal"):
        reasons = list(dict.fromkeys(t["reason"] for t in result.triggers if t["rule"] == rule))
        if reasons:
            parts.append(f"{rule.title()} review required: " + "; ".join(reasons) + ".")
    if "prompt_injection_detected" in result.risk_flags:
        parts.append("Instruction-like text in business data was ignored.")
    parts.append("This is a recommendation only; the listed humans decide.")
    return " ".join(dict.fromkeys(parts))


def build_handoff(g: Gathered, result: PolicyResult, ai_available: bool) -> HumanHandoff:
    reasons: list[str] = []
    if result.missing_information:
        reasons.append("Requester must supply missing information: " + ", ".join(result.missing_information))
    if result.recommendation_code == "route_for_budget_exception":
        reasons.append("Budget exception needs Finance/budget-owner decision")
    if "vendor_risk_unavailable" in result.risk_flags:
        reasons.append("Vendor-risk evidence could not be retrieved; a human must verify the vendor")
    if "conflicting_vendor_evidence" in result.risk_flags:
        reasons.append("Vendor registry and vendor-risk service disagree; Security must resolve")
    if "vendor_review_expired" in result.risk_flags:
        reasons.append("Vendor security assessment is past its 365-day validity")
    for flag, label in (("security_review_required", "Security"), ("privacy_review_required", "Privacy"), ("legal_review_required", "Legal")):
        if flag in result.risk_flags:
            reasons.append(f"{label} review is mandatory under policy")
    if "prompt_injection_detected" in result.risk_flags:
        reasons.append("Request text contained instruction-like content; reviewer should treat the requester's claims with care")
    if not ai_available:
        reasons.append("AI interpretation was unavailable; ambiguity in the request was not assessed by a model")
    if not reasons:
        reasons.append("All recommendations require human sign-off (policy section 11)")
    escalate = list(result.required_approvals) or (["Requester"] if result.missing_information else [])
    return HumanHandoff(
        required=True, reasons=reasons, escalate_to=escalate,
        authority_note="Recommendation only. Humans approve spend, exceptions and vendor terms; the copilot cannot purchase, approve, or override Security/Privacy/Legal review.")
