from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
APPROVALS = {
    "manager", "department head", "procurement", "finance", "cfo", "security", "privacy", "legal"
}
RISK_FLAGS = {
    "existing_tool_overlap", "budget_insufficient", "security_review_required",
    "privacy_review_required", "legal_review_required", "vendor_review_expired",
    "conflicting_vendor_evidence", "vendor_risk_unavailable", "prompt_injection_detected",
    "missing_information", "budget_data_unverified"
}
RECOMMENDATIONS = {
    "proceed_to_required_approvals", "request_clarification",
    "route_for_budget_exception", "route_for_manual_review"
}
PUBLIC_CASE_REQUESTS = {
    "PUB-01": "REQ-1001", "PUB-02": "REQ-1002", "PUB-03": "REQ-1003",
    "PUB-04": "REQ-1005", "PUB-05": "REQ-1006", "PUB-06": "REQ-1009"
}
EVIDENCE_STATUSES = {"verified", "missing", "expired", "unknown", "unavailable", "conflicting"}
EXPECTATION_FIELDS = {
    "required_approvals_all_of", "required_approvals_one_of_groups", "forbidden_approvals",
    "required_risk_flags_all_of", "required_risk_flags_one_of_groups", "forbidden_risk_flags",
    "allowed_extra_risk_flags", "required_missing_information_all_of", "required_recommendation",
    "required_human_review", "required_next_step_properties", "required_evidence",
    "manual_grounding_review"
}
CASE_FIELDS = {"case_id", "request_id", "title", "what_it_tests", "expectations"}
APPROVAL_ALIASES = {"dept head": "department head", "department-head": "department head"}
RISK_ALIASES = {
    "overlap": "existing_tool_overlap",
    "budget": "budget_insufficient",
    "security": "security_review_required",
    "privacy": "privacy_review_required",
    "legal": "legal_review_required",
    "unavailable": "vendor_risk_unavailable",
    "tool failure": "vendor_risk_unavailable",
    "api": "vendor_risk_unavailable",
    "missing": "missing_information",
    "prompt injection": "prompt_injection_detected",
    "untrusted": "prompt_injection_detected",
}
MISSING_ALIASES = {
    "annual cost": "annual_cost_usd", "cost": "annual_cost_usd", "price": "annual_cost_usd",
    "users": "user_count", "user count": "user_count", "license count": "user_count",
    "seat count": "user_count", "data access": "data_access_level",
    "data access scope": "data_access_level", "business purpose": "business_justification",
    "business justification": "business_justification",
}


def _text(value: Any) -> str:
    return " ".join(str(value).split()).casefold()


def _unique_string_list(value: Any, path: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"{path} must be an array of non-empty strings")
    normalized = [_text(item) for item in value]
    if len(normalized) != len(set(normalized)):
        raise ValueError(f"{path} must not contain duplicates")
    return value


def _normalize_approval(value: str) -> str:
    normalized = _text(value)
    normalized = APPROVAL_ALIASES.get(normalized, normalized)
    if normalized not in APPROVALS:
        raise ValueError(f"Unknown approval value: {value}")
    return normalized


def _normalize_flag(value: str) -> str:
    normalized = _text(value)
    normalized = RISK_ALIASES.get(normalized, normalized)
    if normalized not in RISK_FLAGS:
        raise ValueError(f"Unknown risk flag: {value}")
    return normalized


def _normalize_missing(value: str) -> str:
    normalized = _text(value).replace("-", " ").replace("_", " ")
    normalized = " ".join(normalized.split())
    return MISSING_ALIASES.get(normalized, normalized.replace(" ", "_"))


