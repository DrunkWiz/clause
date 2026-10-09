"""The bundled demo cases: a synthetic letter or EOB plus the real plan
documents it relates to, loaded from data/indexes."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from clause.index.model import ClauseIndex
from clause.synthetic.documents import ALL

INDEXES = Path(__file__).resolve().parents[3] / "data" / "indexes"

CASES = {d.doc_id: d for d in ALL}


@lru_cache(maxsize=None)
def load_index(doc_id: str) -> ClauseIndex:
    return ClauseIndex.from_json((INDEXES / f"{doc_id}.json").read_text(encoding="utf-8"))


def case_indexes(case_id: str) -> tuple[ClauseIndex, ClauseIndex]:
    """(the synthetic document's index, the merged plan index)."""
    d = CASES[case_id]
    plan = ClauseIndex()
    for p in d.plan_docs:
        plan = plan.merge(load_index(p))
    return load_index(case_id), plan


def list_cases() -> list[dict]:
    return [{"id": d.doc_id, "kind": d.kind, "title": d.title, "plan_docs": list(d.plan_docs)} for d in ALL]
