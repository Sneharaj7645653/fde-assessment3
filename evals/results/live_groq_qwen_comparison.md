# Comparison: live_groq_qwen

- Provider mode: **live-groq** (model: `qwen/qwen3.8-27b`)
- Case sets: public; cases: 6; runs per case: 2
- Generated: 2026-10-14 09:08:52 +0530
- Automated assertions use the instructor's `evaluate()`; manual grounding review is reported separately and is **not** included in these numbers.

| Metric | A - single agent | B - staged (2 agents) |
|---|---:|---:|
| Runs | 12 | 12 |
| Automated pass (runs) | 12 | 12 |
| Recommendation | 12/12 | 12/12 |
| Next step | 12/12 | 12/12 |
| Evidence expected | 12/12 | 12/12 |
| Evidence grounded | 12/12 | 12/12 |
| Approvals | 12/12 | 12/12 |
| Risk flags | 12/12 | 12/12 |
| Missing information | 12/12 | 12/12 |
| Human escalation | 12/12 | 12/12 |
| Mean latency, end-to-end (ms) | 21137.38 | 48748.8 |
| Mean latency, net of rate-limit waits (ms) | 1512.38 | 2790.47 |
| Median net latency (ms) | 1543.4 | 2786.6 |
| p95 net latency (ms) | 1659.9 | 3111.0 |
| Mean model calls (all attempts, incl. retries) | 3.92 | 6.25 |
| Mean model calls that succeeded | 2.0 | 3.0 |
| Mean tool calls | 4.17 | 4.17 |
| Mean prompt tokens | 2341.83 | 3757.17 |
| Mean completion tokens | 387.08 | 875.5 |
| Failed model calls (total) | 23 | 39 |
| Failed tool calls (total) | 4 | 4 |
| Guardrail tool back-fills (total) | 0 | 0 |
| Ungrounded model claims dropped (total) | 2 | 30 |
| Model status per run | {'live': 12} | {'live': 12} |
| Telemetry matches independent counts (runs) | 12 | 12 |
| Cases with unstable outcomes across runs | [] | [] |

## Pass rate by category (automated)

| Category | A - single agent | B - staged (2 agents) |
|---|---:|---:|
| approval_threshold | 2/2 | 2/2 |
| existing_tool | 4/4 | 4/4 |
| incomplete_or_ambiguous | 2/2 | 2/2 |
| security_sensitive | 2/2 | 2/2 |
| tool_unavailable | 2/2 | 2/2 |

## Failed runs

**A - single agent**: none
**B - staged (2 agents)**: none
