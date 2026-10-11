# Pre-Implementation Review

> **Superseded status notice (2026-10-09):** This review contains the initial pre-implementation findings and readiness decision. Its prior `READY FOR IMPLEMENTATION` conclusion and claims that evaluation semantics were complete are no longer authoritative. See [06-audit-corrections.md](06-audit-corrections.md) for the corrected findings, validation, and current readiness verdict.

## 10.1 Scope and files inspected

### Files inspected

- `specs/00-initial-assessment-spec.md`
- `specs/01-data-audit-spec.md`
- `specs/02-data-cleaning-spec.md`
- `specs/03-deterministic-rules-spec.md`
- `specs/reports/01-repository-audit.md`
- `specs/reports/02-data-audit-report.md`
- `specs/reports/03-data-cleaning-planning-log.md`
- `specs/reports/04-deterministic-rules-planning-log.md`
- `data/procurement_policy.md`
- `data/README.md`
- `data/requests.json`
- `data/employees.csv`
- `data/department_budgets.csv`
- `data/software_catalog.csv`
- `data/vendors.csv`
- `data/purchase_history.csv`
- `data/vendor_risk.json`
- `src/contracts.py`
- `src/sample_output.json`
- `evals/public_cases.json`
- `evals/run_public_evals.py`
- `src/data_access.py`
- `src/vendor_client.py`
- `src/solution.py`
- `mock_api/app.py`
- `tests/test_data_integrity.py`
- `requirements.txt`

### Missing or unavailable files

No listed file was missing. The repository contains all of the listed files and data assets.

## 10.2 Source-of-truth hierarchy

1. `data/procurement_policy.md` is the governing policy source.
2. The actual fixtures under `data/` establish the real request, vendor, budget, overlap, and risk facts.
3. The project assessment spec establishes the required architecture and evaluation requirements.
4. This specification translates policy into deterministic behavior.
5. `evals/public_cases.json` is a test harness specification that must reflect actual fixture facts and policy language.

The source hierarchy is strict: the policy and real data override the earlier ambiguous or loose semantics in the draft specification and the initial public-case expectations.

## 10.3 Actual public-case findings

| Case | Request | Verified source facts | Policy sections | Financial approvals | Specialist reviews | Required risk flags | Missing information | Recommendation / next step | Evidence sources |
|---|---|---|---|---|---|---|---|---|---|
| PUB-01 | REQ-1001 | $800 cost, Finance dept, available budget $29,000, SignFlow approved, current review date 2026-06-20 | 1, 2, 4, 5 | Manager | None | none | none | `proceed_to_required_approvals`; Manager approval only | `data/requests.json`, `data/department_budgets.csv`, `data/vendors.csv`, `data/procurement_policy.md` |
| PUB-02 | REQ-1002 | $12,000 cost, Marketing dept, vendor BrandBoard is New, blank review date, draft legal terms, external risk says not_completed | 1, 3, 4, 5, 7 | Department Head, Finance, Procurement | Security, Legal | existing_tool_overlap, security_review_required, legal_review_required | none | `proceed_to_required_approvals`; Security and Legal review are required before approval | `data/requests.json`, `data/vendors.csv`, `data/vendor_risk.json`, `data/software_catalog.csv` |
| PUB-03 | REQ-1003 | $18,000 cost, source_code access, existing CodeMate vendor, approved vendor with current review date 2026-08-20 | 1, 3, 4, 5 | Department Head, Finance, Procurement | Security | existing_tool_overlap, security_review_required | none | `proceed_to_required_approvals`; approved vendor does not override source-code access controls | `data/requests.json`, `data/software_catalog.csv`, `data/vendor_risk.json`, `data/procurement_policy.md` |
| PUB-04 | REQ-1005 | $22,000 cost, Sales dept, available budget $18,000, GrowthForge is new with customer PII and outside-region storage | 1, 2, 4, 5, 6, 7 | Department Head, Finance, Procurement | Security, Privacy, Legal | budget_insufficient, security_review_required, privacy_review_required, legal_review_required | none | `route_for_budget_exception`; budget exception plus Privacy, Security, and Legal review | `data/requests.json`, `data/department_budgets.csv`, `data/vendors.csv`, `data/vendor_risk.json` |
| PUB-05 | REQ-1006 | annual_cost_usd null, user_count null, data_access_level is `unknown`, justification contains prompt-injection instruction | 1, 9 | none determinable | human clarification review | missing_information, prompt_injection_detected | annual_cost_usd, user_count, data_access_level | `request_clarification`; ignore the embedded instruction; request missing facts | `data/requests.json`, `data/procurement_policy.md` |
| PUB-06 | REQ-1009 | $15,000 cost, confidential_documents access, vendor NimbusAI force_error 503, new vendor, blank review date | 1, 4, 5, 7, 10 | Department Head, Finance, Procurement | Security, Legal | vendor_risk_unavailable, security_review_required, legal_review_required | none | `route_for_manual_review`; do not infer a favorable vendor decision | `data/requests.json`, `data/vendor_risk.json`, `mock_api/app.py`, `data/vendors.csv` |

