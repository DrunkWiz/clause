"""Regulation text -> clauses, so rule outputs can cite the law and pass the
same grounding verifier as everything else.

Sources (raw files in data/regs/raw, fetched by scripts/fetch_regs.py):
- eCFR rendered HTML, where every paragraph is a <p data-title="147.136(d)(2)(i)">
- GovInfo HTML for 5 U.S.C. 6103 (federal holidays)

Regulation clauses have no page geometry: page 1, zero boxes, and a `label`
holding the full citation. Stdlib only.
"""

from __future__ import annotations

import hashlib
import html
import re
from dataclasses import dataclass, replace
from html.parser import HTMLParser
from pathlib import Path

from clause.index.model import PARAGRAPH, Clause, ClauseIndex, Document, Line, make_clause_id

_NO_BOX = (0.0, 0.0, 0.0, 0.0)

ECFR = "https://www.ecfr.gov/api/renderer/v1/content/enhanced/{date}/title-{title}?part={part}&section={section}"


@dataclass(frozen=True)
class Source:
    raw_file: str
    url: str
    kind: str  # "ecfr" | "usc6103" | "pdf"
    title_no: int = 0
    section: str = ""
    citation: str = ""  # for "pdf": label prefix, e.g. "CMS MLN905367"


def _ecfr(title_no: int, section: str, date: str) -> Source:
    part = section.split(".")[0]
    return Source(
        raw_file=f"{title_no}-cfr-{section}.html",
        url=ECFR.format(date=date, title=title_no, part=part, section=section),
        kind="ecfr",
        title_no=title_no,
        section=section,
    )


# Every regulation the rules cite. Dates are the eCFR "up to date as of" dates
# used when the text was fetched (see data/regs/SOURCES.md).
SOURCES: tuple[Source, ...] = (
    _ecfr(45, "147.136", "2026-10-01"),
    _ecfr(29, "2560.503-1", "2026-09-30"),
    _ecfr(45, "149.110", "2026-10-01"),
    _ecfr(45, "149.120", "2026-10-01"),
    _ecfr(45, "149.130", "2026-10-01"),
    _ecfr(45, "149.410", "2026-10-01"),
    _ecfr(45, "149.420", "2026-10-01"),
    Source(
        raw_file="5-usc-6103.htm",
        url="https://www.govinfo.gov/content/pkg/USCODE-2024-title5/html/USCODE-2024-title5-partIII-subpartE-chap61-subchapI-sec6103.htm",
        kind="usc6103",
    ),
    # CMS guidance, not regulation: what the claim adjustment group codes mean.
    Source(
        raw_file="cms-mln905367.pdf",
        url="https://www.cms.gov/Outreach-and-Education/Medicare-Learning-Network-MLN/MLNProducts/Downloads/ICN905367TextOnly.pdf",
        kind="pdf",
        citation="CMS MLN905367 (Remittance Advice Resources and FAQs)",
    ),
)


def build_regs_index(raw_dir: Path) -> ClauseIndex:
    idx = ClauseIndex()
    for s in SOURCES:
        path = raw_dir / s.raw_file
        if s.kind == "ecfr":
            doc, clauses = parse_ecfr(path.read_text(encoding="utf-8"), s.title_no, s.section, s.url)
        elif s.kind == "usc6103":
            doc, clauses = parse_usc_6103(path.read_text(encoding="utf-8", errors="replace"), s.url)
        else:
            doc, clauses = parse_pdf_source(path.read_bytes(), s)
        idx.add_document(doc, clauses)
    return idx


def parse_pdf_source(data: bytes, s: Source) -> tuple[Document, list[Clause]]:
    """A PDF guidance document, through the normal PDF extractor, with each
    clause labelled "<citation>, p.<page>"."""
    from clause.index.extract import extract_pdf  # needs pdfplumber; only at build time

    doc_id = _doc_id(Path(s.raw_file).stem)
    doc, clauses = extract_pdf(data, s.raw_file, doc_id)
    doc = replace(doc, title=s.citation, source_url=s.url)
    return doc, [replace(c, label=f"{s.citation}, p.{c.page}") for c in clauses]


