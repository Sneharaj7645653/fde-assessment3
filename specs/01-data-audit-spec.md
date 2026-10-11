# Data Audit Specification

## 1. Purpose

This specification defines the required read-only data audit for the AI Procurement Request Copilot starter pack. The purpose is to inspect the repository’s datasets, identify quality issues that could affect procurement decisions or evaluation outcomes, and document findings with evidence without changing any data, code, or configuration.

This audit is a separate step from implementation. It is intentionally limited to inspection and reporting.

## 2. Scope

The audit covers all relevant CSV and JSON data files in the repository, including files under nested directories when present. The primary scope is the project’s business datasets and evaluation data, not the application code.

### In-scope files

The audit must inspect all relevant repository data assets, including at minimum:

- `data/employees.csv`
- `data/department_budgets.csv`
- `data/software_catalog.csv`
- `data/vendors.csv`
- `data/purchase_history.csv`
- `data/requests.json`
- `data/vendor_risk.json`
- `evals/public_cases.json`
- `templates/evaluation_results_template.csv`
- `src/sample_output.json`

If additional CSV or JSON files are present in the repository or subdirectories, they must also be checked if they are data-bearing, evaluation-bearing, or schema-bearing files.

### Out of scope for this audit

- modifying any dataset or file
- cleaning, transforming, overwriting, renaming, or deleting data
- changing application logic
- installing or upgrading Python packages
- editing evaluation cases or policy files
- using the application to generate or mutate data

## 3. Audit method

The audit must be completed using read-only inspection.

### Required approach

1. Enumerate all CSV and JSON files under the repository that are relevant to data, evaluation, or contract schema.
2. Record the file path, format, apparent purpose, and row or record count.
3. Inspect each dataset for schema and content issues without altering it.
4. Classify each issue using the categories below.
5. Capture evidence from the actual file content, including affected record IDs, rows, or field values when practical.
6. Distinguish defects from intentional edge cases and test fixtures.
7. Document cross-dataset relationships and integrity findings.
8. Produce a final read-only assessment of data readiness.

### Inspected dataset characteristics

For each dataset, the audit must record, at minimum:

- path
- file type (CSV or JSON)
- row or record count
- column names / keys
- apparent purpose or usage
- sample or representative record details when useful

## 4. Required checks

Each relevant dataset must be reviewed for the following issues.

### 4.1 Missing or null values

Check for empty strings, null values, missing columns, and absent required fields.

Examples:

- vendor security review date missing
- request cost or user count missing
- null values in mandatory fields

### 4.2 Duplicate rows and duplicate identifiers

Check for duplicate rows and repeated values in primary keys or business identifiers.

Examples:

- duplicate `employee_id` values
- duplicate `request_id` values
- duplicate `vendor_id` values
- repeated vendor names or product names where repeated values may be valid or intentional

### 4.3 Inconsistent data types, formats, casing, whitespace, and categorical values

Check for values that violate expected representation or normalization.

Examples:

- inconsistent `status` values (`Approved`, `approved`, `Approved - limited use`)
- inconsistent casing or trailing whitespace in vendor names or departments
- numeric fields stored as strings in CSVs and numbers in JSON
- dates stored in multiple formats or with unusual formatting

### 4.4 Invalid values and violated constraints

Check for data that violates known business or schema rules.

Examples:

- negative or zero values in cost or user counts where the domain expects positive values
- dates after the evaluation reference date when the file is meant to be historical
- invalid vendor or department names relative to the reference tables

### 4.5 Conflicting records across related datasets

Compare tables and JSON records that correspond to the same entities.

Examples:

- vendor registry status differs from vendor-risk API status
- vendor risk status says `expired` or `not_completed` while vendor registry says `Approved`
- purchase history and current software catalog disagree on a product or vendor relationship

### 4.6 Expired or potentially outdated information

Use the policy reference date defined by the project (`2026-09-30`) when evaluating freshness.

Examples:

