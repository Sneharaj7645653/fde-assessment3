"""Entry points: ``handle_request`` / ``evaluate_request`` (the starter's public interface).

Pipeline for every architecture:
  1. an agent (A: one, B: two stages) calls tools and returns *validated, grounded* interpretation signals;
  2. code re-runs the deterministic policy engine with those signals (they can only add caution);
  3. code composes the structured decision (evidence only from tool results) and the human handoff.

If the model is unavailable or misbehaves, step 1 is replaced by plain tool execution and the decision
is marked ``llm_status = fallback|disabled`` - policy output is unchanged, and the reviewer is told that
no AI interpretation took place.
"""
from __future__ import annotations

from typing import Any

from src import policy
from src.agents import AgentOutcome, run_single, run_staged
from src.composer import (
    build_evidence, build_handoff, deterministic_rationale, next_step, recommendation_text,
)
from src.contracts import Architecture, ProcurementDecision, RunMetadata
from src.data_access import get_request
from src.instrumentation import RunRecorder
from src.llm import LLMError, LLMProvider, get_provider
from src.tools import ToolExecutor

_default_provider: LLMProvider | None = None


def default_provider() -> LLMProvider:
    global _default_provider
    if _default_provider is None:
        _default_provider = get_provider()
    return _default_provider


def reset_default_provider() -> None:
    global _default_provider
    _default_provider = None


def evaluate_request(request: dict[str, Any], architecture: Architecture = "single", provider: LLMProvider | None = None) -> ProcurementDecision:
    if architecture not in ("single", "staged"):
        raise ValueError(f"Unknown architecture: {architecture!r}")
    provider = provider or default_provider()
    recorder = RunRecorder()
    executor = ToolExecutor(request, recorder)
    runner = run_single if architecture == "single" else run_staged
    agents = ["review_agent"] if architecture == "single" else ["evidence_analyst", "independent_reviewer"]

    try:
        outcome = runner(request, provider, recorder, executor)
    except Exception as exc:  # model/provider/validation failure -> deterministic fallback, never a silent success
        kind = exc.kind if isinstance(exc, LLMError) else f"internal_error:{type(exc).__name__}"
        reason = exc.message if isinstance(exc, LLMError) else str(exc)[:200]
        executor.ensure_all(caller="fallback")
        outcome = AgentOutcome(
            executor=executor, agents=agents,
            llm_status="disabled" if kind == "missing_credentials" else "fallback",
            fallback_reason=f"{kind}: {reason}",
            notes=["Model unavailable; decision uses deterministic tools and policy only"],
        )

    if executor.duplicate_calls_suppressed:
        outcome.notes.append(f"Suppressed {executor.duplicate_calls_suppressed} duplicate tool call(s); cached results were reused")
    g = executor.gathered
    result = policy.evaluate(g, outcome.signals)
    evidence = build_evidence(g, result)
    ai_available = outcome.llm_status in {"live", "mock"}
    rationale = outcome.rationale or deterministic_rationale(g, result)
    if not ai_available:
        rationale += " (AI interpretation unavailable: this explanation is a deterministic template.)"

    return ProcurementDecision(
        request_id=policy.text(request.get("request_id") or "UNKNOWN"),
        recommendation=recommendation_text(result.recommendation_code),
        recommendation_code=result.recommendation_code,
        evidence=evidence,
        required_approvals=result.required_approvals,
        missing_information=result.missing_information,
        risk_flags=sorted(result.risk_flags),
        next_step=next_step(g, result),
        human_review_required=True,
        telemetry=recorder.to_telemetry(),
        rationale=rationale,
        human_handoff=build_handoff(g, result, ai_available),
        ai_assessment=outcome.assessment,
        metadata=RunMetadata(
            architecture=architecture, agents=outcome.agents, llm_status=outcome.llm_status,
            provider=provider.name if ai_available else None, model=provider.model if ai_available else None,
            fallback_reason=outcome.fallback_reason, guardrail_notes=outcome.notes, ungrounded_claims=outcome.ungrounded),
    )


def handle_request(request_id: str, architecture: Architecture = "single", provider: LLMProvider | None = None) -> ProcurementDecision:
    return evaluate_request(get_request(request_id), architecture=architecture, provider=provider)
