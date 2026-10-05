"""The clause index: every paragraph of every document, with where it sits on the page.

Coordinates are PDF points with the origin at the top left of the page, as
(x0, top, x1, bottom). Everything downstream reads from this structure.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

EXTRACTOR_VERSION = "1"

# Clause kinds
PARAGRAPH = "paragraph"
TABLE_ROW = "table_row"
PAGE = "page"  # fallback when a page does not segment cleanly

BBox = tuple[float, float, float, float]


def make_clause_id(doc_id: str, page: int, n: int) -> str:
    """`<doc_id>#p<page>.<n>`, with page and n both 1-based."""
    return f"{doc_id}#p{page}.{n}"


@dataclass(frozen=True)
class Line:
    """One visual line (or table cell) of a clause, as offsets into its text."""

    bbox: BBox
    start: int
    end: int


@dataclass(frozen=True)
class Clause:
    clause_id: str
    doc_id: str
    page: int
    bbox: BBox
    text: str
    lines: tuple[Line, ...] = ()
    kind: str = PARAGRAPH

    def to_dict(self) -> dict:
        return {
            "clause_id": self.clause_id,
            "doc_id": self.doc_id,
            "page": self.page,
            "bbox": list(self.bbox),
            "text": self.text,
            "lines": [{"bbox": list(l.bbox), "start": l.start, "end": l.end} for l in self.lines],
            "kind": self.kind,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Clause":
        return cls(
            clause_id=d["clause_id"],
            doc_id=d["doc_id"],
            page=int(d["page"]),
            bbox=_bbox(d["bbox"]),
            text=d["text"],
            lines=tuple(Line(_bbox(l["bbox"]), int(l["start"]), int(l["end"])) for l in d.get("lines", [])),
            kind=d.get("kind", PARAGRAPH),
        )


@dataclass(frozen=True)
class Document:
    doc_id: str
    filename: str
    sha256: str
    page_sizes: tuple[tuple[float, float], ...]  # (width, height) per page

    def to_dict(self) -> dict:
        return {
            "doc_id": self.doc_id,
            "filename": self.filename,
            "sha256": self.sha256,
            "page_sizes": [list(s) for s in self.page_sizes],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Document":
        return cls(
            doc_id=d["doc_id"],
            filename=d["filename"],
            sha256=d["sha256"],
            page_sizes=tuple((float(w), float(h)) for w, h in d["page_sizes"]),
        )


@dataclass
class ClauseIndex:
    documents: dict[str, Document] = field(default_factory=dict)
    clauses: dict[str, Clause] = field(default_factory=dict)
    extractor_version: str = EXTRACTOR_VERSION

    def add_document(self, doc: Document, clauses: list[Clause]) -> None:
        if doc.doc_id in self.documents:
            raise ValueError(f"duplicate doc_id: {doc.doc_id}")
        self.documents[doc.doc_id] = doc
        for c in clauses:
            if c.doc_id != doc.doc_id:
                raise ValueError(f"clause {c.clause_id} belongs to {c.doc_id}, not {doc.doc_id}")
            if c.clause_id in self.clauses:
                raise ValueError(f"duplicate clause_id: {c.clause_id}")
            self.clauses[c.clause_id] = c

    def get(self, clause_id: str) -> Clause | None:
        return self.clauses.get(clause_id)

    def merge(self, other: "ClauseIndex") -> "ClauseIndex":
        out = ClauseIndex(extractor_version=self.extractor_version)
        for idx in (self, other):
            for doc_id, doc in idx.documents.items():
                out.add_document(doc, [c for c in idx.clauses.values() if c.doc_id == doc_id])
        return out

    def to_dict(self) -> dict:
        return {
            "extractor_version": self.extractor_version,
            "documents": [d.to_dict() for d in self.documents.values()],
            "clauses": [c.to_dict() for c in self.clauses.values()],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ClauseIndex":
        idx = cls(extractor_version=d.get("extractor_version", EXTRACTOR_VERSION))
        clauses = [Clause.from_dict(c) for c in d.get("clauses", [])]
        for doc in (Document.from_dict(x) for x in d.get("documents", [])):
            idx.add_document(doc, [c for c in clauses if c.doc_id == doc.doc_id])
        orphans = [c.clause_id for c in clauses if c.doc_id not in idx.documents]
        if orphans:
            raise ValueError(f"clauses without a document: {orphans[:3]}")
        return idx

    def to_json(self, indent: int | None = None) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_json(cls, s: str) -> "ClauseIndex":
        return cls.from_dict(json.loads(s))


def _bbox(v) -> BBox:
    x0, top, x1, bottom = (float(x) for x in v)
    return (x0, top, x1, bottom)
