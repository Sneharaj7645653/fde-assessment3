# Architecture Decision Memo

## Decision
Ship **Architecture A, the single agent**, with the deterministic policy engine as the authority and humans approving everything.

## Evidence
Same six public cases, both architectures, two runs each, live model `qwen/qwen3.8-27b` on Groq. All 24 runs received live model answers. Expectations come from the instructor's own `evaluate()`; evidence was also re-verified independently against the data files and the mock API. Source: `evals/results/live_groq_qwen_*`.

| Metric | A single | B staged (2 agents) |
|---|---:|---:|
| Runs passing every automated check | 12/12 | 12/12 |
| Evidence grounded (independent audit) | 12/12 | 12/12 |
| Successful model calls per case | 2.0 | 3.0 |
| Tool calls per case | 4.17 | 4.17 |
| Median latency, net of rate-limit waits | 1.5 s | 2.8 s |
| Prompt / completion tokens per case | 2,342 / 387 | 3,757 / 876 |
| Model claims rejected as ungrounded (total) | 2 | 30 |

A model-free baseline (tools plus policy only) passes 14 of 15 cases, including all six public ones. Its single failure is SYN-03, a synthetic request whose purpose is vague ("everyone else has it"); only a model's reading can catch that.

## Trade-offs
B did not improve any measured correctness, grounding, policy or escalation result. It cost about 50% more model calls, about 60% more prompt tokens and almost double the latency. Stage 1 repeatedly cited records that do not exist (30 dropped claims versus 2 for A); the grounding checks caught them, but this is extra failure surface rather than extra safety. Policy correctness comes from code in both designs, so a second agent has little left to improve on these cases.

## Risks and limits
- Six public cases, two runs, one model: small sample. SYN-03, where the model matters, and the other extended cases were not run live because of free-tier quota; the model's accuracy benefit is therefore **not demonstrated**.
- Free-tier rate limits caused 429 retries, so raw attempt counts overstate cost. We report successful calls and keep wait time out of latency.
- Grounding review of evidence is AI-assisted only; a human review is still needed. Hidden cases and other models are untested.
- Before production: run the extended and hidden cases live over many repetitions, review rationales manually, and confirm the cross-region Legal interpretation with the policy owner.

## Why A is the right MVP
The risky decisions (thresholds, triggers, approvals, escalation) are deterministic and identical in both designs. The model only interprets context and explains, and it can only add caution when its quote exists in the data. A does that with fewer calls, less latency and fewer ungrounded claims. Revisit B only if future evidence shows the reviewer stage reducing false escalations.