def validate_cases(cases: Any, request_ids: set[str]) -> None:
    if not isinstance(cases, list) or not cases:
        raise ValueError("Public cases must be a non-empty array")
    seen_case_ids: set[str] = set()
    actual_case_requests: dict[str, str] = {}
    for index, case in enumerate(cases):
        path = f"cases[{index}]"
        if not isinstance(case, dict) or set(case) != CASE_FIELDS:
            raise ValueError(f"{path} must contain exactly {sorted(CASE_FIELDS)}")
        for field in ("case_id", "request_id", "title", "what_it_tests"):
            if not isinstance(case[field], str) or not case[field].strip():
                raise ValueError(f"{path}.{field} must be a non-empty string")
        if case["case_id"] in seen_case_ids:
            raise ValueError(f"Duplicate case_id: {case['case_id']}")
        seen_case_ids.add(case["case_id"])
        actual_case_requests[case["case_id"]] = case["request_id"]
        if case["request_id"] not in request_ids:
            raise ValueError(f"{path}.request_id does not resolve: {case['request_id']}")

        expectations = case["expectations"]
        if not isinstance(expectations, dict):
            raise ValueError(f"{path}.expectations must be an object")
        missing_keys = EXPECTATION_FIELDS - set(expectations)
        unknown_keys = set(expectations) - EXPECTATION_FIELDS
        if missing_keys or unknown_keys:
            raise ValueError(f"{path}.expectations missing={sorted(missing_keys)} unsupported={sorted(unknown_keys)}")

        list_fields = (
            "required_approvals_all_of", "forbidden_approvals", "required_risk_flags_all_of",
            "forbidden_risk_flags", "allowed_extra_risk_flags", "required_missing_information_all_of",
            "required_next_step_properties"
        )
        for field in list_fields:
            _unique_string_list(expectations[field], f"{path}.expectations.{field}")
        for value in expectations["required_approvals_all_of"] + expectations["forbidden_approvals"]:
            _normalize_approval(value)
        for value in expectations["required_risk_flags_all_of"] + expectations["forbidden_risk_flags"] + expectations["allowed_extra_risk_flags"]:
            _normalize_flag(value)
        for value in expectations["required_missing_information_all_of"]:
            _normalize_missing(value)
        if not isinstance(expectations["required_human_review"], bool):
            raise ValueError(f"{path}.expectations.required_human_review must be Boolean")
        if expectations["required_recommendation"] not in RECOMMENDATIONS:
            raise ValueError(f"{path}.expectations.required_recommendation is unsupported")

        groups = (
            ("required_approvals_one_of_groups", _normalize_approval),
            ("required_risk_flags_one_of_groups", _normalize_flag),
        )
        for field, normalizer in groups:
            value = expectations[field]
            if not isinstance(value, list):
                raise ValueError(f"{path}.expectations.{field} must be an array of arrays")
            for group_index, group in enumerate(value):
                choices = _unique_string_list(group, f"{path}.expectations.{field}[{group_index}]")
                if not choices:
                    raise ValueError(f"{path}.expectations.{field}[{group_index}] cannot be empty")
                for choice in choices:
                    normalizer(choice)

        approval_required = {_normalize_approval(x) for x in expectations["required_approvals_all_of"]}
        approval_forbidden = {_normalize_approval(x) for x in expectations["forbidden_approvals"]}
        flag_required = {_normalize_flag(x) for x in expectations["required_risk_flags_all_of"]}
        flag_forbidden = {_normalize_flag(x) for x in expectations["forbidden_risk_flags"]}
        if approval_required & approval_forbidden or flag_required & flag_forbidden:
            raise ValueError(f"{path}.expectations has a value both required and forbidden")
        for group in expectations["required_approvals_one_of_groups"]:
            if {_normalize_approval(x) for x in group} & approval_forbidden:
                raise ValueError(f"{path}.expectations has an approval alternative that is forbidden")
        for group in expectations["required_risk_flags_one_of_groups"]:
            if {_normalize_flag(x) for x in group} & flag_forbidden:
                raise ValueError(f"{path}.expectations has a risk-flag alternative that is forbidden")

        evidence = expectations["required_evidence"]
        if not isinstance(evidence, list) or not evidence:
            raise ValueError(f"{path}.expectations.required_evidence must be a non-empty array")
        for evidence_index, item in enumerate(evidence):
            evidence_path = f"{path}.expectations.required_evidence[{evidence_index}]"
            allowed_evidence_keys = {"source", "reference", "finding_contains_all", "evidence_status"}
            if not isinstance(item, dict) or not {"source", "reference", "finding_contains_all"} <= set(item) or set(item) - allowed_evidence_keys:
                raise ValueError(f"{evidence_path} has missing or unsupported fields")
            for field in ("source", "reference"):
                if not isinstance(item[field], str) or not item[field].strip():
                    raise ValueError(f"{evidence_path}.{field} must be a non-empty string")
            fragments = _unique_string_list(item["finding_contains_all"], f"{evidence_path}.finding_contains_all")
            if not fragments:
                raise ValueError(f"{evidence_path}.finding_contains_all cannot be empty")
            if "evidence_status" in item and item["evidence_status"] not in EVIDENCE_STATUSES:
                raise ValueError(f"{evidence_path}.evidence_status is unsupported")

        review = expectations["manual_grounding_review"]
        if not isinstance(review, dict) or set(review) != {"required", "checklist"}:
            raise ValueError(f"{path}.expectations.manual_grounding_review must contain required and checklist")
        if review["required"] is not True:
            raise ValueError(f"{path}.expectations.manual_grounding_review.required must be true")
        checklist = _unique_string_list(review["checklist"], f"{path}.expectations.manual_grounding_review.checklist")
        if not checklist:
            raise ValueError(f"{path}.expectations.manual_grounding_review.checklist cannot be empty")
    if actual_case_requests != PUBLIC_CASE_REQUESTS:
        raise ValueError("Public case IDs and request associations must match the six assessment cases")


