# Deterministic Procurement Rules Specification

## 1. Authority and policy classifications

### 1.1 Source hierarchy

1. `data/procurement_policy.md` controls procurement requirements.
2. Actual records under `data/` control request, employee, budget, catalog, purchase, vendor, and risk-service facts.
3. `specs/00-initial-assessment-spec.md` controls assessment deliverables, architecture requirements, and common evaluation requirements.
4. This document translates policy requirements into deterministic application behavior.
5. `evals/public_cases.json` tests those rules and must not add policy.

### 1.2 Requirement labels

- **Policy-mandated:** explicitly required by `data/procurement_policy.md`.
- **Assessment-mandated:** required by the assessment specification, not policy.
- **Application-level:** needed to operate the supplied application/data interfaces; not itself a procurement approval rule.
- **Implementation choice:** a deterministic choice made to resolve an underspecified engineering detail; it must be visible and reversible.
- **Unresolved policy question:** requires policy-owner direction; no favorable assumption is allowed meanwhile.

### 1.3 Sources and fixed conventions

- Request facts: `data/requests.json` (**Assessment data**).
- Requester/department mapping: `data/employees.csv` (**Assessment data**).
- Budget values: `data/department_budgets.csv`; its guide defines `available = annual - committed` (**Assessment data**).
- Existing products and seats: `data/software_catalog.csv`; prior transactions: `data/purchase_history.csv` (**Assessment data**).
- Internal vendor facts: `data/vendors.csv`; external risk evidence: mock vendor-risk API backed by `data/vendor_risk.json` (**Assessment data**).
- Policy: `data/procurement_policy.md` (**Policy-mandated**).
- Snapshot date: `2026-09-30` (**Policy and data-guide fact**).
- Money: USD, parsed as exact decimal amounts and compared in integer cents; never binary float equality (**Implementation choice**).

### 1.4 Evidence and uncertainty

**Policy-mandated:** do not invent missing facts; do not infer favorable status from unavailable required evidence; preserve conflicting vendor findings and route them to Security/manual review. An `EvidenceItem` reference identifies the actual source record, policy section, or endpoint. `evidence_status` distinguishes `verified`, `missing`, `expired`, `unknown`, `unavailable`, and `conflicting`; it does not replace the factual finding.

## 2. Input contract

An empty value is not the same as an explicitly empty collection. `null`, absent keys, blanks, and sentinel values such as `unknown` remain distinct until validated.

| Field | Source and meaning | Required status | Validation and missing/invalid behavior | Estimate permitted? |
|---|---|---|---|---|
| `request_id` | `requests.json`; record selector | Application-level required | Non-empty and must resolve; unknown ID is controlled input error | No |
| `requester_id` | `requests.json`; resolve in `employees.csv` | Policy-mandated requester, app key | Missing/blank/unresolved blocks review; do not infer identity | No |
| Department | Derived only by joining requester to `employees.csv` | Policy-mandated | Missing/unresolved employee department blocks budget and routing checks | No |
| `product_name` and `vendor_name` | `requests.json`; product/vendor being requested | Policy-mandated (product/vendor information) | Require enough information to identify product/vendor; distinguish missing request value from a missing registry record | No |
| `annual_cost_usd` | `requests.json`; annualized cost | Policy-mandated | Exact non-negative decimal. Null/absent/blank or malformed means no tier and clarification. Negative is invalid and clarification-required. Zero follows the literal up-to-$1,000 tier; do not invent a free-purchase exception | A reasonable annual estimate is permitted only with a traceable source and explicit `estimated` label |
| `user_count` | `requests.json`; users/licenses | Policy-mandated | Must be a positive integer when applicable. Missing/unknown/invalid means clarification; never invent a count | No estimate rule specified by policy; do not estimate without documented requester evidence |
| `business_justification` | `requests.json`; business purpose | Policy-mandated | Must state a comprehensible business purpose. Present-but-inadequate content is missing information. “Need AI ASAP” is inadequate | No |
| `data_access_level` | `requests.json`; intended data access | Policy-mandated | Absent/null/blank/`unknown` means unknown scope and clarification; do not infer data class from vendor identity | No |
| `requested_integrations` | `requests.json`; required integrations | Policy-mandated when applicable | Absent/null means unknown; explicit `[]` means requester says no integrations; non-empty entries are checked for production/cloud access | No |
| `category` | `requests.json`; catalog comparison hint | Application-level optional | Missing category limits category matching; it is not a policy failure by itself | No |
| `urgency` | `requests.json`; workflow context | Application-level optional | Never changes thresholds, approvals, or evidence requirements | No |

