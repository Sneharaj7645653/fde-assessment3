"""Run Architecture A (single) and B (staged) on the SAME case set and report measured results.

Case sets
  public    evals/public_cases.json    instructor-provided, six cases (unchanged)
  extended  evals/extended_cases.json  solution-owned additions (real records + clearly marked SYN-* synthetic requests)

Every case is checked with the instructor's own `evaluate()` (imported from run_public_evals.py) so
expectations are applied identically. Beyond it this script adds:
  * an independent evidence audit: each evidence item is re-verified against the data files / a direct
    call to the mock API, not against the system's own tool outputs;
  * measured latency (end-to-end and net of deliberate rate-limit waits), model calls, tool calls, tokens;
  * a cross-check of the system's own telemetry against independently counted HTTP calls;
  * repeated runs (--runs) with outcome-stability reporting, because live models are nondeterministic.

Usage
  python evals/compare_architectures.py --provider groq --runs 2 --label live_groq
  python evals/compare_architectures.py --provider none --label no_llm_baseline
Outputs (evals/results/<label>_*): raw per-run CSV, summary JSON, comparison Markdown.
Manual/AI-assisted grounding reviews are reported separately from automated results.
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
import time
from collections import Counter, defaultdict
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evals"))

import httpx  # noqa: E402
import requests  # noqa: E402

import run_public_evals as instructor  # noqa: E402  (instructor's evaluator; used unmodified for expectation checks)
from src import tools  # noqa: E402
from src import vendor_client  # noqa: E402
from src.contracts import ProcurementDecision  # noqa: E402
from src.data_access import load_budgets, load_employees, load_purchase_history, load_requests, load_software_catalog, load_vendors  # noqa: E402
from src.llm import LLMProvider, NullProvider, get_provider  # noqa: E402
from src.solution import evaluate_request  # noqa: E402
from src.tools import records  # noqa: E402

RESULTS_DIR = ROOT / "evals" / "results"
DIMENSIONS = ["recommendation", "next_step", "evidence_expected", "evidence_grounded", "approvals", "risk_flags", "missing_information", "human_escalation"]
FAILURE_DIMENSION = [
    ("recommendation expected", "recommendation"), ("required next-step phrase", "next_step"),
    ("required grounded evidence", "evidence_expected"), ("evidence[", "evidence_expected"),
    ("approval", "approvals"), ("risk flag", "risk_flags"), ("risk-flag", "risk_flags"),
    ("missing-information", "missing_information"), ("human_review_required", "human_escalation"),
]


# ------------------------------------------------------------------ cases
def load_cases(sets: list[str]) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    request_ids = {r["request_id"] for r in load_requests()}
    if "public" in sets:
        public = json.loads((ROOT / "evals" / "public_cases.json").read_text())
        instructor.validate_cases(public, request_ids)
        for case in public:
            cases.append({**case, "set": "public", "category": CATEGORY_BY_PUBLIC[case["case_id"]]})
    if "extended" in sets:
        for case in json.loads((ROOT / "evals" / "extended_cases.json").read_text()):
            if "request" not in case and case["request_id"] not in request_ids:
                raise ValueError(f"{case['case_id']}: request_id does not resolve")
            cases.append({**case, "set": "extended"})
    return cases


CATEGORY_BY_PUBLIC = {
    "PUB-01": "existing_tool", "PUB-02": "existing_tool", "PUB-03": "security_sensitive",
    "PUB-04": "approval_threshold", "PUB-05": "incomplete_or_ambiguous", "PUB-06": "tool_unavailable",
}


def case_request(case: dict[str, Any]) -> dict[str, Any]:
    if "request" in case:
        return case["request"]
    return next(r for r in load_requests() if r["request_id"] == case["request_id"])


# ------------------------------------------------------------------ independent counting and audit
class Counters:
    def __init__(self) -> None:
        self.model_posts = 0
        self.vendor_attempts = 0


@contextmanager
def independent_counters(override: dict[str, dict] | None):
    """Count real outbound attempts without trusting the system's own telemetry; optionally poison vendor data."""
    counters = Counters()
    real_post, real_get = httpx.Client.post, vendor_client.get_vendor_risk

    def post(self, url, *a, **kw):  # noqa: ANN001
        if "groq" in str(url):
            counters.model_posts += 1
        return real_post(self, url, *a, **kw)

    def get(vendor_name, timeout_seconds=3.0):
        counters.vendor_attempts += 1
        if override and vendor_name in override:  # synthetic case: simulate what the service returned
            return override[vendor_name]
        return real_get(vendor_name, timeout_seconds)

    with patch.object(httpx.Client, "post", post), patch.object(vendor_client, "get_vendor_risk", get):
        yield counters


