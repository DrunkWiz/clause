"""The grounding verifier.

The model returns claims, each with citations `{doc, clause_id, quote}`. This
module checks every citation against the clause index with plain code. A claim
is supported only if it has at least one citation, every citation verifies,
and every money amount, percentage and day count in its text appears in one of
its quotes. Anything else is unsupported and must never be shown as fact.

What this proves: each quote really is in the clause it cites. What it does
not prove: that the claim follows from the quote.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from clause.index.model import BBox, Clause, ClauseIndex
from clause.verify.normalise import find_words, normalise, numeric_facts, word_count

MIN_QUOTE_WORDS = 4

# Citation failure reasons
MALFORMED = "malformed"
EMPTY_QUOTE = "empty_quote"
UNKNOWN_CLAUSE = "unknown_clause"
DOC_MISMATCH = "doc_mismatch"
QUOTE_TOO_SHORT = "quote_too_short"
QUOTE_NOT_IN_CLAUSE = "quote_not_in_clause"

# Claim failure reasons
NO_CITATIONS = "no_citations"
CITATION_FAILED = "citation_failed"
NUMBER_NOT_IN_QUOTE = "number_not_in_quote"

_ELLIPSIS = re.compile(r"\.\s*\.\s*\.|…")


@dataclass(frozen=True)
class Highlight:
    page: int
    bbox: BBox


@dataclass(frozen=True)
class CitationResult:
    doc: object
    clause_id: object
    quote: object
    ok: bool
    reason: str | None = None
    spans: tuple[tuple[int, int], ...] = ()  # offsets into the clause's original text
    highlights: tuple[Highlight, ...] = ()

    def to_dict(self) -> dict:
        return {
            "doc": self.doc,
            "clause_id": self.clause_id,
            "quote": self.quote,
            "ok": self.ok,
            "reason": self.reason,
            "spans": [list(s) for s in self.spans],
            "highlights": [{"page": h.page, "bbox": list(h.bbox)} for h in self.highlights],
        }


@dataclass(frozen=True)
class ClaimResult:
    text: object
    supported: bool
    reason: str | None
    citations: tuple[CitationResult, ...] = ()
    missing_numbers: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "supported": self.supported,
            "reason": self.reason,
            "citations": [c.to_dict() for c in self.citations],
            "missing_numbers": list(self.missing_numbers),
        }


@dataclass(frozen=True)
class Report:
    claims: tuple[ClaimResult, ...] = ()
    error: str | None = None  # set when the whole response could not be read

    @property
    def supported(self) -> tuple[ClaimResult, ...]:
        return tuple(c for c in self.claims if c.supported)

    @property
    def unsupported(self) -> tuple[ClaimResult, ...]:
        return tuple(c for c in self.claims if not c.supported)

    @property
    def rejection_rate(self) -> float:
        return len(self.unsupported) / len(self.claims) if self.claims else 0.0

    def to_dict(self) -> dict:
        return {
            "claims": [c.to_dict() for c in self.claims],
            "error": self.error,
            "supported": len(self.supported),
            "unsupported": len(self.unsupported),
            "rejection_rate": self.rejection_rate,
        }


def verify(raw, index: ClauseIndex) -> Report:
    """Verify a model response: a JSON string, a list of claims, or
    `{"claims": [...]}`. Never raises on bad input."""
    if isinstance(raw, (str, bytes)):
        try:
            raw = json.loads(raw)
        except (ValueError, TypeError):
            return Report(error=MALFORMED)
    if isinstance(raw, dict):
        raw = raw.get("claims")
    if not isinstance(raw, list):
        return Report(error=MALFORMED)
    return Report(claims=tuple(verify_claim(c, index) for c in raw))


def verify_claim(claim, index: ClauseIndex) -> ClaimResult:
    if not isinstance(claim, dict):
        return ClaimResult(text=None, supported=False, reason=MALFORMED)
    text = claim.get("text")
    citations = claim.get("citations")
    if not isinstance(text, str) or not text.strip():
        return ClaimResult(text=text, supported=False, reason=MALFORMED)
    if citations is None or citations == []:
        return ClaimResult(text=text, supported=False, reason=NO_CITATIONS)
    if not isinstance(citations, list):
        return ClaimResult(text=text, supported=False, reason=MALFORMED)

    results = tuple(verify_citation(c, index) for c in citations)
    if not all(r.ok for r in results):
        return ClaimResult(text=text, supported=False, reason=CITATION_FAILED, citations=results)

    quoted = " ".join(normalise(r.quote)[0] for r in results)
    missing = numeric_facts(normalise(text)[0]) - numeric_facts(quoted)
    if missing:
        return ClaimResult(
            text=text,
            supported=False,
            reason=NUMBER_NOT_IN_QUOTE,
            citations=results,
            missing_numbers=tuple(sorted(_describe(f) for f in missing)),
        )
    return ClaimResult(text=text, supported=True, reason=None, citations=results)


def verify_citation(cit, index: ClauseIndex) -> CitationResult:
    if not isinstance(cit, dict):
        return CitationResult(doc=None, clause_id=None, quote=None, ok=False, reason=MALFORMED)
    doc, clause_id, quote = cit.get("doc"), cit.get("clause_id"), cit.get("quote")

    def fail(reason: str) -> CitationResult:
        return CitationResult(doc=doc, clause_id=clause_id, quote=quote, ok=False, reason=reason)

    if not all(isinstance(v, str) for v in (doc, clause_id, quote)):
        return fail(MALFORMED)
    if not normalise(quote)[0]:
        return fail(EMPTY_QUOTE)
    clause = index.get(clause_id)
    if clause is None:
        return fail(UNKNOWN_CLAUSE)
    if clause.doc_id != doc:
        return fail(DOC_MISMATCH)

    clause_norm, offsets = normalise(clause.text)
    fragments = [f for f in (normalise(p)[0] for p in _ELLIPSIS.split(quote)) if f]
    whole_clause = len(fragments) == 1 and fragments[0] == clause_norm
    if not whole_clause and any(word_count(f) < MIN_QUOTE_WORDS for f in fragments):
        return fail(QUOTE_TOO_SHORT)

    spans = []
    pos = 0
    for f in fragments:
        at = find_words(clause_norm, f, pos)
        if at == -1:
            return fail(QUOTE_NOT_IN_CLAUSE)
        end = at + len(f)
        spans.append((offsets[at], offsets[end - 1] + 1))
        pos = end
    return CitationResult(
        doc=doc,
        clause_id=clause_id,
        quote=quote,
        ok=True,
        spans=tuple(spans),
        highlights=_highlights(clause, spans),
    )


def _highlights(clause: Clause, spans: list[tuple[int, int]]) -> tuple[Highlight, ...]:
    if not clause.lines:
        return (Highlight(clause.page, clause.bbox),)
    out: list[Highlight] = []
    for line in clause.lines:
        if any(s < line.end and e > line.start for s, e in spans):
            h = Highlight(clause.page, line.bbox)
            if h not in out:
                out.append(h)
    return tuple(out)


def _describe(fact: tuple[str, str]) -> str:
    kind, num = fact
    if kind == "money":
        whole, _, cents = num.partition(".")
        return f"${int(whole):,}" + (f".{cents.ljust(2, '0')}" if cents else "")
    return {"percent": f"{num}%", "days": f"{num} days", "hours": f"{num} hours"}.get(kind, num)
