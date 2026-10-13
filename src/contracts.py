from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

APPROVAL_NAMES = frozenset({
    "Manager",
    "Department Head",
    "Procurement",
    "Finance",
    "CFO",
    "Security",
    "Privacy",
    "Legal",
})

RISK_FLAG_NAMES = frozenset({
    "existing_tool_overlap",
    "budget_insufficient",
    "security_review_required",
    "privacy_review_required",
    "legal_review_required",
    "vendor_review_expired",
    "conflicting_vendor_evidence",
    "vendor_risk_unavailable",
    "prompt_injection_detected",
    "missing_information",
    "budget_data_unverified",
})

RECOMMENDATION_CODES = frozenset({
    "proceed_to_required_approvals",
    "request_clarification",
    "route_for_budget_exception",
    "route_for_manual_review",
})


class EvidenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    source: str = Field(description="Tool or data source name")
    finding: str = Field(description="Concise factual finding")
    reference: str = Field(description="Exact record ID, policy section, or endpoint")
    evidence_status: Literal["verified", "missing", "expired", "unknown", "unavailable", "conflicting"] | None = None
    tool: str | None = Field(default=None, description="Tool whose result this item was built from (solution addition)")

    @field_validator("source", "finding")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Value must be a non-empty string")
        return value.strip()


class RunTelemetry(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    llm_calls: int = Field(ge=0, description="Observed LLM request attempts, including retries")
    tool_calls: int = Field(ge=0, description="Observed tool dispatch attempts, including retries")
    llm_retries: int = Field(ge=0)
    tool_retries: int = Field(ge=0)
    failed_llm_calls: int = Field(ge=0)
    failed_tool_calls: int = Field(ge=0)
    timeouts: int = Field(ge=0, description="Timed-out attempts; included in failed call counts")
    tool_errors: int = Field(ge=0, description="Non-timeout failed tool attempts")
    tool_names: list[str] = Field(description="Unique tool identifiers observed during the run")
    # Solution additions: all values are measured by src.instrumentation.RunRecorder.
    llm_latency_ms: float = Field(default=0.0, ge=0, description="Time spent inside provider calls, excluding rate-limit waits")
    tool_latency_ms: float = Field(default=0.0, ge=0)
    rate_limit_wait_ms: float = Field(default=0.0, ge=0, description="Time deliberately waited for provider rate limits")
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    guardrail_tool_backfills: int = Field(default=0, ge=0, description="Mandatory tool calls the code had to run because the agent did not")
    rejected_tool_calls: int = Field(default=0, ge=0, description="Dispatches refused before execution (bad arguments, unknown tool, wrong request_id); included in tool_calls and failed_tool_calls")
    tool_call_counts: dict[str, int] = Field(default_factory=dict, description="Executed attempts per tool (rejected dispatches excluded)")

    @field_validator("tool_names")
    @classmethod
    def _validate_tool_names(cls, value: list[str]) -> list[str]:
        normalized = [item.strip() for item in value]
        if any(not item for item in normalized):
            raise ValueError("Tool names cannot be blank")
        if len({item.casefold() for item in normalized}) != len(normalized):
            raise ValueError("Tool names must be unique")
        return normalized

    @model_validator(mode="after")
    def _validate_counts(self) -> RunTelemetry:
        if self.llm_retries > self.llm_calls or self.failed_llm_calls > self.llm_calls:
            raise ValueError("LLM retries and failures cannot exceed LLM attempts")
        if self.tool_retries > self.tool_calls or self.failed_tool_calls > self.tool_calls:
            raise ValueError("Tool retries and failures cannot exceed tool attempts")
        if self.timeouts > self.failed_llm_calls + self.failed_tool_calls:
            raise ValueError("Timeouts must be included in failed call counts")
        if self.tool_errors > self.failed_tool_calls:
            raise ValueError("Tool errors cannot exceed failed tool attempts")
        return self


class HumanHandoff(BaseModel):
    """Who must act next. The copilot never approves, purchases, or grants exceptions itself."""

    model_config = ConfigDict(extra="forbid", strict=True)

    required: bool
    reasons: list[str]
    escalate_to: list[str]
    authority_note: str


class AIAssessment(BaseModel):
    """Validated, grounded interpretation produced by the model (never policy)."""

    model_config = ConfigDict(extra="forbid", strict=True)

    justification_adequate: bool | None = None
    justification_note: str | None = None
    injection_suspected: bool = False
    injection_quote: str | None = None
    overlap_view: Literal["yes", "partial", "no", "unclear"] | None = None
    overlap_note: str | None = None
    overlap_refs: list[str] = Field(default_factory=list)
    clarifying_questions: list[str] = Field(default_factory=list)


class RunMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    architecture: Literal["single", "staged"]
    agents: list[str] = Field(description="Agents/stages that executed, in order")
    llm_status: Literal["live", "mock", "fallback", "disabled"] = Field(
        description="live = real provider answered; mock = scripted test provider; "
        "fallback = provider failed and deterministic policy output was used; disabled = no provider configured"
    )
    provider: str | None = None
    model: str | None = None
    fallback_reason: str | None = None
    guardrail_notes: list[str] = Field(default_factory=list, description="Places where deterministic code overrode, ignored, or rejected model output")
    ungrounded_claims: int = Field(default=0, ge=0, description="Model claims (quotes, citations, figures) that did not match tool results and were dropped")


class ProcurementDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    request_id: str = Field(description="Unique request identifier")
    recommendation: str = Field(description="Human-facing recommendation")
    recommendation_code: Literal[
        "proceed_to_required_approvals",
        "request_clarification",
        "route_for_budget_exception",
        "route_for_manual_review",
    ] = Field(description="Machine-readable recommendation code")
    evidence: list[EvidenceItem]
    required_approvals: list[Literal[
        "Manager",
        "Department Head",
        "Procurement",
        "Finance",
        "CFO",
        "Security",
        "Privacy",
        "Legal",
    ]]
    missing_information: list[str]
    risk_flags: list[Literal[
        "existing_tool_overlap",
        "budget_insufficient",
        "security_review_required",
        "privacy_review_required",
        "legal_review_required",
        "vendor_review_expired",
        "conflicting_vendor_evidence",
        "vendor_risk_unavailable",
        "prompt_injection_detected",
        "missing_information",
        "budget_data_unverified",
    ]]
    next_step: str = Field(description="Specific next action for a human reviewer")
    human_review_required: bool
    telemetry: RunTelemetry | None = None
    # Solution additions (all optional so the instructor's minimal contract still validates).
    rationale: str | None = Field(default=None, description="Short explanation for reviewers (model-written when live, template otherwise)")
    human_handoff: HumanHandoff | None = None
    ai_assessment: AIAssessment | None = None
    metadata: RunMetadata | None = None

    @field_validator("request_id", "recommendation", "next_step")
    @classmethod
    def _non_empty_string(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Field must be a non-empty string")
        return value.strip()

    @field_validator("missing_information")
    @classmethod
    def _validate_missing_information(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for item in value:
            cleaned = item.strip()
            if not cleaned:
                raise ValueError("Missing information values cannot be blank")
            normalized.append(cleaned)
        if len({item.casefold() for item in normalized}) != len(normalized):
            raise ValueError("Missing-information values must be unique")
        return normalized

    @field_validator("required_approvals", "risk_flags")
    @classmethod
    def _validate_unique_values(cls, value: list[str]) -> list[str]:
        if len({item.casefold() for item in value}) != len(value):
            raise ValueError("Approval and risk-flag values must be unique")
        return value


Architecture = Literal["single", "staged"]
