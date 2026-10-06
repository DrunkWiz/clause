"""Build clause indexes from PDFs and print what came out, for checking by eye.

    python scripts/build_index.py data/plans/*.pdf --out data/indexes
    python scripts/build_index.py data/plans/kaiser-ga-hmo-eoc-2026.pdf --dump 31
"""

from __future__ import annotations

import argparse
import collections
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from clause.index.extract import extract_pdf  # noqa: E402
from clause.index.model import ClauseIndex  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdfs", nargs="+")
    ap.add_argument("--out", help="directory to write <doc_id>.json into")
    ap.add_argument("--dump", type=int, help="print every clause on this page")
    args = ap.parse_args()

    for path in map(Path, args.pdfs):
        t = time.perf_counter()
        doc, clauses = extract_pdf(path.read_bytes(), path.name)
        secs = time.perf_counter() - t
        kinds = collections.Counter(c.kind for c in clauses)
        lengths = sorted(len(c.text) for c in clauses)
        print(
            f"{doc.doc_id}: {len(doc.page_sizes)} pages, {len(clauses)} clauses {dict(kinds)}, "
            f"median {lengths[len(lengths) // 2] if lengths else 0} chars, longest {lengths[-1] if lengths else 0}, {secs:.1f}s"
        )
        for c in sorted(clauses, key=lambda c: -len(c.text))[:3]:
            print(f"  longest: {c.clause_id} ({c.kind}, {len(c.text)} chars, {len(c.lines)} lines)")
        if args.dump:
            for c in clauses:
                if c.page == args.dump:
                    print(f"  [{c.clause_id}] ({c.kind}) {c.text!r}"[:400])
        if args.out:
            idx = ClauseIndex()
            idx.add_document(doc, clauses)
            out = Path(args.out) / f"{doc.doc_id}.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(idx.to_json(), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