def validate_grounding_reviews(
    reviews: Any, case_checklists: dict[str, list[str]]
) -> dict[str, dict[str, Any]]:
    if not isinstance(reviews, list):
        raise ValueError("Grounding review file must be an array")
    result: dict[str, dict[str, Any]] = {}
    for index, review in enumerate(reviews):
        required_keys = {"case_id", "status", "reviewer", "notes", "checklist_results"}
        if not isinstance(review, dict) or set(review) != required_keys:
            raise ValueError(f"grounding_reviews[{index}] has missing or unsupported fields")
        if review["case_id"] not in case_checklists:
            raise ValueError(f"Unknown grounding-review case: {review['case_id']}")
        if review["case_id"] in result:
            raise ValueError(f"Duplicate grounding-review case: {review['case_id']}")
        if review["status"] not in {"pass", "fail"}:
            raise ValueError(f"grounding_reviews[{index}].status must be pass or fail")
        for field in ("reviewer", "notes"):
            if not isinstance(review[field], str) or not review[field].strip():
                raise ValueError(f"grounding_reviews[{index}].{field} must be a non-empty string")
        checklist_results = review["checklist_results"]
        expected_checklist = set(case_checklists[review["case_id"]])
        if not isinstance(checklist_results, dict) or set(checklist_results) != expected_checklist:
            raise ValueError(f"grounding_reviews[{index}].checklist_results must answer every case checklist item exactly")
        if any(not isinstance(result, bool) for result in checklist_results.values()):
            raise ValueError(f"grounding_reviews[{index}].checklist_results values must be Boolean")
        checklist_passed = all(checklist_results.values())
        if (review["status"] == "pass") != checklist_passed:
            raise ValueError(f"grounding_reviews[{index}].status conflicts with checklist_results")
        result[review["case_id"]] = review
    return result


def _decision_dict(decision: Any) -> dict[str, Any]:
    if hasattr(decision, "model_dump"):
        decision = decision.model_dump()
    if not isinstance(decision, dict):
        raise ValueError("Decision must be a mapping or Pydantic model")
    required = {
        "request_id", "recommendation", "recommendation_code", "evidence", "required_approvals",
        "missing_information", "risk_flags", "next_step", "human_review_required"
    }
    missing = required - set(decision)
    if missing:
        raise ValueError(f"Decision is missing required fields: {sorted(missing)}")
    return decision


