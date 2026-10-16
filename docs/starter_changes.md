# Changes to instructor-provided files

**Protected evidence (never modified):** everything under `data/`, `mock_api/`, `evals/public_cases.json`, `evals/README.md`, `docs/Assignment_3_Brief.pdf`.
`scripts/check_starter_integrity.py` verifies these byte-for-byte against `integrity/starter_manifest.json` (SHA-256 of the baseline commit `5e6e2fc`), and a unit test runs it.

```bash
python scripts/check_starter_integrity.py
```

## Handover state
At handover the working tree was missing four starter files (`mock_api/__init__.py`, `mock_api/app.py`, `data/README.md`, `evals/README.md`) although they were in the Git index. They were restored from the index without change. The virtualenv copied from another machine had a dangling interpreter and was recreated (`.venv` is git-ignored).

## Scaffold code that was changed (the brief says diagnosing the scaffold is part of the assignment)

| File | Issue found in the scaffold | Change |
|---|---|---|
| `evals/run_public_evals.py` | `python evals/run_public_evals.py` failed to import `src` (repo root not on `sys.path`) | 2 lines adding the root to `sys.path`. Expectation logic is untouched and is imported unmodified by `evals/compare_architectures.py` |
| `verify_setup.py` | Its sample `ProcurementDecision` did not satisfy the starter's own strict contract (missing required fields), so the pre-flight could not pass | Sample updated to the full contract |
| `src/vendor_client.py` | Raised bare `HTTPError`s; outage vs absence not distinguishable; no retry | `get_vendor_risk` keeps its signature and now preserves status + service text; added `fetch_vendor_risk` returning `ok / not_found / unavailable`, 1 retry on transient failures, malformed bodies treated as unavailable |
| `src/contracts.py` | Contract had no place for rationale, handoff, run metadata, tool attribution or measured telemetry | Added **optional** fields only (`rationale`, `human_handoff`, `ai_assessment`, `metadata`, `EvidenceItem.tool`, extra telemetry counters). All original required fields and validators are unchanged |
| `src/solution.py` | Stub (`NotImplementedError`-style scaffold) | Replaced by the real pipeline (see `docs/architecture.md`) |
| `src/telemetry.py` | Optional counter helper | Left in place, unused; real measurement is in `src/instrumentation.py` |
| `app.py` | Starter UI | Rewritten (request details, evidence panel, recommendation + handoff, architecture selector, custom request, run details) |
| `run_local.py` | Hardcoded ports; a port clash gave a confusing failure; the UI process was not told which API port to use | Ports via `API_PORT` / `UI_PORT`, early clash detection with a clear message, `VENDOR_RISK_BASE_URL` passed to the UI |
| `.env.example` | Provider placeholders for other vendors | Groq configuration with placeholders only |
| `data/vendors.csv` handling | Empty cells load as `NaN` through pandas and would print as the text "nan" | Normalised to `None` in `src/tools.py::records` (the CSV itself is unchanged) |

Use `git diff 5e6e2fc -- <file>` to see the exact change to any file.
