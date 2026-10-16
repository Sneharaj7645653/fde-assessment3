# Spec 05 — Final implementation and requirements traceability

Authoritative description of what was built. Supersedes the planning specs 00–04 where they differ (those remain as the planning record). Source of truth order: assessment PDF → starter data/policy → this spec/code → engineering judgement (marked *interpretation*).

## 1. Requirement → implementation → verification

Status key: **Verified** = exercised by an automated test or a recorded run; **Partial** / **Unverified** are explained.

| # | Official requirement (PDF) | Implementation | Verification | Status |
|---|---|---|---|---|
| R1 | Product UI: request details, evidence panel, recommendation + action | `app.py` (Streamlit): request table, evidence cards with status badges, recommendation, next step, handoff, approvals, flags, missing info | `tests/test_app_ui.py` (11 tests); manual runs in the in-app browser in deterministic mode and with the live qwen model | Verified |
| R2 | ≥3 tools, ≥1 deterministic | 4 tools in `src/tools.py`; 3 deterministic (`lookup_requester_budget`, `search_existing_software`, `check_policy`) + 1 external HTTP (`get_vendor_status`) | `tests/test_tools.py`, telemetry `tool_call_counts` cross-checked against independently counted calls in the harness | Verified |
| R3 | Working single-agent baseline | `agents.run_single` (Architecture A) | `tests/test_agents.py`; live runs: 12/12 on the six public cases (README table 1) | Verified |
| R4 | Structured outputs | `ProcurementDecision` (`src/contracts.py`), strict pydantic, schema-validated model outputs with one repair call | `tests/test_agents.py::ContractTests` (every request × both architectures) | Verified |
| R5 | Human handoff for sensitive decisions/exceptions | `human_review_required` always true; `human_handoff` (reasons, decision owners, authority note); UI warning | tests above | Verified |
| R6 | AI interprets, code enforces thresholds, human approves | Model output is advisory and filtered by `agents._apply_signals`, `grounding.py`; `policy.py` is authoritative | `test_model_cannot_override_policy_with_claims`, `test_model_can_only_escalate_with_a_verbatim_quote`, `test_model_cannot_remove_flags_or_approvals_for_injection_case` | Verified |
| R7 | Build A first, then lightweight B (staged / 2-agent), ≤2 agents | `agents.run_staged`: Evidence Analyst (tools) → Independent Reviewer (no tools) with a validated `EvidenceBrief` | `ArchitectureBTests` | Verified |
| R8 | Same test set on both; evaluate correctness, grounding, policy, escalation, latency, LLM/tool calls | `evals/compare_architectures.py` (public 6 + extended 9, instructor `evaluate()` reused unmodified, independent evidence audit, measured latency/calls/tokens, repeat runs) | `tests/test_eval_and_integrity.py`; result files in `evals/results/` | Verified |
| R9 | Edge: incomplete/ambiguous | `request_clarification`; PUB-05, SYN-03 | harness + `test_policy.py::MissingInformationTests` | Verified (SYN-03 needs the model; see README) |
| R10 | Edge: existing tool already solves need | `existing_tool_overlap` with match basis; never asserts capacity | PUB-01/02/03, EXT-03/04 | Verified |
| R11 | Edge: conflicting or expired vendor info | states `approved/expired/not_completed/missing/unavailable/unknown`; conflict → manual review | `VendorStateTests`, EXT-01 (REQ-1007) | Verified |
| R12 | Edge: security-sensitive, approval thresholds | exact `Decimal` tiers; triggers in `policy.evaluate` | `ThresholdTests` (boundaries 1000/1000.01/10000/10000.01/25000/25000.01), `TriggerTests`, PUB-03/04, EXT-02, SYN-01 | Verified |
| R13 | Edge: prompt injection in business data | regex detector over request + catalog/purchase/registry/API text; model quote-verified; injection never changes policy | `InjectionTests`, PUB-05, SYN-02 (request text), SYN-04 (planted in API notes) | Verified |
| R14 | Edge: tool/API unavailable | `vendor_client.fetch_vendor_risk` → `unavailable`; evidence status `unavailable`; manual review | `VendorClientTests`, PUB-06, UI 503 test | Verified |
| R15 | Public GitHub repository | repo prepared locally | — | **Not done by instruction** — user asked for local changes only, no push |
| R16 | One-command local start | `./start.sh` (venv + deps + preflight + `run_local.py`); `python run_local.py` | `run_local.py` started and health-checked (README "What was verified") | Verified locally (macOS, Python 3.14; started on alternate ports) |
| R17 | Architecture/workflow diagram + assumptions | `docs/architecture.md` | review | Verified (documentation) |
| R18 | Reproducible evaluation script and results | `evals/compare_architectures.py`, `evals/results/` | commands in README | Verified |
| R19 | Decision memo ≤ 500 words | `docs/architecture_decision_memo.md` | `tests/test_eval_and_integrity.py::DeliverableTests` (464 words) | Verified |
| R20 | README coverage; no secrets; `.env.example` | `README.md`, `.env.example`, `.gitignore` | `DeliverableTests::test_no_secrets_in_tracked_candidates`; `.env` git-ignored | Verified |
| R21 | Policy: date checks use the policy reference date | `policy.reference_date()` parses the policy file | `test_thresholds_match_policy_file` | Verified |
| R22 | Policy: do not infer favourable status when evidence is missing/unavailable | `vendor_risk_state`, evidence statuses | `test_unavailable_evidence_is_not_expired_or_favourable` | Verified |

## 2. Design rules enforced in code

1. Model output can only **add caution** (clarification request, injection flag), and only when its quote appears verbatim in the business data. It can never remove a flag/approval, change a tier, or change the recommendation code.
2. Evidence items are built from tool results by `composer.build_evidence`; the model writes none. Model-written rationale is accepted only if every `$` figure, date and record id also appears in the evidence/request, and it makes no approval/purchase claim; otherwise a deterministic rationale is used and `ungrounded_claims` is incremented.
3. A tool never runs twice per request; skipped mandatory tools are run by a guardrail and counted.
4. Provider errors are classified (`missing_credentials, auth, rate_limited, timeout, network, server, bad_request, malformed_output, schema_validation`); any failure yields a deterministic fallback with identical policy output and an honest `llm_status`.
5. Credentials: only the first working Groq key is used; others only replace a key rejected as invalid; never rotated to bypass rate limits; keys are never logged or included in errors (tested).

## 3. Telemetry definitions (all measured by `src/instrumentation.py`)

`llm_calls` = provider HTTP attempts including retries; `tool_calls` = dispatches including retries and rejected dispatches; `rate_limit_wait_ms` = time deliberately slept to respect provider limits (reported separately; "net latency" excludes it); `guardrail_tool_backfills`; `ungrounded_claims`. The harness independently counts model HTTP posts and vendor-API attempts and flags any mismatch (`telemetry_consistent`).

## 4. Known gaps (also in README)

- Live results come from one model (`qwen/qwen3.8-27b`), one provider, 6 public cases × 2 runs; the extended cases were not run live (quota). An earlier `openai/gpt-oss-120b` run was discarded because its daily quota ran out.
- Human grounding review is **not** done; only an AI-assisted review (labelled) exists.
- GitHub publication and Google-Form submission not performed (deadline 8 Oct 2026 has passed; user asked for local changes only: no push).