A reasonable annual estimate is valid only when its amount, currency, annualization basis, source, and estimator are recorded. This is an **Implementation choice** that operationalizes the policy’s phrase “reasonable annual estimate”; if these cannot be recorded, request clarification. An estimate is used for budget and threshold calculations only when explicitly identified as an estimate. No other field may be inferred from an estimate.

## 3. Deterministic rule catalogue

### R-001 — Required information and clarification
- Classification/source: **Policy-mandated**, Section 1.
- Trigger: requester/department, product/vendor, annual cost or valid estimate, user/license count, business purpose, data-access level, or applicable integrations absent, invalid, unknown, or inadequate.
- Sources: request, employee record, and the source relevant to each field.
- Calculation: validate each material field independently; `[]` integrations is explicitly none, while absent/null is unknown.
- Outcome: record canonical missing field identifiers; do not apply an approval tier where cost is unresolved; request clarification. `human_review_required=true`.
- Risk: `missing_information`.
- Positive test: REQ-1006; negative test: complete REQ-1001.
- Conflict/failure: keep original value and exact source; do not fill it from another unrelated record.

### R-002 — Budget sufficiency and source consistency
- Classification/source: **Policy-mandated**, Section 2; arithmetic inputs and formula also documented in `data/README.md`.
- Trigger: valid annual cost and a consistent, complete department budget row.
- Calculation: parse annual budget, committed amount, stored available amount, and request cost as exact USD decimals. Calculate `derived_available = annual_budget - committed`. Compare derived and stored available exactly to cents; compare request cost with the stored available only when the row is complete and consistent.
- Outcome: if cost `>` available, add `budget_insufficient`, record cost/available evidence, and route to Finance/budget-exception review. Do not automatically reject. If cost `<=` available, continue review; this is not approval.
- Missing committed amount, missing stored available amount, missing row, malformed number, negative budget component, or mismatch: preserve source values, do not substitute a fabricated value or report a positive budget result; add `budget_data_unverified`, state the exact unavailable/inconsistent field, and route to Finance/manual review. If stored available is absent but annual and committed are valid, show the derived arithmetic only as derived evidence; do not treat the missing stored amount as verified budget authority.
- Tests: cost below/equal/above available; each missing component; malformed/negative component; stored/calculated mismatch. Positive fixture: REQ-1005; negative fixture: REQ-1001.

### R-003 — Financial approval tier
- Classification/source: **Policy-mandated**, Section 4.
- Exact tier calculation using integer cents:
  - `$0.00` through `$1,000.00`: `Manager`.
  - `$1,000.01` through `$10,000.00`: `Department Head`, `Procurement`.
  - `$10,000.01` through `$25,000.00`: `Department Head`, `Finance`, `Procurement`.
  - Above `$25,000.00`: `Department Head`, `Finance`, `CFO`, `Procurement`.
- Missing/unknown/malformed/negative cost: no financial tier; clarification, not a guessed approval.
- Specialist reviews and Finance budget-exception review are additive; duplicate role names appear once.
- Boundary tests: $999.99, $1,000.00, $1,000.01; $9,999.99, $10,000.00, $10,000.01; $24,999.99, $25,000.00, $25,000.01. Also test zero, negative, malformed, missing, and sourced estimate.

