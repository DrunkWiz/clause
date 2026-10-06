"""Shared pieces for the rules.

Rules are plain code. Their output uses the same claim shape as the model's,
`{text, citations: [{doc, clause_id, quote}]}`, citing regulation text in the
regulations index, so it goes through the same grounding verifier. A rule
claim is marked `source: "rule"`.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from clause.index.model import ClauseIndex
from clause.verify.normalise import find_words, norm

REGS_INDEX = Path(__file__).resolve().parents[3] / "data" / "regs" / "regs_index.json"


@lru_cache(maxsize=1)
def regs() -> ClauseIndex:
    return ClauseIndex.from_json(REGS_INDEX.read_text(encoding="utf-8"))


@dataclass(frozen=True)
class Ref:
    """A regulation paragraph and the exact words a rule relies on."""

    label: str  # e.g. "45 CFR 147.136(d)(2)(i)"
    quote: str

    def citation(self, index: ClauseIndex | None = None) -> dict:
        """The citation for this reference: the clause with this label that
        contains the quote. Several clauses can share a label (the holiday
        lines of 5 U.S.C. 6103(a)); the quote picks the right one. If none
        contains it, the first labelled clause is cited and the verifier
        will reject the claim, which is what the rule-table tests check."""
        index = index or regs()
        clauses = index.by_label(self.label)
        if not clauses:
            raise KeyError(f"no regulation paragraph labelled {self.label!r}")
        q = norm(self.quote)
        clause = next((c for c in clauses if find_words(norm(c.text), q) != -1), clauses[0])
        return {"doc": clause.doc_id, "clause_id": clause.clause_id, "quote": self.quote, "label": self.label}


def rule_claim(rule_id: str, text: str, *refs: Ref | dict) -> dict:
    """A rule's claim. `refs` are regulation references, or citations into
    the person's own documents (e.g. the EOB line an amount came from), so
    that every number in `text` can be checked against a quote."""
    return {
        "text": text,
        "citations": [r.citation() if isinstance(r, Ref) else dict(r) for r in refs],
        "source": "rule",
        "rule_id": rule_id,
    }
