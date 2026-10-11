# Deterministic Rules Planning Log

Date: 2026-10-09

## 1. Objective and scope

This log records the work done during the deterministic-rules specification step under strict Spec-Driven Development (SDD). The objective was to inspect the policy, data, and current code interfaces, derive the mandatory procurement rules, and define the small set of tool contracts without beginning implementation.

Scope:

- read the existing specs and reports
- read the current policy and data-access sources
- inspect the data contract and mock API interfaces
- map the public evaluation cases to deterministic rules
- draft the rule specification and tool contracts
- document assumptions and unresolved questions
- keep the approval gate active for future implementation

## 2. Files inspected

The following files were read as part of this planning step:

- `specs/00-initial-assessment-spec.md`
- `specs/01-data-audit-spec.md`
- `specs/02-data-cleaning-spec.md`
- `specs/reports/01-repository-audit.md`
- `specs/reports/02-data-audit-report.md`
- `specs/reports/03-data-cleaning-planning-log.md`
- `data/procurement_policy.md`
- `data/README.md`
- `src/contracts.py`
- `src/data_access.py`
- `src/vendor_client.py`
- `src/solution.py`
- `mock_api/app.py`
- `evals/public_cases.json`
- `evals/run_public_evals.py`
- `tests/test_data_integrity.py`
- `src/sample_output.json`

Additional inspection was performed where needed to confirm the actual data schema and the mock vendor-risk API behavior.

## 3. Specifications created or updated

Files created during this planning step:

- `specs/03-deterministic-rules-spec.md` — deterministic rule definitions and tool contracts for the planning stage
- `specs/reports/04-deterministic-rules-planning-log.md` — this activity log

No existing source files, policy files, evaluation cases, or datasets were edited.

## 4. Policy rules extracted and traceability

The following rules were extracted from the policy source and mapped to their governing sections:

- Section 1: required request information and missing-information handling
- Section 2: budget check and available-budget comparison
- Section 3: existing software overlap and use-case review
- Section 4: approval thresholds by annual spend
- Section 5: security-review conditions and stale/missing vendor reviews
- Section 6: privacy review for PII and cross-region risk
- Section 7: legal review for new-vendor or cross-region risk triggers
- Section 8: AI-tool restrictions and no automatic approval by prior purchase
- Section 9: prompt-injection handling and untrusted business content
- Section 10: tool and evidence failure handling
- Section 11: human authority and non-autonomous approval behaviour

These rules were traced back to the actual policy document rather than inferred from the assessment summary.

## 5. Tool contracts proposed and why

The proposed minimal tool set is four tools, which satisfies the assessment requirement for at least three tools and keeps the design small enough for the project stage:

1. `request_lookup_tool` — resolves the request by `request_id` and returns the request payload
2. `budget_tool` — resolves department budget and compares annual cost to available budget
3. `software_tool` — checks overlap against the software catalog and purchase history
4. `vendor_tool` — resolves internal vendor status and external vendor-risk evidence, including conflicts and outage conditions

This matches the existing repository code shape:

- `src/data_access.py` exposes deterministic data loading functions
- `src/vendor_client.py` defines the external vendor-risk lookup client
- `src/contracts.py` defines the decision contract
- `mock_api/app.py` exposes the vendor-risk API contract for unavailable, failed, and stale-vendor scenarios

The design preserves the smallest sufficient set of deterministic and external tools while avoiding speculative complexity.

## 6. Assumptions and unresolved questions

Assumptions:

- the data is intentionally synthetic and includes stale, conflicting, or adversarial cases by design
- the public evaluation harness expects policy and risk logic to be derived from those fixtures without modifying the underlying source data

Unresolved questions that remain design-level and should be flagged for future review:

- how best to encode overlap detection without over-merging fuzzy names or categories
- how to present conflicting internal and external vendor evidence in a minimal but traceable output format
- how to treat `unknown` or partially unspecified `data_access_level` values when they are material to security review

These questions are documented and not resolved through invented rules.

## 7. Commands and validation checks executed

The following command was used during the planning validation stage to verify that the required documents are present and that source files still exist unchanged:

```bash
cd /Users/sneharaj/Desktop/FDE_Assessment_3_Starter_Pack && printf '\n=== Spec files ===\n' && ls -l specs && printf '\n=== Report files ===\n' && ls -l specs/reports && printf '\n=== Validation summary ===\n' && python3 - <<'PY'
from pathlib import Path
required = [
    Path('specs/02-data-cleaning-spec.md'),
    Path('specs/reports/03-data-cleaning-planning-log.md'),
]
for p in required:
    print(f'{p}: EXISTS={p.exists()} SIZE={p.stat().st_size if p.exists() else 0}')
PY
printf '\n=== Unchanged-file check ===\n' && python3 - <<'PY'
from pathlib import Path
check = [
    Path('data/requests.json'),
    Path('data/vendors.csv'),
    Path('data/vendor_risk.json'),
    Path('data/employees.csv'),
    Path('data/department_budgets.csv'),
    Path('data/software_catalog.csv'),
    Path('data/purchase_history.csv'),
    Path('data/procurement_policy.md'),
    Path('evals/public_cases.json'),
    Path('src/solution.py'),
]
for p in check:
    print(f'{p}: EXISTS={p.exists()} SIZE={p.stat().st_size if p.exists() else 0}')
PY
printf '\n=== Git status ===\n' && git status --short --untracked-files=all || true
```

### Actual results

- The planning documents and earlier report files exist.
- The checked source files all exist and remained at their original sizes.
- No application code, dataset, policy, or evaluation-case file was modified in this step.
- Git-based validation was unavailable because the workspace is not a Git repository.

## 8. Completion and approval status

Completed actions:

- reviewed existing specs and reports
- reviewed project policy and dataset notes
- inspected the current code interfaces and mock API contract
- mapped the public evaluation cases to deterministic rules and expected escalations
- drafted the rule specification and tool contracts
- created the activity log

Proposed future actions (not executed):

- implementation of the procurement workflow
- implementation of the tool contracts in code
- creation of the actual architecture-specific implementation
- execution of any public evaluations or tests beyond the read-only validation already performed

Approval gate:

- active
- does not authorize implementation or data changes

Recommended next step:

- human review of the deterministic-rules specification
- approval before moving into the implementation specification or code execution phase