def audit_evidence(decision: ProcurementDecision, request: dict[str, Any], override: dict[str, dict] | None) -> list[str]:
    """Re-verify evidence against source files / a direct API call. Returns problems (empty = grounded)."""
    problems: list[str] = []
    emp = {r["employee_id"]: r for r in records(load_employees())}
    bud = {r["department"]: r for r in records(load_budgets())}
    cat = {r["software_id"]: r for r in records(load_software_catalog())}
    po = {r["purchase_id"]: r for r in records(load_purchase_history())}
    ven = {r["vendor_id"]: r for r in records(load_vendors())}
    vname = {r["vendor_name"]: r for r in records(load_vendors())}
    policy_text = (ROOT / "data" / "procurement_policy.md").read_text()
    for item in decision.evidence:
        ref, finding = item.reference, item.finding
        file_part, _, ident = ref.partition("#")
        ok = True
        if item.source == "data/employees.csv":
            ok = (ident in emp and emp[ident]["name"] in finding) if item.evidence_status == "verified" else ident not in emp
        elif item.source == "data/department_budgets.csv":
            ok = ident in bud and f"{int(bud[ident]['available_usd']):,}" in finding
        elif item.source == "data/software_catalog.csv":
            ok = ident in cat and cat[ident]["product_name"] in finding and str(cat[ident]["licensed_seats"]) in finding
        elif item.source == "data/purchase_history.csv":
            ok = ident in po and po[ident]["vendor_name"] in finding
        elif item.source == "data/vendors.csv":
            ok = (ident in ven and ven[ident]["vendor_name"] in finding) if item.evidence_status == "verified" else ident not in vname
        elif item.source == "mock_api":
            vendor = ref.rsplit("/", 1)[-1]
            ok = _audit_vendor_risk(vendor, item, override)
        elif item.source == "data/requests.json":
            ok = ident == request["request_id"] and str(request.get("product_name")) in finding
        elif item.source == "data/procurement_policy.md":
            fragment = " ".join(finding.split()[:12])
            ok = fragment in " ".join(policy_text.split()) or "Instruction-like text" in finding
        else:
            ok = False
        if not ok:
            problems.append(f"{item.source} {ref}: not supported by source")
        if not item.tool:
            problems.append(f"{ref}: no producing tool recorded")
    return problems


def _audit_vendor_risk(vendor: str, item, override: dict[str, dict] | None) -> bool:
    if override and vendor in override:
        record = override[vendor]
        return record["security_review_status"] in item.finding and str(record.get("notes", ""))[:20] in item.finding
    try:
        response = requests.get(f"{vendor_client.os.getenv('VENDOR_RISK_BASE_URL', 'http://127.0.0.1:8001').rstrip('/')}/vendor-risk/{requests.utils.quote(vendor, safe='')}", timeout=3)
    except requests.RequestException:
        return item.evidence_status == "unavailable"
    if response.status_code == 404:
        return item.evidence_status == "missing"
    if response.status_code >= 500:
        return item.evidence_status == "unavailable" and str(response.status_code) in item.finding
    data = response.json()
    return data["security_review_status"] in item.finding and f"last_review_date: {data['last_review_date'] if data['last_review_date'] is not None else 'null'}" in item.finding