- vendor review date older than the allowed window
- stale security review records
- outdated risk data that may still be intentionally included to test detection logic

### 4.7 Referential-integrity issues

Check that foreign keys and references resolve to existing records where expected.

Examples:

- request `requester_id` missing from employees
- request `vendor_name` missing from vendors
- vendor or product references absent from the vendor registry or catalog
- `manager_id` values not found in the employee table

### 4.8 Schema inconsistencies and unexpected columns

Check for missing or extra fields, inconsistent field names, or unexpected JSON keys.

Examples:

- missing expected columns in a CSV
- unexpected top-level entries in JSON data
- records with different field sets from the rest of the dataset

### 4.9 Potential data-quality issues affecting procurement decisions or evaluation results

Flag any data quality issue that could materially affect decision-making or evaluation outcomes.

Examples:

- intentionally adversarial text in request justifications
- missing required request details that could block approval workflows
- vendor-risk API outage simulation entries
- naturally occurring conflicting or stale business records that require human review

## 5. Intentional edge cases and test fixtures

The audit must not automatically classify every anomaly as a defect.

The following conditions may be deliberate assessment fixtures and should be analyzed before being labeled as bad data:

- conflicting or stale vendor information used to test vendor-risk detection logic
- missing business fields in a request to test missing-information handling
- a vendor-risk service response that simulates an outage or forced error
- one-off adversarial request text meant to test prompt-injection or untrusted content handling

If the repository documentation or file content indicates that the issue is intentionally included for assessment testing, it should be classified as `intentional test case` rather than `confirmed defect`.

## 6. Reporting requirements

The audit report must include, for each relevant file and issue:

- dataset inventory: path, format, row count, columns or keys, and apparent purpose
- findings by dataset and issue category
- evidence for each finding, including affected rows or record identifiers where practical
- severity: `critical`, `high`, `medium`, or `low`
- classification: `confirmed defect`, `suspected issue`, `intentional test case`, or `needs investigation`
- recommended remediation without applying it
- cross-dataset relationships and integrity findings
- overall data-readiness assessment
- uncertainties and limitations

## 7. Evidence and severity guidance

Findings must be based on direct inspection of the data, not assumptions.

Minimum evidence should include one of the following:

- affected row number
- affected record ID
- affected vendor or employee ID
- exact file and field names
- an excerpt from the relevant record or JSON payload

Severity should reflect the likely impact on procurement decisions or evaluation correctness.

Examples:

- `critical`: invalid reference chain, missing core appraisal data for a request, vendor-risk outage as a service-level test case with direct business impact
- `high`: stale or expired review records with material risk implications
- `medium`: inconsistent status formatting, missing optional metadata, duplicated non-key values that are not harmful
- `low`: cosmetic whitespace or casing inconsistencies that do not alter logic

## 8. Acceptance criteria

The audit is complete only when all of the following are true:

1. Every relevant CSV and JSON dataset has been inspected or explicitly recorded as not inspectable.
2. The inventory includes path, format, row or record count, and purpose for each relevant file.
3. Each issue is backed by file evidence and, where practical, records or identifiers.
4. Issues are classified as `confirmed defect`, `suspected issue`, `intentional test case`, or `needs investigation`.
5. Cross-dataset integrity findings are documented.
6. No data files were changed, rewritten, or cleaned during the audit.
7. The final report distinguishes intentional assessment fixtures from actual defects.
8. The final assessment clearly states whether the data is ready for the next stage or requires a separate data-cleaning specification.

## 9. Expected output

The audit must create a report at:

- `specs/reports/02-data-audit-report.md`

This report must be generated after the specification is written and before any data-cleaning or implementation decision is made.

## 10. Required discipline

This is a spec-first, evidence-first, no-cleanup step. The audit must not silently skip issues, must not assume anomalies are defects, and must not perform modifications. The next stage, if warranted, is a separate data-cleaning specification created only after the audit is reviewed and approved by a human.
