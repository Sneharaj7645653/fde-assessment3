# Pre-Implementation Audit Corrections

Date: 2026-10-09

## Scope and authoritative inputs

This report records corrections made after the independent readiness audit. The policy source is `data/procurement_policy.md`; actual fixture facts override case titles and prior summaries. No application architecture or external service was invoked.

Inspected: `specs/03-deterministic-rules-spec.md`, `src/contracts.py`, `src/sample_output.json`, `evals/public_cases.json`, `evals/run_public_evals.py`, `specs/reports/05-preimplementation-review.md`, `specs/00-initial-assessment-spec.md`, `data/procurement_policy.md`, `data/README.md`, all six public request records and relevant employees/budget/catalog/vendor/purchase/vendor-risk records, `mock_api/app.py`, `src/vendor_client.py`, `src/solution.py`, and `requirements.txt`.

## Findings and corrections

| Original finding | Change and location | Validation performed | Result | Remaining limitation |
|---|---|---|---|---|
| PUB-01 suppressed the existing SignFlow catalog/history match and treated no overlap as certain. | R-004 and case PUB-01 in `specs/03-deterministic-rules-spec.md` / `evals/public_cases.json`; `src/sample_output.json` now cites SW010 and PO-2513, flags an existing-product match, and explicitly avoids calling it redundant. | Fixture read; required source/reference/finding checks exercised in evaluator self-check. | PASS | Current unused seat capacity and functional redundancy are not in the fixtures; manual checklist requires review. |
| Policy-required integrations were classified application-level; REQ-1006 business purpose was inadequate but not missing. | Input contract and R-001 in `specs/03-deterministic-rules-spec.md`; PUB-05 now requires clarification for cost, user count, unknown access scope, and business purpose. Explicit empty integrations mean none; absent/null means unknown. | Compared against Policy Section 1 and REQ-1006; schema/evaluator validation. | PASS | Valid annual estimates require traceable source/basis and are an explicitly labeled implementation choice. |
| Missing or inconsistent budget components lacked distinct behavior. | R-002, Section 5, and failure table in `specs/03-deterministic-rules-spec.md`; added canonical `budget_data_unverified` for untrustworthy budget data. No amount is silently substituted; over-budget is an exception path, not rejection. | Static comparison to budget formula in `data/README.md`; boundary/failure cases specified. | PASS | Budget failure scenarios are specified but not run as application tests. |
| Freshness logic presented the 365-day boundary as an unquestionable policy fact and could call missing dates expired. | R-006 and date matrix in `specs/03-deterministic-rules-spec.md`; inclusive 365-day interpretation is explicitly labeled implementation choice; missing, unknown, unavailable, expired, and conflicting states are distinct. | Date arithmetic checked against 2026-09-30; missing dates do not require `vendor_review_expired`. | PASS | Policy owner confirmation is required before production; mock fixture ages otherwise classify deterministically. |
| PUB-05 required an optional prompt-injection flag. | R-009 and PUB-05 in the spec/cases: ignoring embedded text is mandatory; the flag is optional and allowed only as an extra. No escalation is triggered by injection alone. | Evaluator checks the flag is not required, and it rejects unrelated unsupported flags. | PASS | The evaluator does not claim to prove that an arbitrary detector is reliable; the manual checklist verifies the instruction was ignored. |
| New public-case expectation keys were ignored by the runner; malformed schema could be silently accepted. | Rewrote `evals/run_public_evals.py` with strict case/expectation validation, fixed case associations, all-of/one-of/forbidden semantics, extra-value rejection, request-ID check, and `--validate-only`. | Schema success and failure-path tests run against the actual six cases (see Validation). | PASS | Architecture execution cannot be tested because `src/solution.py` still raises `NotImplementedError`; Pydantic is unavailable. |
| Evidence quantity could pass without grounded facts. | Cases now declare source, reference, required finding fragments, and evidence status. Evaluator matches all required assertions and outputs `PENDING_GROUNDING_REVIEW` until human sign-off. | Positive/negative evidence matching tests run; manual-review schema tested. | PASS | Literal matching verifies traceability and required text, not factual truth or completeness. Reviewer checklist remains mandatory. |
| Extra approvals/flags, aliases, and missing-info comparisons were ambiguous. | Evaluation semantics documented in Section 8 of the spec and implemented in the runner. Unsupported extras fail; canonical output required by contract; documented evaluator-only legacy aliases are normalized explicitly. | Scoring tests for missing required and unjustified extra values; alias behavior tested. | PASS | Semantic policy review is not reducible to string comparison. |
| Output contract allowed implicit required fields, duplicate values, and unknown extras; evidence status was not structured. | `src/contracts.py` now requires explicit core fields, forbids extras, rejects duplicate approval/flag/missing items, requires evidence references, adds `evidence_status`, and validates non-negative telemetry relations. Telemetry remains optional as a whole. | Python AST parse; JSON structural check; runtime Pydantic check attempted. | BLOCKED (runtime) | Pydantic is not installed. Declared requirement is `pydantic>=2.9,<3`; run `ProcurementDecision.model_validate(sample)` in the declared project environment after normal setup, without changing this task’s environment. |
| Architecture metrics could rely on model-reported telemetry and did not define retries/errors. | Section 9 of the spec defines a shared transport/dispatcher measurement contract, exact latency window, attempts/retries/failure/timeouts, common test set, and pending instrumentation requirement. Runner never treats output telemetry as ground truth. | Static inspection of measurement documentation and runner output columns. | PASS (design) | Shared call-count hooks must be wired at provider/tool boundaries during implementation; counts remain blank/unavailable until then. |
| Earlier review claimed readiness and protected-file integrity without sufficient evidence. | Banner added to `specs/reports/05-preimplementation-review.md`; this report supersedes the old readiness conclusion. | Git/baseline availability checked; repository has no `.git`, and no reliable pre-change hashes were available. | UNVERIFIED (historical integrity claim) | Cannot independently prove whether prohibited files changed in earlier sessions. This correction task itself changed only the scoped files listed below. |