# ------------------------------------------------------------------ running
def classify(failures: list[str]) -> dict[str, bool]:
    ok = {dim: True for dim in DIMENSIONS}
    for failure in failures:
        for needle, dim in FAILURE_DIMENSION:
            if needle in failure:
                ok[dim] = False
                break
    return ok


def run_one(case: dict[str, Any], architecture: str, provider: LLMProvider, run_index: int) -> dict[str, Any]:
    request = case_request(case)
    override = case.get("vendor_risk_override")
    row: dict[str, Any] = {"set": case["set"], "case_id": case["case_id"], "request_id": request["request_id"], "category": case.get("category", ""),
                           "architecture": architecture, "run": run_index}
    started = time.perf_counter()
    try:
        with independent_counters(override) as counters:
            decision = evaluate_request(request, architecture=architecture, provider=provider)
        latency_ms = (time.perf_counter() - started) * 1000
        decision = ProcurementDecision.model_validate(decision)
        failures = instructor.evaluate(decision, case["expectations"], request["request_id"])
        dims = classify(failures)
        audit = audit_evidence(decision, request, override)
        dims["evidence_grounded"] = not audit
        dims["human_escalation"] = dims["human_escalation"] and bool(decision.human_handoff and decision.human_handoff.required)
        t, m = decision.telemetry, decision.metadata
        consistent_model = (counters.model_posts == t.llm_calls) if m.llm_status == "live" else counters.model_posts == 0
        consistent_vendor = counters.vendor_attempts == t.tool_call_counts.get("get_vendor_status", 0)
        row.update({
            "automated_pass": not failures and not audit, "failures": " | ".join(failures + [f"AUDIT {a}" for a in audit]),
            **{f"ok_{d}": dims[d] for d in DIMENSIONS},
            "llm_status": m.llm_status, "fallback_reason": m.fallback_reason or "", "latency_ms": round(latency_ms, 1),
            "latency_net_of_waits_ms": round(latency_ms - t.rate_limit_wait_ms, 1), "rate_limit_wait_ms": t.rate_limit_wait_ms,
            "llm_calls": t.llm_calls, "tool_calls": t.tool_calls, "llm_retries": t.llm_retries, "tool_retries": t.tool_retries,
            "failed_llm_calls": t.failed_llm_calls, "failed_tool_calls": t.failed_tool_calls, "guardrail_backfills": t.guardrail_tool_backfills,
            "prompt_tokens": t.prompt_tokens, "completion_tokens": t.completion_tokens, "ungrounded_claims": m.ungrounded_claims,
            "independent_model_posts": counters.model_posts, "independent_vendor_attempts": counters.vendor_attempts,
            "telemetry_consistent": consistent_model and consistent_vendor,
            "signature": json.dumps([decision.recommendation_code, decision.required_approvals, decision.risk_flags, decision.missing_information]),
            "guardrail_notes": " | ".join(m.guardrail_notes),
        })
    except Exception as exc:  # a crash is a failed case, never a skipped one
        row.update({"automated_pass": False, "failures": f"{type(exc).__name__}: {exc}", **{f"ok_{d}": False for d in DIMENSIONS},
                    "llm_status": "crash", "latency_ms": round((time.perf_counter() - started) * 1000, 1)})
    return row


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for arch in sorted({r["architecture"] for r in rows}):
        mine = [r for r in rows if r["architecture"] == arch]
        def mean(key):
            vals = [r[key] for r in mine if isinstance(r.get(key), (int, float))]
            return round(statistics.fmean(vals), 2) if vals else None
        lat = sorted(r["latency_net_of_waits_ms"] for r in mine if "latency_net_of_waits_ms" in r)
        by_case: dict[str, set] = defaultdict(set)
        for r in mine:
            by_case[r["case_id"]].add(r.get("signature"))
        out[arch] = {
            "runs": len(mine), "cases": len({r["case_id"] for r in mine}),
            "automated_pass": sum(bool(r["automated_pass"]) for r in mine),
            **{f"pass_{d}": sum(bool(r.get(f"ok_{d}")) for r in mine) for d in DIMENSIONS},
            "mean_latency_ms": mean("latency_ms"), "mean_latency_net_of_waits_ms": mean("latency_net_of_waits_ms"),
            "median_latency_net_ms": round(statistics.median(lat), 1) if lat else None, "p95_latency_net_ms": round(lat[min(len(lat) - 1, int(0.95 * len(lat)))], 1) if lat else None,
            "mean_llm_calls": mean("llm_calls"), "mean_tool_calls": mean("tool_calls"),
            "mean_prompt_tokens": mean("prompt_tokens"), "mean_completion_tokens": mean("completion_tokens"),
            "failed_llm_calls": sum(r.get("failed_llm_calls", 0) for r in mine), "failed_tool_calls": sum(r.get("failed_tool_calls", 0) for r in mine),
            "guardrail_backfills": sum(r.get("guardrail_backfills", 0) for r in mine), "ungrounded_claims": sum(r.get("ungrounded_claims", 0) for r in mine),
            "llm_status": dict(Counter(r.get("llm_status") for r in mine)),
            "telemetry_consistent": sum(bool(r.get("telemetry_consistent")) for r in mine),
            "unstable_cases": sorted(case for case, sigs in by_case.items() if len(sigs) > 1),
            "failed_runs": [f"{r['case_id']}#{r['run']}: {r['failures'][:160]}" for r in mine if not r["automated_pass"]],
            "category_pass": {c: f"{sum(bool(r['automated_pass']) for r in mine if r['category'] == c)}/{sum(1 for r in mine if r['category'] == c)}" for c in sorted({r['category'] for r in mine})},
        }
    return out