class _EcfrParser(HTMLParser):
    """Collects (data-title, text) for each paragraph <p>."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.paras: list[tuple[str, str]] = []
        self._depth = 0  # >0 while inside a <p>
        self._title = ""
        self._buf: list[str] = []
        self.last_title = ""

    def handle_starttag(self, tag, attrs):
        if tag == "p":
            a = dict(attrs)
            self._depth = 1
            # Titles can carry escaped markup, e.g. "147.136(d)(2)(iii)(B)(<em>6</em>)".
            self._title = re.sub(r"<[^>]+>", "", a.get("data-title") or "")
            self._buf = []
        elif self._depth:
            self._depth += 1 if tag not in ("br", "img") else 0

    def handle_endtag(self, tag):
        if tag == "p" and self._depth:
            text = re.sub(r"\s+", " ", "".join(self._buf)).strip()
            if text:
                title = self._title or self.last_title
                self.paras.append((title, text))
                if self._title:
                    self.last_title = self._title
            self._depth = 0
        elif self._depth > 1:
            self._depth -= 1

    def handle_data(self, data):
        if self._depth:
            self._buf.append(data)


def _doc_id(citation: str) -> str:
    """"45 CFR 147.136" -> "45-cfr-147-136"; "5 U.S.C. 6103" -> "5-usc-6103"."""
    return re.sub(r"[^a-z0-9]+", "-", citation.lower().replace("u.s.c.", "usc")).strip("-")


def _clauses(doc_id: str, items: list[tuple[str, str]]) -> list[Clause]:
    return [
        Clause(
            clause_id=make_clause_id(doc_id, 1, n),
            doc_id=doc_id,
            page=1,
            bbox=_NO_BOX,
            text=text,
            lines=(Line(_NO_BOX, 0, len(text)),),
            kind=PARAGRAPH,
            label=label,
        )
        for n, (label, text) in enumerate(items, start=1)
    ]


def parse_ecfr(raw: str, title_no: int, section: str, source_url: str) -> tuple[Document, list[Clause]]:
    """eCFR rendered HTML for one section."""
    citation = f"{title_no} CFR {section}"
    doc_id = _doc_id(citation)
    p = _EcfrParser()
    p.feed(raw)
    items = [(f"{title_no} CFR {t}" if t else citation, text) for t, text in p.paras]
    doc = Document(
        doc_id=doc_id,
        filename=f"{doc_id}.html",
        sha256=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        page_sizes=(),
        title=citation,
        source_url=source_url,
    )
    return doc, _clauses(doc_id, items)


def parse_usc_6103(raw: str, source_url: str) -> tuple[Document, list[Clause]]:
    """GovInfo HTML for 5 U.S.C. 6103: subsection (a), one clause per
    holiday, and the opening of (b), which limits the observed-day rules to
    pay and leave."""
    citation = "5 U.S.C. 6103"
    doc_id = _doc_id(citation)
    text = html.unescape(re.sub(r"<[^>]+>", "\n", raw))
    lines = [re.sub(r"\s+", " ", l).strip() for l in text.splitlines()]
    lines = [l for l in lines if l]
    start = next(i for i, l in enumerate(lines) if l.startswith("(a) The following are legal public holidays"))
    items = [(f"{citation}(a)", lines[start])]
    i = start + 1
    while not lines[i].startswith("(b)"):
        items.append((f"{citation}(a)", lines[i]))
        i += 1
    items.append((f"{citation}(b)", lines[i]))
    doc = Document(
        doc_id=doc_id,
        filename=f"{doc_id}.htm",
        sha256=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        page_sizes=(),
        title=citation,
        source_url=source_url,
    )
    return doc, _clauses(doc_id, items)