### R-004 — Existing-product and functional-overlap review
- Classification/source: **Policy-mandated**, Section 3.
- Trigger: same product/vendor, same category, or a product reasonably able to satisfy the stated use case.
- Sources: catalog, purchase history, request scope, seats, and business justification.
- Outcome: surface each evidence-backed match. `existing_tool_overlap` means a relevant existing-product match/potential overlap, **not** a finding that the request is redundant. Only assert a confirmed functional duplicate when scope/use case and unused capacity support that conclusion. Record a credible gap/exception reason; exact duplicates or unused capacity receive human review before a new purchase.
- Broad category alone is insufficient to assert functional equivalence. A same vendor/product match is sufficient to surface an existing-product match, but not to reject.
- Tests: REQ-1001 SignFlow add-on, REQ-1002 creative alternatives, REQ-1003 CodeMate expansion, and a no-match request.

### R-005 — Security review
- Classification/source: **Policy-mandated**, Section 5.
- Trigger: source code; production or cloud-account integration; confidential documents; employee/customer PII; credentials/secrets; or missing, expired, or not-completed vendor assessment.
- Outcome: `security_review_required` and `Security` approval; additive to financial approvals. Approved vendor status never waives use-case checks.
- Evidence: request access/integrations plus assessment status and source. Tests: REQ-1002, REQ-1003, REQ-1005, REQ-1009; REQ-1001 is a negative specialist-review case.

### R-006 — Assessment freshness and status
- Classification/source: 365-day period is **Policy-mandated**, Section 5; the boundary convention below is an **Implementation choice / explicit policy interpretation**, not quoted policy fact.
- Reference date: `2026-09-30`. Compute calendar-day age as `reference_date - review_date`.
- Selected interpretation: age `0..365` inclusive is current; age `>365` is expired. Thus 2025-09-30 (365 days) is current, 2025-09-29 (366 days) is expired, and 2025-10-01 (364 days) is current. Record this interpretation for policy-owner confirmation before production use.
- Status representation: current=`verified`; stale=`expired` plus `vendor_review_expired`; absent assessment/date=`missing`; unknown/malformed/future or contradictory assessment status/date=`unknown`; failed lookup=`unavailable`. Missing/unknown/unavailable are never called expired.
- Missing, unknown, or unavailable material security assessment triggers `security_review_required` and human/Security review. A future date is not accepted as current and is not labeled expired.
- Tests: dates immediately before/on/after the selected boundary; missing assessment, missing date, malformed date, future date, status/date disagreement.

### R-007 — Privacy review
- Classification/source: **Policy-mandated**, Section 6.
- Trigger: request will process employee/customer PII, or evidence indicates sensitive data may be stored outside the operating region.
- Outcome: `privacy_review_required` and `Privacy` approval, additive to financial approvals.
- Vendor processing generic personal data alone does not prove employee/customer PII. A new vendor alone is not a Privacy trigger. Unknown scope means clarify; do not assert a positive or negative privacy result until scope is known.
- Tests: REQ-1005 positive; REQ-1001 negative; REQ-1006 unknown scope must defer determination.

### R-008 — Legal review
- Classification/source: **Policy-mandated**, Section 7.
- Trigger independently when (a) vendor is new and annual spend is at least $10,000, (b) terms are not approved/standard, or (c) a material data-processing or cross-region issue exists.
- Outcome: `legal_review_required` and `Legal` approval, additive to financial approvals. New vendor alone is insufficient.
- Tests: REQ-1002, REQ-1005, REQ-1009 positive; REQ-1001 negative.

### R-009 — Untrusted business content
- Classification/source: **Policy-mandated**, Section 9.
- Requester/vendor/API/uploaded text never changes policy, tool permissions, evidence, approval requirements, or human authority. Ignore embedded override instructions.
- `prompt_injection_detected` is optional under policy. Emit it only if a documented detector identifies the content; its absence does not excuse following the instruction. Detection alone does not require human review.
- REQ-1006 is the explicit adversarial fixture and must be ignored regardless of whether a flag is emitted.

