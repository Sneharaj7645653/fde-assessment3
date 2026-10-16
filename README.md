# AI Procurement Request Copilot — FDE Assessment 3

An internal tool that reviews a software/service purchase request, gathers evidence with tools, applies the procurement policy **in code**, and recommends the next action — while **humans keep every approval, exception and purchase decision**.

Two architectures run behind the same UI, tools, policy engine and output contract, and are compared on the same cases:

- **A – single agent:** one tool-using model agent gathers evidence and writes the interpretation.
- **B – staged, two agents:** an Evidence Analyst agent (tools) hands a validated brief to an Independent Reviewer agent (no tools).

> All data, vendors and policy are synthetic assessment material. Nothing here approves, purchases or modifies anything.

## Quick start

Prerequisites: Python 3.11+ (developed on 3.14), macOS/Linux shell.

```bash
./start.sh
```

This creates `.venv`, installs `requirements.txt`, creates `.env` from `.env.example` if missing, runs the pre-flight (`verify_setup.py`), then starts the mock vendor-risk API (`http://127.0.0.1:8001`) and the UI (`http://127.0.0.1:8501`). If those ports are busy: `API_PORT=8011 UI_PORT=8511 ./start.sh`.

Manual equivalent:

```bash
python -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env        # then add GROQ_API_KEY_1 (optional)
python verify_setup.py
python run_local.py
```

### Model configuration (Groq) — optional

Without a key the app still works in **deterministic mode** (tools + policy, no model); the UI and `metadata.llm_status` say so. To enable the agents put a key in `.env` (git-ignored; never commit it):

```
LLM_PROVIDER=groq
GROQ_MODEL=qwen/qwen3.8-27b
GROQ_API_KEY_1=...            # more keys (GROQ_API_KEY_2…, or GROQ_API_KEYS=a,b) are standby only
```

Extra keys are used **only** if the first is rejected as invalid; they are never rotated to get around rate limits (a 429 is waited out on the same key, then the run falls back). `LLM_PROVIDER=none` forces deterministic mode.

## Product workflow

1. Pick a request (or enter a custom one) and an architecture in the sidebar; press **Run analysis**.
2. The agent(s) call the tools; the policy engine computes approvals, flags and the recommendation; validated model signals can only add caution.
3. The UI shows: request details → **Recommendation** + human-review warning + **Human handoff** (who must act) → rationale → **Required approvals**, **Risk flags**, **Missing information** → **Next step** → **Supporting evidence** (each item: source, record reference, producing tool, status badge `verified / missing / expired / unknown / unavailable / conflicting`) → measured run details.
4. Errors show "No recommendation was generated"; a model outage shows a fallback warning while policy output is unchanged.

Output contract (`src/contracts.py`, identical for A and B): `recommendation`, `recommendation_code`, `evidence[]`, `required_approvals[]`, `missing_information[]`, `risk_flags[]`, `next_step`, `human_review_required`, plus optional `rationale`, `human_handoff`, `ai_assessment`, `metadata`, `telemetry`.

## Architecture, tools and agents

Full diagrams (Mermaid) and the list of assumptions are in [`docs/architecture.md`](docs/architecture.md). Summary:

| Layer | Does | Authority |
|---|---|---|
| Model (Groq) | interprets context: purpose adequacy, instruction-like text, existing-tool overlap; writes rationale / questions | advisory; can only add caution, only with a quote found verbatim in the data |
| Code (`policy.py`, `tools.py`, `composer.py`) | thresholds (exact `Decimal`), budget check, approvals, security/privacy/legal triggers, vendor-assessment state, recommendation code, all evidence text | authoritative |
| Humans | approve spend, grant exceptions, accept vendor terms, resolve conflicts | final |

Tools: `lookup_requester_budget`, `search_existing_software`, `check_policy` (deterministic) and `get_vendor_status` (HTTP to the mock API; 503/timeouts → `unavailable`, 404 → `missing`; one retry). Tools take only `request_id`, never run twice per request, and every dispatch is recorded.

**A vs B in code:** `agents.run_single` vs `agents.run_staged`. B adds a second model call with a different role, input (raw request + validated brief + deterministic evidence) and output schema, and Stage 2 is authoritative for the interpretive signals. Stage-1 facts citing unknown references are dropped before review.

**Prompt injection:** request text, catalog/purchase notes, registry notes and API notes are scanned; instruction-like text raises `prompt_injection_detected` and has no effect on approvals or flags. Model injection claims are accepted only with a verbatim quote.

## Reproduce the tests and evaluations