## Independently verified public-case summary

| Case | Verified facts and expected decision | Status |
|---|---|---|
| PUB-01 / REQ-1001 | $800, Finance, $29,000 available; Manager. SignFlow review is current and legal terms approved. SW010 and PO-2513 are existing-product evidence. Flag potential overlap, not confirmed duplication. No specialist review is supported. | PASS after correction |
| PUB-02 / REQ-1002 | $12,000, Marketing, $15,000 available; Department Head, Finance, Procurement. BrandBoard is new, assessment not completed/missing date, terms Draft: Security and Legal. PixelCraft and CreativeSuite are same-category alternatives; surface them without asserting equivalence. No Privacy trigger is established. | PASS after correction |
| PUB-03 / REQ-1003 | $18,000, Engineering, $26,000 available; Department Head, Finance, Procurement. Source code triggers Security. Existing CodeMate match/history; no Privacy or Legal trigger is established. | PASS after correction |
| PUB-04 / REQ-1005 | $22,000, Sales, $18,000 available; $4,000 over budget. Department Head, Finance, Procurement plus Finance exception; customer PII/incomplete assessment trigger Security, PII and outside-region storage trigger Privacy, and new-vendor $22,000/Unknown terms/cross-region support Legal. No automatic rejection. | PASS after correction |
| PUB-05 / REQ-1006 | Cost/user count null, access unknown, “Need AI ASAP” inadequate as purpose. No financial tier; clarify four items. NeuralDesk existing limited-use match is surfaced. Ignore injected approval instruction. Prompt flag optional. Do not infer privacy trigger before scope is known. | PASS after correction |
| PUB-06 / REQ-1009 | $15,000, Finance, $29,000 available; Department Head, Finance, Procurement. Confidential docs and unknown/missing assessment require Security; new vendor at $15,000 and Unknown terms require Legal. NimbusAI fixture forces HTTP 503. No Privacy trigger is evidenced. | PASS after correction |

## Architecture comparison contract

