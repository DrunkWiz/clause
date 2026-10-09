"""Render the synthetic documents to PDF, index them with the normal
extractor, and record where each tagged block landed (ground truth).

The ground truth is what a perfect extraction would return: for each tag, the
clause it is in and a quote from it. Tests and the fake model gateway use it.
"""

from __future__ import annotations

from clause.index.extract import extract_pdf
from clause.index.model import Clause, Document
from clause.synthetic.documents import HEADER, P, SyntheticDoc, T
from clause.synthetic.pdfwrite import Flow
from clause.verify.normalise import find_words, norm

QUOTE_WORDS = 8


def render(doc: SyntheticDoc) -> bytes:
    f = Flow(HEADER, f"Synthetic · {doc.doc_id}")
    for b in doc.blocks:
        if isinstance(b, P):
            f.para(b.text, size=b.size, font="bold" if b.bold else "regular", after=10 if b.size > 10 else 6)
        elif isinstance(b, T):
            f.table([list(r) for r in b.rows], list(b.widths))
    return f.to_bytes()


def _quote_for(text: str) -> str:
    return " ".join(text.split()[:QUOTE_WORDS])


def _locate(clauses: list[Clause], quote: str) -> Clause:
    q = norm(quote)
    for c in clauses:
        if find_words(norm(c.text), q) != -1:
            return c
    raise LookupError(f"tagged text not found in extracted clauses: {quote!r}")


def build(doc: SyntheticDoc) -> tuple[bytes, Document, list[Clause], dict]:
    pdf = render(doc)
    document, clauses = extract_pdf(pdf, f"{doc.doc_id}.pdf", doc.doc_id)
    tags: dict[str, dict] = {}
    for b in doc.blocks:
        if isinstance(b, P) and b.tag:
            quote = _quote_for(b.text)
            c = _locate(clauses, quote)
            tags[b.tag] = {"clause_id": c.clause_id, "quote": quote, "text": b.text}
        elif isinstance(b, T):
            for row, tag in zip(b.rows, b.tags):
                if tag:
                    quote = " | ".join(cell for cell in row if cell)
                    c = _locate(clauses, quote)
                    tags[tag] = {"clause_id": c.clause_id, "quote": quote, "text": quote}
    truth = {
        "doc_id": doc.doc_id,
        "kind": doc.kind,
        "title": doc.title,
        "plan_docs": list(doc.plan_docs),
        "synthetic": True,
        **doc.truth,
        "tags": tags,
    }
    return pdf, document, clauses, truth