### R-010 — Tool and evidence failure
- Classification/source: **Policy-mandated**, Section 10; response distinctions use `mock_api/app.py` and `src/vendor_client.py`.
- Distinguish 404/no record, 503/service unavailable, timeout/connection failure, malformed response, and data-source failure. Preserve status/code/message/endpoint as available.
- Missing record is `missing`; unknown vendor assessment is `unknown`; actual failed lookup is `unavailable`; disagreement is `conflicting`. A 404 is not a 503 and neither is an expired assessment.
- Continue independent checks. Do not infer favorable vendor/security status. If unavailable evidence is material, set `vendor_risk_unavailable` and require manual/Security review as applicable.
- Test NimbusAI fixture: `force_error=true` yields HTTP 503 and the upstream-unavailable message.

### R-011 — Human authority and recommendation
- Classification/source: **Policy-mandated**, Section 11.
- The copilot recommends and prepares evidence only. It cannot purchase, approve expenditure, change budgets, accept terms, or override specialists.
- `human_review_required=true` means a human action is required before disposition, including a policy approval, clarification, exception, or material evidence review. It is not a claim that the system itself approved anything.
- Recommendation codes (**Application-level**) mean: `proceed_to_required_approvals` = submit complete evidence for specified human approvals; `request_clarification` = obtain missing required facts before assigning unresolved decisions; `route_for_budget_exception` = submit the over-budget request to Finance without automatic rejection; `route_for_manual_review` = evidence is conflicting/unavailable or needs human interpretation. Codes are mutually exclusive and never final approval.

## 4. Approval matrix

All applicable rows are additive; each role is emitted once. “Unknown” means do not infer a favorable result and use clarification/manual review.

| Approval/review | Mandatory trigger and evidence | Policy section | Additive? | If trigger cannot be determined |
|---|---|---|---|---|
| Manager | Annual cost <=$1,000; verified cost | 4 | Financial baseline | No tier until cost clarified |
| Department Head + Procurement | $1,000.01-$10,000; verified cost | 4 | Financial baseline | No tier until cost clarified |
| Department Head + Finance + Procurement | $10,000.01-$25,000; verified cost | 4 | Financial baseline | No tier until cost clarified |
| Department Head + Finance + CFO + Procurement | >$25,000; verified cost | 4 | Financial baseline | No tier until cost clarified |
| Finance/budget exception | Request cost exceeds verified department available budget | 2 | Yes; deduplicate Finance if already in tier | Incomplete/inconsistent budget => Finance/manual review, but do not assert an overrun |
| Security | Any R-005 condition; request/integration or assessment evidence | 5 | Yes | Clarify scope or route to Security; no favorable security inference |
| Privacy | Employee/customer PII or sensitive outside-region storage | 6 | Yes | Clarify scope; do not infer from vendor-new status |
| Legal | Any R-008 condition; vendor, spend, terms, or material data-processing evidence | 7 | Yes | Clarify the trigger; new-vendor status alone does not suffice |
| Security/manual conflict review | Registry and vendor-risk evidence disagree | 5 | Yes | Preserve both sources and route to human/Security review |
| Manual evidence review | Required material source/service unavailable or malformed | 10 | Yes; plus independently triggered specialist reviews | Preserve exact failure and state what remains unverified |
| Clarification | Any material R-001 field absent/invalid/unknown/inadequate | 1 | Yes; no tier for unknown cost | Ask for the exact missing field; do not fabricate |

## 5. Budget and date boundary tests

### 5.1 Budget source handling

- Stored available amount is the comparison value only when annual budget, committed spend, and stored available are all valid and consistent with the documented formula.
- Missing committed: cannot derive available; preserve annual and stored available values, mark `budget_data_unverified`, and route Finance/manual review. Do not assume the stored amount is correct.
- Missing stored available: compute a clearly labeled derived amount for evidence if annual and committed are valid, but do not treat it as verified authority; route for review.
- Missing row, invalid numeric, negative component, or arithmetic mismatch: no positive budget determination; preserve every supplied source value and route for review.
- Valid cost greater than valid available: `budget_insufficient`; Finance exception review. No automatic rejection.
- Valid cost equal to or below available: continue review; no approval inference.

### 5.2 Date boundary matrix