```bash
python -m unittest discover -s tests              # 105 tests, no network or model needed
python verify_setup.py                            # pre-flight
python scripts/check_starter_integrity.py         # protected starter inputs are byte-identical to baseline

# instructor's public runner (works for both architectures; add --grounding-review to apply a review file)
python evals/run_public_evals.py --architecture single
python evals/run_public_evals.py --architecture staged

# this project's A/B comparison (needs the mock API: python run_local.py, or uvicorn mock_api.app:app --port 8001)
python evals/compare_architectures.py --provider none --label no_llm_baseline     # deterministic floor, no model
python evals/compare_architectures.py --provider groq --runs 2 --label live_groq  # live Groq, about 20-30 min on the free tier
```

Result files (`evals/results/<label>_*`): `_raw.csv` (every case × architecture × run), `_summary.json`, `_comparison.md`, `_template.csv` (columns of `templates/evaluation_results_template.csv`). Categories are never mixed: `no_llm_baseline_*` = deterministic fallback (mock/none), `live_groq_*` = real Groq calls.

Case sets: **public** (6 instructor cases, unchanged) + **extended** (`evals/extended_cases.json`, solution-owned: 4 real records not in the public set + 5 `SYN-*` synthetic requests for threshold boundary, injection in request text, injection planted in API notes, vague purpose, unknown vendor). Expectations were written from the policy before the live runs and not changed afterwards. The instructor's `evaluate()` is imported unmodified for every case; the harness adds an independent evidence audit (each item re-checked against the CSVs / a direct API call) and independently counts model HTTP posts and vendor attempts to cross-check the system's own telemetry.

## Evaluation results

Three result sets, **never mixed**. All numbers below are copied from the files named.

### 1. Live Groq, public cases — `evals/results/live_groq_qwen_*` (the comparison that decides)

Model `qwen/qwen3.8-27b`, 6 public cases × 2 runs × 2 architectures = 24 runs, **all 24 received live model answers**, telemetry matched independently counted HTTP calls on all 24. Command: `python evals/compare_architectures.py --provider groq --model qwen/qwen3.8-27b --sets public --runs 2 --label live_groq_qwen`.

| Metric | A – single agent | B – staged (2 agents) |
|---|---:|---:|
| Runs passing all automated checks | 12 / 12 | 12 / 12 |
| Recommendation / next step correct | 12 / 12 | 12 / 12 |
| Approvals / risk flags / missing info correct | 12 / 12 each | 12 / 12 each |
| Human escalation correct | 12 / 12 | 12 / 12 |
| Evidence matches expected + independently audited | 12 / 12 | 12 / 12 |
| Successful model calls per case (mean) | 2.0 | 3.0 |
| Model attempts per case incl. 429 retries (mean) | 3.92 | 6.25 |
| Tool calls per case (mean) | 4.17 | 4.17 |
| Net latency per case, mean / median / p95 | 1.51 s / 1.54 s / 1.66 s | 2.79 s / 2.79 s / 3.11 s |
| Prompt / completion tokens per case | 2,342 / 387 | 3,757 / 876 |
| Model claims rejected as ungrounded (total) | 2 | 30 |
| Guardrail tool back-fills / outcome differences between runs | 0 / none | 0 / none |

"Net latency" excludes time the client deliberately waited for Groq's free-tier rate limits (end-to-end means: 21.1 s vs 48.7 s, dominated by those waits). 429 retries are counted as failed model calls (A 23, B 39), which is why attempts exceed successful calls. Tool calls above 4 include the one retry after the NimbusAI HTTP 503.

### 2. No model (deterministic floor) — `evals/results/no_llm_baseline_*`

15 cases (6 public + 9 extended), tools + policy only, both architecture labels identical by construction: **14/15 pass**. All six public cases pass. The one failure is `SYN-03` (complete request whose stated purpose is "everyone else seems to have it"), which needs model judgement; this is expected and is why the case exists.

### 3. Instructor's public runner

```bash
python evals/run_public_evals.py --architecture single --grounding-review evals/grounding_reviews_ai_assisted.json   # 6 PASS, 0 FAIL, 0 pending
python evals/run_public_evals.py --architecture staged --grounding-review evals/grounding_reviews_ai_assisted.json   # 6 PASS, 0 FAIL, 0 pending
```

Run in no-model mode. Without the review file all six cases show `PENDING_GROUNDING_REVIEW` (the runner requires a review per case). **The review file is AI-assisted (written by Claude after reading the generated evidence), not a human sign-off**; the runner does not authenticate reviewers, so a genuine human review is still outstanding.

