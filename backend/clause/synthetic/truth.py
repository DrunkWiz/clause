"""Turn a synthetic document's ground truth into the inputs a perfect model
extraction would give the rules. Used by tests and the fake model gateway."""

from __future__ import annotations

import json
from pathlib import Path

from clause.rules.notice import ELEMENT_IDS

SYNTHETIC_DIR = Path(__file__).resolve().parents[3] / "data" / "synthetic"


def load_truth(doc_id: str) -> dict:
    return json.loads((SYNTHETIC_DIR / f"{doc_id}.truth.json").read_text(encoding="utf-8"))


def citation(truth: dict, tag: str) -> dict:
    t = truth["tags"][tag]
    return {"doc": truth["doc_id"], "clause_id": t["clause_id"], "quote": t["quote"]}


def notice_findings(truth: dict) -> list[dict]:
    """One finding per notice element present in the letter."""
    return [
        {"element": tag, "text": f"The letter includes this element: {tag.replace('_', ' ')}.", "citations": [citation(truth, tag)]}
        for tag in truth["tags"]
        if tag in ELEMENT_IDS
    ]


def eob_lines(truth: dict) -> list[dict]:
    return [
        {"group": l["group"], "code": l["code"], "amount": l["amount"], "citation": citation(truth, l["tag"])}
        for l in truth.get("lines", [])
    ]


def patient_owes(truth: dict) -> dict | None:
    p = truth.get("patient_owes")
    return {"amount": p["amount"], "citation": citation(truth, p["tag"])} if p else None
