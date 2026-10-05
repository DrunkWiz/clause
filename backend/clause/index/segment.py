"""Words and table rows on a page -> clauses.

Pure geometry, no PDF library, so it can be tested on hand-made word lists.
Steps: find a column gutter if there is one, group words into lines, group
lines into paragraphs, add table rows, then order everything for reading.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass

from clause.index.model import PAGE, PARAGRAPH, TABLE_ROW, BBox, Clause, Line, make_clause_id

# Gutter search: only in the middle of the page, at least this wide, with at
# most this share of words crossing it, and enough words on each side.
GUTTER_ZONE = (0.3, 0.7)
GUTTER_MIN_WIDTH = 8.0
GUTTER_MAX_CROSSING = 0.02
GUTTER_MIN_SIDE_SHARE = 0.15

PARA_GAP_RATIO = 0.6  # a vertical gap above this x line height starts a new paragraph
SIZE_CHANGE = 1.0  # a font size change above this (points) starts a new paragraph
SINGLE_LINE_MAX = 18.0  # a table cell no taller than this (points) holds one line of text
PAGE_FALLBACK_LINES = 60  # a single paragraph this long means segmentation failed
BULLETS = ("•", "●", "▪", "◦", "", "", "", "➢")
# "3. ", "a) ", "(iv) ", "B. ": a numbered list item starts its own paragraph.
_LIST_ITEM = re.compile(r"^(?:\(?(?:\d{1,2}|[a-zA-Z]|[ivxIVX]{1,4})[.)]|\((?:\d{1,2}|[a-zA-Z]|[ivxIVX]{1,4})\))\s")
# Dot leaders, as in a table of contents: each such line is its own clause.
_LEADER = re.compile(r"\.{5,}|(?:\. ){5,}")


@dataclass(frozen=True)
class Word:
    text: str
    x0: float
    top: float
    x1: float
    bottom: float
    size: float = 0.0


@dataclass(frozen=True)
class Cell:
    bbox: BBox
    text: str
    parts: tuple[tuple[BBox, str], ...] = ()  # sub-lines after merging; empty means one part


@dataclass(frozen=True)
class TableRow:
    cells: tuple[Cell, ...]


@dataclass
class _Line:
    words: list[Word]

    @property
    def top(self) -> float:
        return min(w.top for w in self.words)

    @property
    def bottom(self) -> float:
        return max(w.bottom for w in self.words)

    @property
    def x0(self) -> float:
        return min(w.x0 for w in self.words)

    @property
    def height(self) -> float:
        return self.bottom - self.top

    @property
    def size(self) -> float:
        return statistics.median(w.size for w in self.words)

    @property
    def bbox(self) -> BBox:
        return (self.x0, self.top, max(w.x1 for w in self.words), self.bottom)

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)


@dataclass
class _Block:
    sort_key: tuple
    kind: str
    parts: list  # paragraph: [(bbox, text)] per line; table row: per column, [(bbox, text)] per sub-line


def find_gutter(words: list[Word], width: float) -> float | None:
    """x position of the gap between two text columns, or None."""
    if len(words) < 20:
        return None
    lo, hi = int(width * GUTTER_ZONE[0]), int(width * GUTTER_ZONE[1])
    limit = max(1, int(len(words) * GUTTER_MAX_CROSSING))
    clear = []
    for x in range(lo, hi + 1):
        crossing = sum(1 for w in words if w.x0 <= x <= w.x1)
        clear.append(crossing <= limit)
    best, run_start = None, None
    for i, ok in enumerate(clear + [False]):
        if ok and run_start is None:
            run_start = i
        elif not ok and run_start is not None:
            if best is None or i - run_start > best[1] - best[0]:
                best = (run_start, i)
            run_start = None
    if best is None or best[1] - best[0] < GUTTER_MIN_WIDTH:
        return None
    gutter = lo + (best[0] + best[1]) / 2
    left = sum(1 for w in words if w.x1 < gutter)
    right = sum(1 for w in words if w.x0 > gutter)
    if min(left, right) < len(words) * GUTTER_MIN_SIDE_SHARE:
        return None
    return gutter


def group_lines(words: list[Word]) -> list[_Line]:
    """Words whose vertical extents overlap by at least half go on one line."""
    lines: list[_Line] = []
    for w in sorted(words, key=lambda w: (w.top, w.x0)):
        h = w.bottom - w.top
        for line in reversed(lines[-3:]):
            overlap = min(line.bottom, w.bottom) - max(line.top, w.top)
            if overlap >= 0.5 * min(h, line.height or h):
                line.words.append(w)
                break
        else:
            lines.append(_Line([w]))
    for line in lines:
        line.words.sort(key=lambda w: w.x0)
    lines.sort(key=lambda l: (l.top, l.x0))
    return lines


def group_paragraphs(lines: list[_Line]) -> list[list[_Line]]:
    paras: list[list[_Line]] = []
    for line in lines:
        if paras:
            prev = paras[-1][-1]
            gap = line.top - prev.bottom
            h = max(min(line.height, prev.height), 1.0)
            new = (
                gap > PARA_GAP_RATIO * h
                or abs(line.size - prev.size) > SIZE_CHANGE
                or line.text.startswith(BULLETS)
                or _LIST_ITEM.match(line.text) is not None
                or _LEADER.search(line.text) is not None
                or _LEADER.search(prev.text) is not None
            )
            if not new:
                paras[-1].append(line)
                continue
        paras.append([line])
    return paras


def merge_continuation_rows(rows: list[TableRow]) -> list[TableRow]:
    """Fold sub-rows back into the row they belong to.

    Table finders often split a multi-line cell into one-line sub-rows, so a
    row holding only the second line of a "Limitations" cell appears on its
    own. A row is a continuation when it sits inside the previous row's band
    (top to the median bottom of its cells) and each of its cells lies under a
    cell of that row; its text is appended to that cell.
    """
    out: list[list[list]] = []  # rows -> columns -> parts [(bbox, text)]
    bands: list[tuple[float, float]] = []
    prev_raw: list[Cell] = []
    for row in rows:
        cells = [c for c in row.cells if c.text and c.text.strip()]
        if not cells:
            continue
        if out and _continues(out[-1], bands[-1], prev_raw, cells):
            for c in cells:
                out[-1][_best_column(out[-1], c.bbox)].append((c.bbox, c.text.strip()))
        else:
            out.append([[(c.bbox, c.text.strip())] for c in cells])
            bands.append((min(c.bbox[1] for c in cells), statistics.median(c.bbox[3] for c in cells)))
        prev_raw = cells
    return [TableRow(tuple(_column_cell(col) for col in r)) for r in out] if out else []


def _continues(row: list[list], band: tuple[float, float], prev_raw: list[Cell], cells: list[Cell]) -> bool:
    if any(_best_column(row, c.bbox) is None for c in cells):
        return False
    top, bottom = band
    # Inside the band of the row above (a cell split into sub-rows).
    if all(c.bbox[1] >= top - 1 and c.bbox[3] <= bottom + 1 for c in cells):
        return True
    # Touching one-line rows: one row broken into a row per text line, unless
    # this looks like a new row (capitalised after a finished sentence).
    single = all(c.bbox[3] - c.bbox[1] <= SINGLE_LINE_MAX for c in prev_raw + cells)
    touching = abs(min(c.bbox[1] for c in cells) - max(c.bbox[3] for c in prev_raw)) <= 2
    if not (single and touching):
        return False
    first = min(cells, key=lambda c: c.bbox[0])
    above = row[_best_column(row, first.bbox)][-1][1]
    return not (first.text.strip()[:1].isupper() and above.rstrip().endswith(("?", ".", ":")))


def _column_cell(parts: list[tuple[BBox, str]]) -> Cell:
    boxes = [b for b, _ in parts]
    bbox = (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))
    return Cell(bbox, "\n".join(t for _, t in parts), tuple(parts))


def _best_column(row: list[list], bbox: BBox) -> int | None:
    best, best_overlap = None, 0.0
    for i, parts in enumerate(row):
        b = parts[0][0]
        overlap = min(b[2], bbox[2]) - max(b[0], bbox[0])
        if overlap > best_overlap:
            best, best_overlap = i, overlap
    width = bbox[2] - bbox[0]
    return best if width > 0 and best_overlap >= 0.5 * width else None


def segment_page(
    doc_id: str,
    page_no: int,
    width: float,
    words: list[Word],
    tables: list[list[TableRow]] = (),
) -> list[Clause]:
    """`tables` holds each table's rows, in order, as the table finder gave them."""
    words = [w for w in words if w.text.strip()]
    gutter = find_gutter(words, width)

    def group_of(x0: float, x1: float) -> int:
        if gutter is None:
            return 1
        if x1 < gutter:
            return 1
        if x0 > gutter:
            return 2
        return 0  # spans the gutter

    # Assign whole lines, so a full-width header that crosses the gutter
    # stays in one piece instead of being split between the columns.
    columns: dict[int, list[Word]] = {}
    for line in group_lines(words) if gutter is not None else [_Line(words)]:
        groups = {group_of(w.x0, w.x1) for w in line.words}
        for w in line.words:
            g = 0 if 0 in groups else group_of(w.x0, w.x1)
            columns.setdefault(g, []).append(w)

    column_top = min(
        (w.top for g, ws in columns.items() if g != 0 for w in ws),
        default=float("inf"),
    )

    def key(group: int, top: float) -> tuple:
        if group == 0:  # full-width: before the columns if above them, else after
            return (0 if top <= column_top else 3, top)
        return (group, top)

    blocks: list[_Block] = []
    for group, ws in columns.items():
        for para in group_paragraphs(group_lines(ws)):
            blocks.append(_Block(key(group, para[0].top), PARAGRAPH, [(l.bbox, l.text) for l in para]))

    for row in (r for t in tables for r in merge_continuation_rows(t)):
        cells = list(row.cells)
        x0 = min(c.bbox[0] for c in cells)
        x1 = max(c.bbox[2] for c in cells)
        top = min(c.bbox[1] for c in cells)
        columns_parts = [list(c.parts) or [(c.bbox, c.text.strip())] for c in cells]
        blocks.append(_Block(key(group_of(x0, x1), top), TABLE_ROW, columns_parts))

    blocks.sort(key=lambda b: b.sort_key)

    if len(blocks) == 1 and blocks[0].kind == PARAGRAPH and len(blocks[0].parts) >= PAGE_FALLBACK_LINES:
        blocks[0].kind = PAGE

    return [_to_clause(doc_id, page_no, n, b) for n, b in enumerate(blocks, start=1)]


def _to_clause(doc_id: str, page_no: int, n: int, block: _Block) -> Clause:
    """Paragraph parts are lines joined by newlines. Table row parts are
    columns joined by " | ", each column's sub-lines joined by newlines."""
    columns = block.parts if block.kind == TABLE_ROW else [block.parts]
    sep = " | " if block.kind == TABLE_ROW else "\n"
    text, lines = "", []
    for i, column in enumerate(columns):
        if i:
            text += sep
        for j, (bbox, part) in enumerate(column):
            if j:
                text += "\n"
            start = len(text)
            text += part
            lines.append(Line(tuple(round(v, 2) for v in bbox), start, len(text)))
    boxes = [l.bbox for l in lines]
    return Clause(
        clause_id=make_clause_id(doc_id, page_no, n),
        doc_id=doc_id,
        page=page_no,
        bbox=(min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)),
        text=text,
        lines=tuple(lines),
        kind=block.kind,
    )
