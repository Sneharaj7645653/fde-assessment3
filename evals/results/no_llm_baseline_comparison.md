# Comparison: no_llm_baseline

- Provider mode: **no-llm (deterministic fallback)** (model: `-`)
- Case sets: public, extended; cases: 15; runs per case: 1
- Generated: 2026-10-13 23:24:09 +0530
- Automated assertions use the instructor's `evaluate()`; manual grounding review is reported separately and is **not** included in these numbers.

| Metric | A - single agent | B - staged (2 agents) |
|---|---:|---:|
| Runs | 15 | 15 |
| Automated pass (runs) | 14 | 14 |
| Recommendation | 14/15 | 14/15 |
| Next step | 14/15 | 14/15 |
| Evidence expected | 15/15 | 15/15 |
| Evidence grounded | 15/15 | 15/15 |
| Approvals | 15/15 | 15/15 |
| Risk flags | 14/15 | 14/15 |
| Missing information | 14/15 | 14/15 |
| Human escalation | 15/15 | 15/15 |
| Mean latency, end-to-end (ms) | 18.37 | 19.15 |
| Mean latency, net of rate-limit waits (ms) | 18.37 | 19.15 |
| Median net latency (ms) | 3.8 | 3.7 |
| p95 net latency (ms) | 219.6 | 223.8 |
| Mean model calls | 0.0 | 0.0 |
| Mean tool calls | 3.07 | 3.07 |
| Mean prompt tokens | 0.0 | 0.0 |
| Mean completion tokens | 0.0 | 0.0 |
| Failed model calls (total) | 0 | 0 |
| Failed tool calls (total) | 2 | 2 |
| Guardrail tool back-fills (total) | 0 | 0 |
| Ungrounded model claims dropped (total) | 0 | 0 |
| Model status per run | {'disabled': 15} | {'disabled': 15} |
| Telemetry matches independent counts (runs) | 15 | 15 |
| Cases with unstable outcomes across runs | [] | [] |

## Pass rate by category (automated)

| Category | A - single agent | B - staged (2 agents) |
|---|---:|---:|
| approval_threshold | 4/4 | 4/4 |
| conflicting_or_expired_vendor | 2/2 | 2/2 |
| existing_tool | 2/2 | 2/2 |
| incomplete_or_ambiguous | 1/2 | 1/2 |
| prompt_injection | 2/2 | 2/2 |
| security_sensitive | 2/2 | 2/2 |
| tool_unavailable | 1/1 | 1/1 |

## Failed runs

**A - single agent**: 
- SYN-03#1: required risk flag missing: missing_information | required missing-information item absent: business_justification | recommendation expected request_clarificati
**B - staged (2 agents)**: 
- SYN-03#1: required risk flag missing: missing_information | required missing-information item absent: business_justification | recommendation expected request_clarificati