def write_outputs(label: str, rows: list[dict[str, Any]], summary: dict[str, Any], meta: dict[str, Any]) -> list[Path]:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    raw = RESULTS_DIR / f"{label}_raw.csv"
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with raw.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    summary_path = RESULTS_DIR / f"{label}_summary.json"
    summary_path.write_text(json.dumps({"meta": meta, "summary": summary}, indent=2) + "\n")
    md = RESULTS_DIR / f"{label}_comparison.md"
    md.write_text(render_markdown(label, summary, meta))
    return [raw, summary_path, md]


def render_markdown(label: str, summary: dict[str, Any], meta: dict[str, Any]) -> str:
    archs = list(summary)
    names = {"single": "A - single agent", "staged": "B - staged (2 agents)"}
    def line(title, key, fmt=lambda v: v):
        return f"| {title} | " + " | ".join(str(fmt(summary[a][key])) for a in archs) + " |"
    n = {a: summary[a]["runs"] for a in archs}
    lines = [f"# Comparison: {label}", "", f"- Provider mode: **{meta['provider_mode']}** (model: `{meta['model']}`)", f"- Case sets: {', '.join(meta['sets'])}; cases: {meta['cases']}; runs per case: {meta['runs']}",
             f"- Generated: {meta['generated']}", "- Automated assertions use the instructor's `evaluate()`; manual grounding review is reported separately and is **not** included in these numbers.", "",
             "| Metric | " + " | ".join(names.get(a, a) for a in archs) + " |", "|---|" + "---:|" * len(archs),
             line("Runs", "runs"), line("Automated pass (runs)", "automated_pass", lambda v: v)]
    for d in DIMENSIONS:
        lines.append("| " + d.replace("_", " ").capitalize() + " | " + " | ".join(f"{summary[a]['pass_' + d]}/{n[a]}" for a in archs) + " |")
    lines += [line("Mean latency, end-to-end (ms)", "mean_latency_ms"), line("Mean latency, net of rate-limit waits (ms)", "mean_latency_net_of_waits_ms"),
              "| Median net latency (ms) | " + " | ".join(str(summary[a]["median_latency_net_ms"]) for a in archs) + " |",
              "| p95 net latency (ms) | " + " | ".join(str(summary[a]["p95_latency_net_ms"]) for a in archs) + " |",
              line("Mean model calls", "mean_llm_calls"), line("Mean tool calls", "mean_tool_calls"),
              line("Mean prompt tokens", "mean_prompt_tokens"), line("Mean completion tokens", "mean_completion_tokens"),
              line("Failed model calls (total)", "failed_llm_calls"), line("Failed tool calls (total)", "failed_tool_calls"),
              line("Guardrail tool back-fills (total)", "guardrail_backfills"), line("Ungrounded model claims dropped (total)", "ungrounded_claims"),
              line("Model status per run", "llm_status"), line("Telemetry matches independent counts (runs)", "telemetry_consistent"),
              line("Cases with unstable outcomes across runs", "unstable_cases"), "", "## Pass rate by category (automated)", ""]
    cats = sorted({c for a in archs for c in summary[a]["category_pass"]})
    lines += ["| Category | " + " | ".join(names.get(a, a) for a in archs) + " |", "|---|" + "---:|" * len(archs)]
    lines += [f"| {c} | " + " | ".join(summary[a]["category_pass"].get(c, "-") for a in archs) + " |" for c in cats]
    lines += ["", "## Failed runs", ""]
    for a in archs:
        lines.append(f"**{names.get(a, a)}**: " + ("none" if not summary[a]["failed_runs"] else ""))
        lines += [f"- {f}" for f in summary[a]["failed_runs"]]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--provider", choices=["groq", "none"], default="groq", help="groq = live model; none = deterministic policy only (no-LLM floor)")
    parser.add_argument("--architectures", nargs="+", choices=["single", "staged"], default=["single", "staged"])
    parser.add_argument("--sets", nargs="+", choices=["public", "extended"], default=["public", "extended"])
    parser.add_argument("--runs", type=int, default=1, help="repeat every case N times to expose model nondeterminism")
    parser.add_argument("--label", default=None)
    parser.add_argument("--cases", nargs="*", help="restrict to these case IDs")
    args = parser.parse_args()

    cases = [c for c in load_cases(args.sets) if not args.cases or c["case_id"] in args.cases]
    provider: LLMProvider = get_provider() if args.provider == "groq" else NullProvider("--provider none")
    if args.provider == "groq" and isinstance(provider, NullProvider):
        print("No Groq credentials configured (set GROQ_API_KEY_1 in .env). Use --provider none for the deterministic baseline.", file=sys.stderr)
        return 2
    label = args.label or ("live_groq" if args.provider == "groq" else "no_llm_baseline")
    rows: list[dict[str, Any]] = []
    for run in range(1, args.runs + 1):
        for index, case in enumerate(cases):
            order = args.architectures if (index + run) % 2 == 0 else list(reversed(args.architectures))  # alternate order to cancel drift
            for arch in order:
                row = run_one(case, arch, provider, run)
                rows.append(row)
                print(f"[run {run}] {case['case_id']:7} {arch:6} {'PASS' if row['automated_pass'] else 'FAIL'} "
                      f"llm={row.get('llm_calls', '-')} tools={row.get('tool_calls', '-')} {row.get('latency_net_of_waits_ms', '-')}ms {row.get('failures', '')[:100]}", flush=True)
    rows.sort(key=lambda r: (r["run"], r["case_id"], r["architecture"]))
    meta = {"provider_mode": "live-groq" if args.provider == "groq" else "no-llm (deterministic fallback)", "model": getattr(provider, "model", "") or "-",
            "sets": args.sets, "cases": len(cases), "runs": args.runs, "generated": time.strftime("%Y-%m-%d %H:%M:%S %z")}
    summary = summarize(rows)
    paths = write_outputs(label, rows, summary, meta)
    print("\nWrote: " + ", ".join(str(p.relative_to(ROOT)) for p in paths))
    for arch, data in summary.items():
        print(f"{arch}: automated_pass {data['automated_pass']}/{data['runs']}, mean llm calls {data['mean_llm_calls']}, mean tool calls {data['mean_tool_calls']}, mean net latency {data['mean_latency_net_of_waits_ms']} ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
