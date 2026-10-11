# Data Cleaning Planning Log

Date: 2026-10-09

## 1. Objective and scope

This log records the work performed during the data-cleaning planning step under strict Spec-Driven Development (SDD). The objective was to evaluate the read-only data audit findings and decide whether any actual data cleanup was justified before human approval.

Scope:

- review the repository audit and data audit
- read the relevant project policy and dataset notes
- verify the findings in the actual source data
- classify each finding as defect, valid data, intentional test fixture, or unresolved
- write a proposed data-cleaning specification only, without executing changes
- preserve the approval gate before any future row or field edits

## 2. Documentation and datasets inspected

Files reviewed:

- `specs/00-initial-assessment-spec.md`
- `specs/01-data-audit-spec.md`
- `specs/reports/01-repository-audit.md`
- `specs/reports/02-data-audit-report.md`
- `data/procurement_policy.md`
- `data/README.md`
- `data/requests.json`
- `data/vendors.csv`
- `data/vendor_risk.json`
- `data/employees.csv`
- `data/department_budgets.csv`
- `data/software_catalog.csv`
- `data/purchase_history.csv`

The audit reviewed the actual file content directly rather than relying only on prior summaries.

## 3. Commands and scripts executed

The following actions were performed during this step:

1. Read the earlier project specification and data-audit documents using file reads in the workspace.
2. Read the policy and dataset notes from `data/procurement_policy.md` and `data/README.md`.
3. Inspect the actual request, vendor, and budget source files directly.
4. Run a read-only Python inventory script to confirm the relevant CSV and JSON files were present and inspectable.

The actual verification command used was:

```bash
cd /Users/sneharaj/Desktop/FDE_Assessment_3_Starter_Pack && python3 - <<'PY'
import csv, json
from pathlib import Path
root = Path('.')
files = [
  'data/employees.csv',
  'data/department_budgets.csv',
  'data/software_catalog.csv',
  'data/vendors.csv',
  'data/purchase_history.csv',
  'data/requests.json',
  'data/vendor_risk.json',
  'evals/public_cases.json',
  'templates/evaluation_results_template.csv',
  'src/sample_output.json',
]
for rel in files:
    p = root / rel
    if not p.exists():
        print(f'{rel}: NOT FOUND')
        continue
    if p.suffix.lower() == '.csv':
        with p.open(newline='', encoding='utf-8') as f:
            rows = list(csv.DictReader(f))
            fieldnames = list(rows[0].keys()) if rows else []
            print(f'{rel}: INSPECTED (rows={len(rows)}, fields={fieldnames})')
    else:
        obj = json.loads(p.read_text(encoding='utf-8'))
        if isinstance(obj, list):
            print(f'{rel}: INSPECTED (records={len(obj)}, keys={list(obj[0].keys()) if obj else []})')
        elif isinstance(obj, dict):
            print(f'{rel}: INSPECTED (entries={len(obj)}, keys={list(obj.keys())[:10]})')
        else:
            print(f'{rel}: INSPECTED (type={type(obj).__name__})')
PY
```

### Actual result

The command completed successfully and reported each relevant dataset as `INSPECTED`.

No package installation or dependency update was run. No application code or dataset files were modified as part of this step.

## 4. Findings verified and classification decisions

The evidence was reviewed against the project policy and the dataset notes. The verified classifications are:

- `REQ-1006` — intentional test fixture, not a data defect
- `SignalWatch` stale vendor review — intentional test fixture, not a defect
- `BrandBoard` incomplete onboarding — intentional test fixture, not a defect
- `GrowthForge` incomplete onboarding / high-risk vendor — intentional test fixture, not a defect
- `NimbusAI` simulated vendor-risk outage — intentional test fixture, not a defect
- `employees.csv` manager hierarchy — valid data
- `department_budgets.csv` arithmetic — valid data
- `software_catalog.csv` AI overlap and sensitivity records — policy-behaviour validation case, not cleanable defect
- `purchase_history.csv` — valid data
- Request cases with `customer_pii`, `source_code`, or `confidential_documents` data-access values — policy-behaviour validation cases, not defects

## 5. Files created or updated

The following files were created during this planning step:

- `specs/02-data-cleaning-spec.md` — proposed cleaning plan and remediation matrix; planning-only document, not execution permission
- `specs/reports/03-data-cleaning-planning-log.md` — this activity log

No existing source datasets, application files, policy files, or evaluation files were changed.

## 6. Decisions and reasoning

Decision: no data cleaning is currently justified.

Reasoning:

- The project documents explicitly state that vendor information can be stale or conflicting and that requests may contain missing or adversarial text.
- The policy explicitly requires the system to detect stale or missing vendor review data, route conflicts to human review, and ignore prompt-injection instructions.
- The data appears intentionally constructed to validate those behaviors.
- The repository does not present a clear evidence-backed defect that requires data cleanup.

Therefore, the plan remains in the approval gate and no transformations are proposed for execution.

## 7. Assumptions, unresolved questions, and limitations

Assumptions:

- The assessment data is intentionally synthetic and designed to be policy-testing material.
- The stale or inconsistent records are likely test fixtures rather than accidental defects.

Unresolved questions:

- Whether the eventual implementation will correctly classify and surface the stale and adversarial data in ways required by hidden evaluation tests.

Limitations:

- This step intentionally did not run the application or install dependencies.
- This step did not change source data or policy inputs.
- Git-based verification was unavailable because the repository is not a Git checkout in this environment.

## 8. Validation checks performed and actual results

Validation checks executed:

- Read and reviewed all referenced planning and audit files.
- Direct inspection of the actual source datasets.
- Read-only Python inventory script to confirm relevant CSV/JSON files were inspectable.

Actual result:

- All relevant data files were accounted for and inspected.
- The files existed and were readable.
- No changes were made to the source data files or application files.

## 9. Confirmation of source-data and application-file changes

The current status is:

- Source datasets: unchanged
- Policy files: unchanged
- Evaluation cases: unchanged
- Application code: unchanged
- Data-cleaning execution: not performed

This step is limited to planning and documentation only.

## 10. Current approval-gate status

Approval gate remains active.

Current state:

- Audit evidence completed
- Specification written
- Activity log written
- Validation performed
- Execution not approved

## 11. Recommended next step

The recommended next step is a human review of this planning specification. If the review confirms no real defect beyond assessment fixtures, the decision remains: no data cleaning is currently justified.

Only after explicit approval should a separate spec be produced for any future approved transformation, followed by pre-change validation, execution, and post-change validation.