### Not measured
- The extended cases (incl. the AI-dependent `SYN-03`, injection planted in vendor data `SYN-04`) were **not run against a live model** (quota). Their deterministic behaviour is tested and in table 2.
- A first live run with `openai/gpt-oss-120b` is **discarded**: its 200k-tokens/day free quota ran out mid-run (and Groq returned malformed-tool-call 400s), so only 12 of 60 runs were live. The harness flags such runs as invalid; they are not reported as results. The client now retries those 400s once and, if the tool loop still fails, continues to the final answer step.

## Architecture comparison and ship decision

**Ship Architecture A (single agent).** On the same six cases B matched A on every correctness, grounding, policy and escalation check, but used 50% more successful model calls, about 60% more prompt tokens and roughly 1.85× the latency, and its first stage cited non-existent records 30 times versus 2 for A (all caught by the grounding checks). Policy correctness comes from code in both designs, so a second agent has little to add. The model-free baseline shows how much correctness comes from the deterministic layer; the model's incremental value (purpose-adequacy and injection judgement, rationale) is **not demonstrated by pass/fail on the public cases**. The one-page memo is [`docs/architecture_decision_memo.md`](docs/architecture_decision_memo.md) (464 words).

## What was actually verified (and what was not)

Verified on macOS, Python 3.14:
- `python -m unittest discover -s tests` — all tests pass (policy boundaries, tools, Groq client with mocked HTTP incl. 401/429/timeouts, both architectures with scripted models incl. hostile model output, UI via Streamlit `AppTest`, harness, starter integrity).
- `verify_setup.py` pre-flight passes; `./start.sh` starts the mock API and UI (health endpoints returned 200 on alternate ports).
- UI exercised in the in-app browser (select request → run → read result), which found and fixed a `$…$` LaTeX rendering bug that the scripted UI tests could not see.
- Live Groq calls succeeded with `qwen/qwen3.8-27b` (table 1).

Not verified / not done: human grounding review; the GitHub publication and Google-Form submission (the brief's 8 Oct 2026 deadline has passed; no push was made); behaviour on hidden cases; other operating systems / Python versions; models other than qwen3.8-27b for live runs.

## Known limitations

- Small live sample (6 cases × 2 runs, one model); results are not statistically strong.
- Free-tier limits slow live runs and add retries; wall-clock times include waits (reported separately).
- The model can add caution but never relax policy, so a hallucinated "inadequate purpose" can cause an unnecessary clarification request; the verbatim-quote check limits but does not remove this.
- Interpretations of the policy (e.g. Legal review for sensitive data stored outside the region, security-relevant integrations) are listed in [`docs/architecture.md`](docs/architecture.md#6-assumptions-and-interpretations) and should be confirmed with the policy owner.
- Existing-tool overlap is by vendor/product/category match only; it cannot tell whether spare capacity exists.
- Keyword/regex injection detection is a floor; the model's quote-verified judgement supplements it.
- Single-process, no persistence or auth; this is a vertical slice, not a production service.

## Repository map

```
app.py                    Streamlit UI                     src/policy.py       deterministic policy engine
run_local.py / start.sh   one-command start                src/tools.py        4 tools + executor
src/solution.py           handle_request / evaluate_request src/agents.py      Architectures A and B
src/llm.py                Groq provider, errors, pacing    src/composer.py     evidence, next step, handoff
src/grounding.py          quote/rationale checks           src/instrumentation.py  measured telemetry
evals/compare_architectures.py  A/B harness              evals/extended_cases.json  solution-owned cases
evals/results/            result files                     docs/                architecture, memo, starter changes
specs/                    spec-driven planning + spec 05 (traceability)
integrity/ scripts/       starter-pack integrity manifest + checker
```

Changes to instructor-provided files are listed in [`docs/starter_changes.md`](docs/starter_changes.md); protected data/policy/mock-service files are unmodified (`python scripts/check_starter_integrity.py`).

## Troubleshooting

- **Port in use:** `API_PORT=8011 UI_PORT=8511 ./start.sh`.
- **UI says "No model is configured":** add `GROQ_API_KEY_1` to `.env` (or run with `LLM_PROVIDER=none` intentionally).
- **UI shows a fallback warning:** the model call failed (rate limit, quota, outage); the reason is shown and policy output is unchanged. Free-tier Groq limits are small (8k tokens/min; ~200k tokens/day for `gpt-oss-120b`).
- **Evaluation shows "not a valid live comparison":** some runs fell back; wait for quota to reset or lower `--runs`.
- **Vendor evidence "unavailable":** the mock API is not running on `VENDOR_RISK_BASE_URL`, or the fixture's deliberate 503 (NimbusAI) is being served.