| Review date | Age on 2026-09-30 | Selected interpretation | Status/flag |
|---|---:|---|---|
| 2025-10-01 | 364 days | Current | `verified` |
| 2025-09-30 | 365 days | Current, inclusive boundary | `verified` |
| 2025-09-29 | 366 days | Expired | `expired`, `vendor_review_expired` |
| Missing/null | N/A | Missing | `missing`; Security review, not expired flag |
| Malformed/future/conflicting | Undefined | Unknown | `unknown`; Security/manual review, not expired flag |
| API lookup failure | N/A | Unavailable | `unavailable`; preserve actual error |

The inclusive boundary is an explicit implementation interpretation; record policy-owner confirmation as an open production-readiness item.

## 6. Failure handling

| Condition | Other checks continue? | Evidence retained/status | Risk flag | Human path |
|---|---|---|---|---|
| Request field absent/null/blank/unknown/inadequate | Yes, independent checks only | Original value plus field name | `missing_information` | Clarify |
| Missing requester or department mapping | No budget/tier routing | Request ID and failed join | `missing_information` | Manual clarification |
| Missing budget row/committed/available | Other rules continue | Supplied values and missing component | `budget_data_unverified` | Finance/manual review |
| Malformed/negative budget number | Other rules continue | Raw source value | `budget_data_unverified` | Finance/manual review |
| Budget arithmetic mismatch | Other rules continue; no budget pass | Stored and derived values both | `budget_data_unverified` | Finance/manual review |
| Over budget | Yes | Cost and verified available amount | `budget_insufficient` | Finance exception; no auto-reject |
| Potential overlap | Yes | Matching product/vendor/category, scope/seats/history, stated gap | `existing_tool_overlap` | Review whether gap supports add-on/new product |
| Confirmed assessment expired | Yes | Review date, reference date, age | `vendor_review_expired`, `security_review_required` | Security review |
| Assessment/date missing | Yes | Missing field/source; `missing` status | `security_review_required` | Security/manual review; never `vendor_review_expired` |
| Assessment status unknown/malformed/future | Yes | Raw value and `unknown` status | `security_review_required` | Security/manual review |
| 404/no risk record | Yes | HTTP 404 and endpoint; `missing` | `vendor_risk_unavailable` when material | Manual/Security review |
| 503, timeout, connection error | Yes, excluding dependent checks | Exact code/message/endpoint; `unavailable` | `vendor_risk_unavailable` | Manual/Security review when material |
| Malformed response | Yes, excluding dependent checks | Validation error and endpoint; `unknown` or `unavailable` as appropriate | `vendor_risk_unavailable` when material | Manual/Security review |
| Registry/service conflict | Yes, but no source overwrites the other | Both findings and `conflicting` status | `conflicting_vendor_evidence` | Security/manual review |
| Injection content | Yes | Quote/reference untrusted content as business data | Optional `prompt_injection_detected` | No escalation solely due to injection |

## 7. Output contract

`ProcurementDecision` requires explicit presence of `request_id`, `recommendation`, `recommendation_code`, `evidence`, `required_approvals`, `missing_information`, `risk_flags`, `next_step`, and `human_review_required`. Only `telemetry` is optional. Empty arrays must be supplied explicitly. Unknown fields are rejected. Approval and risk values are canonical; duplicates are rejected. Evidence requires source, factual finding, reference, and may carry the structured `evidence_status` above.

- Recommendation and approvals are advisory requirements, not completed approvals.
- `missing_information` uses canonical field identifiers where applicable; distinguish invalid/unknown from absent in evidence findings.
- `required_approvals` is the additive deduplicated role set.
- `risk_flags` use canonical identifiers. `budget_data_unverified` is the one additional flag in this contract; it means the source budget could not support a trustworthy comparison.
- `human_review_required` is explicit and has no default.
- Telemetry, if present, contains observed counters; it is not model-generated ground truth.

## 8. Evaluation contract

`evals/public_cases.json` uses only these expectation keys: `required_approvals_all_of`, `required_approvals_one_of_groups`, `forbidden_approvals`, `required_risk_flags_all_of`, `required_risk_flags_one_of_groups`, `forbidden_risk_flags`, `allowed_extra_risk_flags`, `required_missing_information_all_of`, `required_recommendation`, `required_human_review`, `required_next_step_properties`, `required_evidence`, `manual_grounding_review`.

