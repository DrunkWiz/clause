"""Generate the synthetic denial letters and EOBs.

    python scripts/make_synthetic.py

Writes data/synthetic/<doc_id>.pdf and <doc_id>.truth.json, and the clause
index to data/indexes/<doc_id>.json. Deterministic: rerunning gives the same
bytes.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from clause.index.model import ClauseIndex  # noqa: E402
from clause.synthetic.documents import ALL  # noqa: E402
from clause.synthetic.generate import build  # noqa: E402

OUT = ROOT / "data" / "synthetic"
INDEXES = ROOT / "data" / "indexes"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for doc in ALL:
        pdf, document, clauses, truth = build(doc)
        (OUT / f"{doc.doc_id}.pdf").write_bytes(pdf)
        (OUT / f"{doc.doc_id}.truth.json").write_text(json.dumps(truth, indent=1, ensure_ascii=False), encoding="utf-8", newline="\n")
        idx = ClauseIndex()
        idx.add_document(document, clauses)
        (INDEXES / f"{doc.doc_id}.json").write_text(idx.to_json(), encoding="utf-8", newline="\n")
        print(f"{doc.doc_id}: {len(document.page_sizes)} pages, {len(clauses)} clauses, {len(truth['tags'])} tags")


if __name__ == "__main__":
    main()
