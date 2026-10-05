"""PDF -> clauses. The only module that imports the PDF library (pdfplumber).

Documents are read from bytes in memory; nothing is written to disk here.
"""

from __future__ import annotations

import hashlib
import io
import re
from pathlib import Path

import pdfplumber

from clause.index.model import Clause, ClauseIndex, Document
from clause.index.segment import Cell, TableRow, Word, segment_page

# Characters smaller than this are hidden text (e.g. the Kaiser SBC header
# carries 1pt text that would otherwise interleave with the visible title).
MIN_CHAR_SIZE = 3.0


def doc_id_for(filename: str) -> str:
    stem = Path(filename).stem.lower()
    return re.sub(r"[^a-z0-9]+", "-", stem).strip("-") or "document"


def extract_pdf(data: bytes, filename: str, doc_id: str | None = None) -> tuple[Document, list[Clause]]:
    doc_id = doc_id or doc_id_for(filename)
    clauses: list[Clause] = []
    sizes: list[tuple[float, float]] = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page_no, page in enumerate(pdf.pages, start=1):
            sizes.append((float(page.width), float(page.height)))
            words, rows = _read_page(page)
            clauses.extend(segment_page(doc_id, page_no, float(page.width), words, rows))
    doc = Document(doc_id=doc_id, filename=Path(filename).name, sha256=hashlib.sha256(data).hexdigest(), page_sizes=tuple(sizes))
    return doc, clauses


def build_index(paths: list[str | Path]) -> ClauseIndex:
    idx = ClauseIndex()
    for p in paths:
        p = Path(p)
        doc, clauses = extract_pdf(p.read_bytes(), p.name)
        idx.add_document(doc, clauses)
    return idx


def _visible_char(obj) -> bool:
    if obj.get("object_type") != "char":
        return True
    return obj.get("size", 0) >= MIN_CHAR_SIZE and obj.get("upright", True)


def _read_page(page) -> tuple[list[Word], list[list[TableRow]]]:
    page = page.filter(_visible_char)
    found = page.find_tables()
    # A table drawn inside another table's cell repeats that cell's text.
    tables = [t for t in found if not any(o is not t and _contains(o.bbox, t.bbox) for o in found)]

    out: list[list[TableRow]] = []
    cell_boxes = []
    for table in tables:
        rows = []
        for row, row_texts in zip(table.rows, table.extract()):
            cells = tuple(
                Cell(tuple(float(v) for v in bbox), text)
                for bbox, text in zip(row.cells, row_texts)
                if bbox is not None and text and text.strip()
            )
            if cells:
                rows.append(TableRow(cells))
                cell_boxes.extend(c.bbox for c in cells)
        out.append(rows)

    # Words already captured in a table cell are left out of the paragraph
    # flow; anything else inside a table's box is kept, so no text is lost.
    words = []
    for w in page.extract_words(extra_attrs=["size"]):
        cx, cy = (w["x0"] + w["x1"]) / 2, (w["top"] + w["bottom"]) / 2
        if any(x0 <= cx <= x1 and top <= cy <= bottom for x0, top, x1, bottom in cell_boxes):
            continue
        words.append(Word(w["text"], float(w["x0"]), float(w["top"]), float(w["x1"]), float(w["bottom"]), float(w["size"])))
    return words, out


def _contains(outer, inner, tol: float = 1.0) -> bool:
    return (
        inner[0] >= outer[0] - tol
        and inner[1] >= outer[1] - tol
        and inner[2] <= outer[2] + tol
        and inner[3] <= outer[3] + tol
    )