- `all_of`: every listed canonical item must be present.
- Each non-empty `one_of_groups` group requires at least one member. Empty group objects are invalid.
- Forbidden values must be absent. Required/forbidden overlap invalidates case schema.
- Actual approvals must be exactly the required set when there are no alternatives; with alternatives, any extra outside the required set and union of declared choices fails. Every unsupported extra is a failed case, not harmless padding.
- Actual risk flags must be a subset of required flags, alternatives, and explicitly `allowed_extra_risk_flags`; other flags fail. PUB-05 permits optional `prompt_injection_detected` without requiring it.
- Missing information is compared as a normalized exact set. Normalization trims/collapses whitespace and case-folds. Documented exact aliases map cost/price to `annual_cost_usd`; seats/licenses to `user_count`; data-access wording to `data_access_level`; purpose/justification to `business_justification`. Unknown values are not dropped.
- Approval normalization is case-insensitive for canonical spellings; `dept head` and `department-head` are the only aliases. Risk normalization accepts canonical spellings case-insensitively plus legacy `overlap`, `budget`, `security`, `privacy`, `legal`, `unavailable`, `tool failure`, `api`, `missing`, `prompt injection`, and `untrusted`. These aliases are evaluator-only; the Pydantic output contract requires canonical values.
- Recommendation code and `human_review_required` are exact comparisons.
- Every `required_next_step_properties` phrase must occur in the next-step string after whitespace normalization/case-folding. These are literal phrase checks, not semantic proof.
- Each `required_evidence` item must match an output evidence item by normalized source, exact normalized reference, optional evidence status, and every `finding_contains_all` fragment. Evidence item count alone never passes grounding.
- Automated evidence checks establish trace linkage and required text only. They cannot prove a finding is true or that all additional findings are supported. A human reviewer must record `case_id`, `reviewer`, non-empty `notes`, a Boolean `checklist_results` entry for every exact checklist item, and `status` (`pass` only when all items are true; otherwise `fail`) in a grounding-review JSON file. Only then can an otherwise passing case be final `PASS`. Missing review means `PENDING_GROUNDING_REVIEW`; missing checklist answers or status disagreement fail review validation.
- `run_public_evals.py --validate-only` validates the complete case schema and request references without importing or invoking application code. Unknown/missing fields fail loudly.

## 9. Shared architecture-comparison measurement contract

The same six cases, order, environment, data snapshot, policy, model/provider settings, tools, retry policy, and contract are used for both architectures. Run cases sequentially with cache state controlled and recorded; do not compare unlike warm/cold runs. No numerical performance threshold is implied.

- End-to-end latency: monotonic wall time from immediately before `handle_request` to after contract validation. Includes model/tool work and retries; excludes case loading, manual review, CSV writing, and evaluator scoring. Record failures/timeouts too.
- LLM calls: every outbound model-request attempt observed at the shared provider transport boundary. Retries are additional attempts and are included in `llm_calls`; `llm_retries` counts attempts beyond the first for a logical request. Failed attempts are included in total calls.
- Tool calls: every tool-dispatch attempt observed at the shared dispatcher boundary, including retried dispatches. `tool_retries` counts attempts beyond the first per logical tool operation. A tool's nested HTTP retries must also be instrumented and identified consistently, not silently hidden.
- Failed calls: failed LLM/tool attempts. Timeouts are a subset of failures; non-timeout tool/API errors are separately counted. Record HTTP status/error class and endpoint/tool name without secrets.
- Evaluation pass rate: final `PASS` cases divided by six, with pending grounding reviews reported separately and not counted as passes. Include automated failure details, reviewer status, and per-case results.
- Ground truth: runner-measured latency and shared transport/dispatcher instrumentation are authoritative. `ProcurementDecision.telemetry` is descriptive only and never substitutes for observed counts.
- Implementation status: current starter interfaces do not yet provide the shared instrumentation hooks. The implementation specification must wire both architectures to the same collector and confirm all counters reconcile before reporting call-count comparisons. Until then, call metrics remain unavailable, not zero.