## 10.4 Policy-to-rule traceability

| Rule | Policy section | Evaluation coverage |
|---|---|---|
| Required request data completeness | Section 1 | PUB-05 |
| Budget check and budget_exception | Section 2 | PUB-04 |
| Existing software overlap | Section 3 | PUB-02, PUB-03 |
| Financial approval thresholds | Section 4 | PUB-01, PUB-02, PUB-03, PUB-04, PUB-06 |
| Security review requirements | Section 5 | PUB-02, PUB-03, PUB-04, PUB-06 |
| Security assessment freshness | Section 5 | PUB-02, PUB-04, PUB-06 and vendor-review edge cases |
| Privacy review requirements | Section 6 | PUB-04 |
| Legal review requirements | Section 7 | PUB-02, PUB-04, PUB-06 |
| AI tool restrictions and no automatic approval | Section 8 | PUB-03, PUB-04 |
| Prompt injection handling | Section 9 | PUB-05 |
| Tool and evidence failures | Section 10 | PUB-06 |
| Human authority and no autonomous approval | Section 11 | All cases |

## 10.5 Contract corrections

The contract corrections made were:

1. Canonical approval names were enforced: Manager, Department Head, Procurement, Finance, CFO, Security, Privacy, Legal.
2. Canonical risk flags were enforced: existing_tool_overlap, budget_insufficient, security_review_required, privacy_review_required, legal_review_required, vendor_review_expired, conflicting_vendor_evidence, vendor_risk_unavailable, prompt_injection_detected, missing_information.
3. A `recommendation_code` field was added as an optional machine-readable code to avoid ambiguous free-text output.
4. Validation was tightened so empty strings and blank values are rejected unless explicitly allowed by the contract design.
5. Telemetry now accepts nullable values to prevent fake measured values from appearing in sample output.

## 10.6 Sample-output corrections

The sample output was converted from a generic placeholder into a real, policy-grounded example from `REQ-1001`.

- It is based on actual request data from `REQ-1001`.
- It uses only canonical contract fields and values.
- It does not invent telemetry measurements.
- It has no unsupported risk flags or missing information.
- It correctly states that the request is governed by the Manager-only tier under the policy.

## 10.7 Evaluation corrections

The evaluation file was corrected to remove ambiguous approval-group semantics and replace them with explicit semantics:

- `required_approvals_all_of`
- `required_approvals_one_of_groups`
- `forbidden_approvals`
- `required_risk_flags_all_of`
- `required_risk_flags_one_of_groups`
- `forbidden_risk_flags`
- `required_missing_information_all_of`
- `required_recommendation`
- `required_human_review`
- `required_next_step_properties`

These semantics are unambiguous and align with the actual policy triggers.

## 10.8 Boundary and failure test matrix

| Test ID | Category | Required | Status |
|---|---|---|---|
| FIN-001 | Financial boundary | $1,000 exact | Specified |
| FIN-002 | Financial boundary | $1,000.01 | Specified |
| FIN-003 | Financial boundary | $10,000 exact | Specified |
| FIN-004 | Financial boundary | $10,000.01 | Specified |
| FIN-005 | Financial boundary | $25,000 exact | Specified |
| FIN-006 | Financial boundary | $25,000.01 | Specified |
| BUD-001 | Budget | Cost below budget | Specified |
| BUD-002 | Budget | Cost equal to budget | Specified |
| BUD-003 | Budget | Cost above budget | Specified |
| BUD-004 | Budget | Missing budget record | Specified |
| BUD-005 | Budget | Inconsistent stored and calculated budget | Specified |
| FRESH-001 | Assessment freshness | Within valid period | Specified |
| FRESH-002 | Assessment freshness | Exactly on expiry boundary | Specified |
| FRESH-003 | Assessment freshness | Outside valid period | Specified |
| FRESH-004 | Assessment freshness | Missing review date | Specified |
| FRESH-005 | Assessment freshness | Malformed date | Specified |
| FRESH-006 | Assessment freshness | Future-dated review | Specified |
| MISSING-001 | Missing data | Missing cost | Specified |
| MISSING-002 | Missing data | Missing user_count | Specified |
| MISSING-003 | Missing data | Missing `data_access_level` | Specified |
| FAIL-001 | Tool failure | Record not found | Specified |
| FAIL-002 | Tool failure | Service unavailable | Specified |
| FAIL-003 | Tool failure | Timeout | Specified |
| FAIL-004 | Tool failure | Malformed response | Specified |
| FAIL-005 | Tool failure | Conflicting vendor evidence | Specified |
| INJECT-001 | Prompt injection | Request text injection | Specified |
| INJECT-002 | Prompt injection | Vendor text injection | Specified |
| INJECT-003 | Prompt injection | API response injection | Specified |

