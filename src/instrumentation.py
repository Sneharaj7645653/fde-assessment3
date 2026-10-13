"""Measured run telemetry.

Every provider attempt and every tool dispatch is recorded here as it happens;
``RunRecorder.to_telemetry`` converts the log into the output contract's
``RunTelemetry``. Nothing in this module is hardcoded per architecture.
"""
from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass, field

from src.contracts import RunTelemetry


@dataclass
class ToolCallRecord:
    name: str
    caller: str
    ok: bool
    status: str
    latency_ms: float
    is_retry: bool = False
    timed_out: bool = False
    error: str | None = None


@dataclass
class LLMCallRecord:
    agent: str
    provider: str
    model: str
    ok: bool
    latency_ms: float
    wait_ms: float = 0.0
    is_retry: bool = False
    timed_out: bool = False
    error_kind: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass
class RunRecorder:
    started: float = field(default_factory=time.perf_counter)
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    llm_calls: list[LLMCallRecord] = field(default_factory=list)
    wait_ms: float = 0.0
    backfills: int = 0

    def record_tool(self, **kwargs) -> ToolCallRecord:
        record = ToolCallRecord(**kwargs)
        self.tool_calls.append(record)
        if record.caller == "guardrail":
            self.backfills += 1
        return record

    def record_llm(self, **kwargs) -> LLMCallRecord:
        record = LLMCallRecord(**kwargs)
        self.llm_calls.append(record)
        return record

    def add_wait(self, ms: float) -> None:
        self.wait_ms += ms

    @property
    def elapsed_ms(self) -> float:
        return (time.perf_counter() - self.started) * 1000

    def to_telemetry(self) -> RunTelemetry:
        failed_llm = [c for c in self.llm_calls if not c.ok]
        failed_tool = [c for c in self.tool_calls if not c.ok]
        names: list[str] = []
        for call in self.tool_calls:
            if call.name.casefold() not in {n.casefold() for n in names}:
                names.append(call.name)
        return RunTelemetry(
            llm_calls=len(self.llm_calls),
            tool_calls=len(self.tool_calls),
            llm_retries=sum(c.is_retry for c in self.llm_calls),
            tool_retries=sum(c.is_retry for c in self.tool_calls),
            failed_llm_calls=len(failed_llm),
            failed_tool_calls=len(failed_tool),
            timeouts=sum(c.timed_out for c in failed_llm) + sum(c.timed_out for c in failed_tool),
            tool_errors=sum(not c.timed_out for c in failed_tool),
            tool_names=names,
            llm_latency_ms=round(sum(c.latency_ms for c in self.llm_calls), 1),
            tool_latency_ms=round(sum(c.latency_ms for c in self.tool_calls), 1),
            rate_limit_wait_ms=round(self.wait_ms, 1),
            prompt_tokens=sum(c.prompt_tokens for c in self.llm_calls),
            completion_tokens=sum(c.completion_tokens for c in self.llm_calls),
            guardrail_tool_backfills=self.backfills,
            rejected_tool_calls=sum(c.status == "rejected" for c in self.tool_calls),
            tool_call_counts=dict(Counter(c.name for c in self.tool_calls if c.status != "rejected")),
        )