## 10. Required test design

All tests below are specified, not executed as application tests in this specification phase.

| ID | Condition | Expected result |
|---|---|---|
| FIN-01..09 | Immediately below, exactly at, immediately above $1k/$10k/$25k | Exact policy tier in R-003; no boundary gaps |
| FIN-10..13 | Zero, negative, malformed, missing cost | Zero follows literal tier; invalid/missing has no tier and requires clarification |
| FIN-14 | Evidence-backed reasonable annual estimate | Explicit estimated evidence and deterministic tier; unsupported estimate rejected for clarification |
| BUD-01..03 | Cost below/equal/above available | Continue / continue / `budget_insufficient` and Finance exception |
| BUD-04..09 | Missing budget row, committed, available; invalid/negative numbers; arithmetic mismatch | Preserve values, `budget_data_unverified`, no inferred budget pass |
| DATE-01..07 | 364/365/366-day boundary; missing assessment/date; malformed/future date; contradictory status/date | Status per R-006; missing/unknown never labeled expired |
| INPUT-01..09 | Each required field absent, null, blank, unknown, invalid, inadequate; explicit empty vs absent integrations | Exact missing item and clarification; no invented fact |
| TOOL-01..06 | 404, 503, timeout, connection error, malformed response, conflicting data | Preserve specific failure/evidence status; no favorable inference |
| INJECT-01..03 | Injection in request, vendor text, API response | Instruction ignored; policy and approvals unchanged; flag remains optional |
| CONTRACT-01..07 | Missing mandatory field, unknown approval/flag, duplicate approvals/flags, negative counters, invalid telemetry relations, extra field | Contract validation rejects |
| EVAL-01..06 | Missing expectation, unsupported key, empty alternative group, duplicate IDs, invalid reference, contradictory required/forbidden values | Case validation fails before architecture invocation |
| SCORE-01..07 | Missing approval, extra approval, forbidden flag, extra risk flag, missing info, wrong recommendation/next step, absent evidence/ref | Automated case failure; no evidence-count-only pass |
| GROUND-01..03 | No signoff, malformed reviewer entry, reviewer fail/pass | Pending, validation failure, fail/pass respectively |

## 11. Public-case policy summary

| Case | Core expected approvals | Specialist triggers | Expected risk flags | Missing information | Recommendation |
|---|---|---|---|---|---|
| PUB-01 / REQ-1001 | Manager | None | `existing_tool_overlap` as a match, not confirmed duplication | None | Route for Manager approval after scope/capacity check |
| PUB-02 / REQ-1002 | Department Head, Finance, Procurement | Security; Legal | overlap, security, legal | None | Proceed to required human approvals |
| PUB-03 / REQ-1003 | Department Head, Finance, Procurement | Security | overlap, security | None | Proceed to approvals including repository-control review |
| PUB-04 / REQ-1005 | Department Head, Finance, Procurement | Finance exception; Security, Privacy, Legal | budget, security, privacy, legal | None | Route for budget exception and specialist reviews; no automatic rejection |
| PUB-05 / REQ-1006 | No financial tier can be determined | Clarification; no specialist tier until data scope is known | missing information, existing NeuralDesk match; injection flag optional | cost, user_count, data_access_level, business_justification | Request clarification; ignore embedded approval instruction |
| PUB-06 / REQ-1009 | Department Head, Finance, Procurement | Security, Legal | vendor risk unavailable, security, legal | None | Manual review; preserve HTTP 503 and do not call the assessment expired |

All recommendation and risk outcomes above are policy-derived from actual fixture facts; evidence citations and manual review checklists are in `evals/public_cases.json`.

## 12. Approval gate

This is a specification and evaluation-design correction only. It does not implement either architecture. The 365-day inclusive boundary remains an explicit interpretation to confirm with the policy owner before production; the assessment implementation may proceed with this interpretation clearly recorded and tested.