def evaluate(decision: Any, expectations: dict[str, Any], expected_request_id: str | None = None) -> list[str]:
    decision = _decision_dict(decision)
    failures: list[str] = []
    if expected_request_id is not None and decision["request_id"] != expected_request_id:
        failures.append(f"request_id expected {expected_request_id}")
    approvals = decision["required_approvals"]
    flags = decision["risk_flags"]
    missing_info = decision["missing_information"]
    evidence = decision["evidence"]
    if not isinstance(approvals, list) or not isinstance(flags, list) or not isinstance(missing_info, list) or not isinstance(evidence, list):
        raise ValueError("Decision approvals, flags, missing information, and evidence must be arrays")

    try:
        actual_approvals = [_normalize_approval(item) for item in approvals]
        actual_flags = [_normalize_flag(item) for item in flags]
        actual_missing = [_normalize_missing(item) for item in missing_info]
    except (TypeError, ValueError) as exc:
        failures.append(str(exc))
        actual_approvals, actual_flags, actual_missing = [], [], []
    if len(actual_approvals) != len(set(actual_approvals)):
        failures.append("duplicate approvals")
    if len(actual_flags) != len(set(actual_flags)):
        failures.append("duplicate risk flags")
    if len(actual_missing) != len(set(actual_missing)):
        failures.append("duplicate missing-information items")

    expected = expectations
    required_approvals = {_normalize_approval(x) for x in expected["required_approvals_all_of"]}
    approval_groups = [[_normalize_approval(x) for x in group] for group in expected["required_approvals_one_of_groups"]]
    forbidden_approvals = {_normalize_approval(x) for x in expected["forbidden_approvals"]}
    actual_approval_set = set(actual_approvals)
    for role in required_approvals - actual_approval_set:
        failures.append(f"required approval missing: {role}")
    for group in approval_groups:
        if not actual_approval_set.intersection(group):
            failures.append(f"approval alternative group unsatisfied: {group}")
    for role in forbidden_approvals & actual_approval_set:
        failures.append(f"forbidden approval present: {role}")
    allowed_approvals = required_approvals.union(*(set(group) for group in approval_groups)) if approval_groups else required_approvals
    for role in actual_approval_set - allowed_approvals:
        failures.append(f"unjustified extra approval: {role}")

    required_flags = {_normalize_flag(x) for x in expected["required_risk_flags_all_of"]}
    flag_groups = [[_normalize_flag(x) for x in group] for group in expected["required_risk_flags_one_of_groups"]]
    forbidden_flags = {_normalize_flag(x) for x in expected["forbidden_risk_flags"]}
    allowed_flags = required_flags | {_normalize_flag(x) for x in expected["allowed_extra_risk_flags"]}
    allowed_flags.update(*(set(group) for group in flag_groups))
    actual_flag_set = set(actual_flags)
    for flag in required_flags - actual_flag_set:
        failures.append(f"required risk flag missing: {flag}")
    for group in flag_groups:
        if not actual_flag_set.intersection(group):
            failures.append(f"risk-flag alternative group unsatisfied: {group}")
    for flag in forbidden_flags & actual_flag_set:
        failures.append(f"forbidden risk flag present: {flag}")
    for flag in actual_flag_set - allowed_flags:
        failures.append(f"unjustified extra risk flag: {flag}")

    expected_missing = {_normalize_missing(x) for x in expected["required_missing_information_all_of"]}
    for item in expected_missing - set(actual_missing):
        failures.append(f"required missing-information item absent: {item}")
    for item in set(actual_missing) - expected_missing:
        failures.append(f"unexpected missing-information item: {item}")

    if decision["recommendation_code"] != expected["required_recommendation"]:
        failures.append(f"recommendation expected {expected['required_recommendation']}")
    if decision["human_review_required"] is not expected["required_human_review"]:
        failures.append(f"human_review_required expected {expected['required_human_review']}")
    next_step = _text(decision["next_step"])
    for property_text in expected["required_next_step_properties"]:
        if _text(property_text) not in next_step:
            failures.append(f"required next-step phrase absent: {property_text}")

    for index, item in enumerate(evidence):
        if not isinstance(item, dict) or not {"source", "reference", "finding"} <= set(item):
            failures.append(f"evidence[{index}] lacks source, reference, or finding")
    for required_item in expected["required_evidence"]:
        matched = False
        for item in evidence:
            if not isinstance(item, dict):
                continue
            if _text(item.get("source", "")) != _text(required_item["source"]):
                continue
            if _text(item.get("reference", "")) != _text(required_item["reference"]):
                continue
            if "evidence_status" in required_item and item.get("evidence_status") != required_item["evidence_status"]:
                continue
            finding = _text(item.get("finding", ""))
            if all(_text(fragment) in finding for fragment in required_item["finding_contains_all"]):
                matched = True
                break
        if not matched:
            failures.append(f"required grounded evidence not matched: {required_item['source']} {required_item['reference']}")
    return failures


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read valid JSON from {path}: {exc}") from exc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--architecture", choices=["single", "staged"], default="single")
    parser.add_argument("--validate-only", action="store_true", help="Validate case schema and request references without running an architecture")
    parser.add_argument("--grounding-review", type=Path, help="Human grounding review JSON, one signed review per public case")
    args = parser.parse_args()

    try:
        cases = load_json(ROOT / "evals" / "public_cases.json")
        requests = load_json(ROOT / "data" / "requests.json")
        request_ids = {item["request_id"] for item in requests}
        validate_cases(cases, request_ids)
        case_checklists = {
            case["case_id"]: case["expectations"]["manual_grounding_review"]["checklist"]
            for case in cases
        }
        reviews = validate_grounding_reviews(load_json(args.grounding_review), case_checklists) if args.grounding_review else {}
    except (KeyError, TypeError, ValueError) as exc:
        print(f"Evaluation input invalid: {exc}", file=sys.stderr)
        return 2

    print(f"Case schema valid: {len(cases)} cases; request references valid.")
    if args.validate_only:
        print("No architecture invoked.")
        return 0

    try:
        from src.contracts import ProcurementDecision
        from src.solution import handle_request
    except ModuleNotFoundError as exc:
        print(f"Runtime evaluation blocked by missing dependency: {exc}", file=sys.stderr)
        return 2

    rows: list[dict[str, Any]] = []
    for case in cases:
        start = time.perf_counter()
        try:
            raw = handle_request(case["request_id"], architecture=args.architecture)
            decision = raw if isinstance(raw, ProcurementDecision) else ProcurementDecision.model_validate(raw)
            failures = evaluate(decision, case["expectations"], case["request_id"])
            latency_ms = (time.perf_counter() - start) * 1000
            grounding = reviews.get(case["case_id"])
            if failures:
                result = "FAIL"
            elif grounding is None:
                result = "PENDING_GROUNDING_REVIEW"
            else:
                result = "PASS" if grounding["status"] == "pass" else "FAIL"
            rows.append({
                "case_id": case["case_id"],
                "request_id": case["request_id"],
                "architecture": args.architecture,
                "automated_failures": " | ".join(failures),
                "latency_ms": round(latency_ms, 1),
                "llm_calls_observed": "",
                "tool_calls_observed": "",
                "retries_observed": "",
                "failed_calls_observed": "",
                "tool_errors_observed": "",
                "measurement_status": "call metrics require shared instrumentation; decision telemetry is not ground truth",
                "grounding_review_status": grounding["status"] if grounding else "pending",
                "grounding_reviewer": grounding["reviewer"] if grounding else "",
                "grounding_notes": grounding["notes"] if grounding else "",
                "result": result,
            })
        except NotImplementedError as exc:
            print(f"Architecture is not implemented: {exc}", file=sys.stderr)
            return 2
        except Exception as exc:
            rows.append({
                "case_id": case["case_id"], "request_id": case["request_id"],
                "architecture": args.architecture,
                "automated_failures": f"{type(exc).__name__}: {exc}",
                "latency_ms": round((time.perf_counter() - start) * 1000, 1),
                "llm_calls_observed": "", "tool_calls_observed": "", "retries_observed": "",
                "failed_calls_observed": "", "tool_errors_observed": "",
                "measurement_status": "call metrics require shared instrumentation; decision telemetry is not ground truth",
                "grounding_review_status": "pending", "grounding_reviewer": "",
                "grounding_notes": "", "result": "FAIL",
            })

    output = ROOT / "evals" / f"results_{args.architecture}.csv"
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    counts = {status: sum(row["result"] == status for row in rows) for status in ("PASS", "FAIL", "PENDING_GROUNDING_REVIEW")}
    print(f"Results: {counts}; output={output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