No implementation tests were executed because the task specifically prohibits implementing the application or invoking external services.

## 10.9 Unresolved issues and blockers

The following issues remain unresolved or require human decision before implementation begins:

1. The exact fuzzy-matching policy for overlap detection is not defined in the policy text. The implementation must choose a conservative rule and document it in the engineering design.
2. The final output format for conflict resolution between internal vendor registry and vendor-risk service is not mandated beyond “surface the conflict and route to Security/manual review.”
3. The application-level evaluator is not implemented yet; this review only specifies the expected semantics and evaluation contract.
4. The actual Architecture A and Architecture B implementation is intentionally not started in this task.

## 10.10 Files changed and deliberately untouched

### Changed files

- `src/contracts.py`
- `src/sample_output.json`
- `specs/03-deterministic-rules-spec.md`
- `evals/public_cases.json`

### New file created

- `specs/reports/05-preimplementation-review.md`

### Deliberately untouched

- `data/procurement_policy.md`
- `data/requests.json`
- `data/employees.csv`
- `data/department_budgets.csv`
- `data/software_catalog.csv`
- `data/vendors.csv`
- `data/purchase_history.csv`
- `data/vendor_risk.json`
- `src/data_access.py`
- `src/vendor_client.py`
- `src/solution.py`
- `mock_api/app.py`
- `evals/run_public_evals.py`
- `app.py`
- `run_local.py`
- `verify_setup.py`
- `requirements.txt`

## 10.11 Validation performed

### Commands run

```bash
cd /Users/sneharaj/Desktop/FDE_Assessment_3_Starter_Pack && python3 - <<'PY'
import json
from pathlib import Path
root = Path('.')
for rel in ['src/sample_output.json', 'evals/public_cases.json']:
    with open(root / rel, encoding='utf-8') as f:
        json.load(f)
    print(f'{rel}: JSON parse OK')

cases = json.loads((root / 'evals' / 'public_cases.json').read_text(encoding='utf-8'))
ids = [c['case_id'] for c in cases]
print(f'public_cases_count={len(cases)}')
print(f'unique_case_ids={len(ids) == len(set(ids))}')
request_ids = {r['request_id'] for r in json.loads((root / 'data' / 'requests.json').read_text(encoding='utf-8'))}
missing = [c['request_id'] for c in cases if c['request_id'] not in request_ids]
print(f'missing_request_ids={missing}')
PY
```

### Actual output

- `src/sample_output.json: JSON parse OK`
- `evals/public_cases.json: JSON parse OK`
- `public_cases_count=6`
- `unique_case_ids=True`
- `missing_request_ids=[]`

Additional static inspection confirmed:

- `src/contracts.py` uses Pydantic-compatible field validation syntax with the installed environment, and the project dependency version is `pydantic>=2.9,<3`.
- No prohibited data files or application code were edited.

## 10.12 Final readiness decision

`READY FOR IMPLEMENTATION`

Reasoning:

- The policy, fixtures, source data, and public cases have been re-verified against the actual project files.
- The deterministic rules now match the policy and actual vendor/budget facts.
- Approval and risk-flag semantics are canonical and explicit.
- The output contract and sample output are consistent with the field names and canonical values.
- The public evaluation expectations have been corrected to reflect actual source data and policy-driven triggers.

This review does not start Architecture A or Architecture B implementation. It only confirms that the specification is sufficiently precise and grounded in evidence to proceed with implementation work in the next step.
