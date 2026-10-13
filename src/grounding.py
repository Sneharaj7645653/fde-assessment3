"""Checks that model-written content is traceable to tool results. Failures are counted, not trusted."""
from __future__ import annotations

import re
from typing import Iterable

from src.contracts import EvidenceItem

_MONEY = re.compile(r"\$\s?\d[\d,]*(?:\.\d+)?")
_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_RECORD_ID = re.compile(r"\b(?:SW\d{3}|PO-\d{4}|V\d{3}|E\d{3}|REQ-\d{4})\b")
_APPROVAL_CLAIM = re.compile(
    r"(has been|have been|is hereby|is now|was|were) (approved|purchased|authori[sz]ed|signed off)|"
    r"\b(i|we) (have |will |am going to )?(approve|approved|purchase|purchased|authori[sz]e|authorized)\b|"
    r"\b(go ahead and|proceed to) (buy|purchase)\b|purchase (is |has been )?(complete|completed|approved)",
    re.IGNORECASE,
)


def normalize(value: str) -> str:
    return " ".join(str(value).split()).casefold()


def quote_grounded(quote: str | None, texts: Iterable[str], min_chars: int = 6) -> bool:
    """A quote is grounded only if it appears verbatim (whitespace/case-insensitive) in a supplied business text."""
    needle = normalize(quote or "")
    if len(needle) < min_chars:
        return False
    return any(needle in normalize(t) for t in texts)


def _tokens(pattern: re.Pattern[str], value: str) -> set[str]:
    return {re.sub(r"[\s,]", "", m.group(0)) for m in pattern.finditer(value)}


def rationale_violations(rationale: str, evidence: list[EvidenceItem], request_text: str = "", max_chars: int = 900) -> list[str]:
    """Reasons a model-written rationale must be rejected (empty list = acceptable)."""
    problems: list[str] = []
    corpus = " ".join(f"{e.reference} {e.finding}" for e in evidence) + " " + request_text
    if not rationale or not rationale.strip():
        return ["empty rationale"]
    if len(rationale) > max_chars:
        problems.append("rationale too long")
    for pattern, label in ((_MONEY, "dollar figure"), (_DATE, "date"), (_RECORD_ID, "record id")):
        unknown = _tokens(pattern, rationale) - _tokens(pattern, corpus)
        if unknown:
            problems.append(f"ungrounded {label}: {sorted(unknown)[0]}")
    if _APPROVAL_CLAIM.search(rationale):
        problems.append("claims an approval or purchase")
    return problems