The implementation must use the same six cases in the same order, same data/policy snapshot, provider/model settings, tool semantics, retry rules, and controlled cache conditions for both architectures. End-to-end latency is measured with a monotonic clock around `handle_request` plus output contract validation, including retries and failures but excluding case loading, scoring, reviewer time, and CSV writing. LLM/tool counts are observed attempts at common transport/dispatcher boundaries; retries are included in totals and counted separately; failures/timeouts and tool/API errors are recorded as defined in spec Section 9. The evaluator does not trust decision telemetry. The exact Architecture A and Architecture B responsibilities remain those in `specs/00-initial-assessment-spec.md`: one agent baseline; exactly two agents in the staged variant, evidence gathering/handoff then evaluation/recommendation, with deterministic controls code-enforced.

## Validation performed

### Actual checks and results

- `python3 evals/run_public_evals.py --validate-only` — **PASS**: `Case schema valid: 6 cases; request references valid.` and `No architecture invoked.`
- JSON parsing of `src/sample_output.json`, `evals/public_cases.json`, and `data/requests.json` — **PASS**. Six cases, unique IDs, valid request references.
- Python `ast.parse` on `src/contracts.py` and `evals/run_public_evals.py` — **PASS**.
- VS Code diagnostics via `get_errors` for the contract and runner — **PASS**: no errors reported.
- Sample structural check — **PASS**: exact required field set; `Manager` and `existing_tool_overlap` are canonical; sample references existing SignFlow catalog/history records.
- PUB-01/PUB-05 consistency check — **PASS**: PUB-01 requires overlap evidence but not a duplicate conclusion; PUB-05 requires all four missing-information items and permits but does not require `prompt_injection_detected`.
- Inline pure-evaluator tests — **PASS**: generated contract-shaped test decisions satisfied each of the six case expectation sets; malformed/missing/unsupported/contradictory expectation fields were rejected; missing approval, unsupported extra approval/flag, bad evidence reference, wrong recommendation, wrong next step, and unmet alternative groups failed; valid alternative groups and documented aliases were accepted; duplicate case IDs and incorrect fixed mappings were rejected; grounding-review sign-off rejected missing checklist answers, non-Boolean answers, and status/checklist disagreement, and accepted a complete, internally consistent review record.
- One initial alternative-group test input contradicted its own forbidden list and failed as invalid test setup; the input was corrected and the success/failure tests then passed. No evaluator code change was needed for that correction.
- Pydantic runtime validation — **BLOCKED**: `pydantic` is absent in the active interpreter, and importing `src.contracts` is also blocked earlier by missing `python-dotenv` through the package import chain. No installation was attempted. In the declared project environment (`pydantic>=2.9,<3`), run `ProcurementDecision.model_validate(json.load(open('src/sample_output.json')))` after normal dependency setup.
- Full Architecture A/B evaluation — **NOT RUN**: `src/solution.py` remains an unimplemented `NotImplementedError` adapter; this task prohibits architecture implementation and external service calls.
- Measurement counters — **NOT AVAILABLE**: latency can be measured by the runner, but shared LLM/tool instrumentation is not yet wired; blank counters are not treated as zero.
- Historical protected-file integrity — **UNVERIFIED**: `git rev-parse --is-inside-work-tree` reports that the workspace is not a Git repository; no reliable pre-change baseline was provided. This correction task’s tool edits were limited to the scoped files below, but that does not prove earlier integrity.

No package was installed and no external service was called. No Git diff or reliable historical integrity comparison is available.

## Files changed in this correction task

- `specs/03-deterministic-rules-spec.md`
- `src/contracts.py`
- `src/sample_output.json`
- `evals/public_cases.json`
- `evals/run_public_evals.py`
- `specs/reports/05-preimplementation-review.md`
- `specs/reports/06-audit-corrections.md` (this report)

No policy, source fixture, solution adapter, architecture implementation, dependency, or external-service file was intentionally edited.

## Final verdict

**READY FOR IMPLEMENTATION SPECIFICATION**

This verdict concerns readiness to write the implementation specification, not readiness to implement either architecture. It is valid only if the post-edit checks recorded above pass. Pydantic runtime validation, architecture execution, actual LLM/tool measurement, and historical protected-file integrity are explicitly not claimed as verified.
