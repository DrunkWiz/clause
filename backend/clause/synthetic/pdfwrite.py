"""A minimal PDF writer for the synthetic letters and EOBs. Stdlib only.

Text in the standard Helvetica fonts (WinAnsi encoding, so curly quotes and
dashes work), straight lines for table rules, US Letter pages. Output is
deterministic: no timestamps or random ids, so the same input gives the same
bytes and the same index hashes.

Coordinates in the API are from the top left, like the clause index.
"""

from __future__ import annotations

import textwrap

PAGE_W, PAGE_H = 612.0, 792.0
FONTS = {"regular": ("F1", "Helvetica"), "bold": ("F2", "Helvetica-Bold")}


def _pdf_string(s: str) -> bytes:
    raw = s.encode("cp1252", errors="replace")
    return b"(" + raw.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)") + b")"


class Page:
    def __init__(self):
        self.ops: list[bytes] = []

    def text(self, x: float, top: float, s: str, size: float = 10, font: str = "regular") -> None:
        name = FONTS[font][0]
        y = PAGE_H - top - size
        self.ops.append(b"BT /%s %.2f Tf %.2f %.2f Td %s Tj ET" % (name.encode(), size, x, y, _pdf_string(s)))

    def line(self, x0: float, top0: float, x1: float, top1: float, width: float = 0.8) -> None:
        self.ops.append(b"%.2f w %.2f %.2f m %.2f %.2f l S" % (width, x0, PAGE_H - top0, x1, PAGE_H - top1))

    def content(self) -> bytes:
        return b"\n".join(self.ops)


class Document:
    def __init__(self):
        self.pages: list[Page] = []

    def new_page(self) -> Page:
        p = Page()
        self.pages.append(p)
        return p

    def to_bytes(self) -> bytes:
        objs: list[bytes] = []  # object n is objs[n-1]

        def add(body: bytes) -> int:
            objs.append(body)
            return len(objs)

        catalog = add(b"")  # filled in below
        pages_obj = add(b"")
        fonts = {
            key: add(b"<< /Type /Font /Subtype /Type1 /BaseFont /%s /Encoding /WinAnsiEncoding >>" % base.encode())
            for key, (_, base) in FONTS.items()
        }
        font_res = b" ".join(b"/%s %d 0 R" % (FONTS[k][0].encode(), n) for k, n in fonts.items())
        kids = []
        for p in self.pages:
            data = p.content()
            stream = add(b"<< /Length %d >>\nstream\n%s\nendstream" % (len(data), data))
            kids.append(
                add(
                    b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 %d %d] /Resources << /Font << %s >> >> /Contents %d 0 R >>"
                    % (pages_obj, PAGE_W, PAGE_H, font_res, stream)
                )
            )
        objs[catalog - 1] = b"<< /Type /Catalog /Pages %d 0 R >>" % pages_obj
        objs[pages_obj - 1] = b"<< /Type /Pages /Kids [%s] /Count %d >>" % (
            b" ".join(b"%d 0 R" % k for k in kids),
            len(kids),
        )

        out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = []
        for n, body in enumerate(objs, start=1):
            offsets.append(len(out))
            out += b"%d 0 obj\n%s\nendobj\n" % (n, body)
        xref = len(out)
        out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
        for off in offsets:
            out += b"%010d 00000 n \n" % off
        out += b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, catalog, xref)
        return bytes(out)


class Flow:
    """Writes wrapped paragraphs down a page, starting new pages as needed,
    with a running header and footer on every page."""

    LEFT, RIGHT, TOP, BOTTOM = 72.0, 540.0, 72.0, 720.0

    def __init__(self, header: str, footer: str):
        self.doc = Document()
        self.header, self.footer = header, footer
        self.page: Page | None = None
        self.y = 0.0
        self._new_page()

    def _new_page(self) -> None:
        self.page = self.doc.new_page()
        n = len(self.doc.pages)
        self.page.text(self.LEFT, 36, self.header, size=8, font="bold")
        self.page.line(self.LEFT, 50, self.RIGHT, 50, width=0.5)
        self.page.text(self.LEFT, 750, f"{self.footer}   Page {n}", size=8)
        self.y = self.TOP

    def ensure(self, height: float) -> None:
        if self.y + height > self.BOTTOM:
            self._new_page()

    def space(self, h: float = 8) -> None:
        self.y += h

    def para(self, text: str, size: float = 10, font: str = "regular", indent: float = 0, after: float = 8) -> None:
        # Helvetica averages about half an em per character; wrap conservatively.
        width_chars = int((self.RIGHT - self.LEFT - indent) / (size * 0.52))
        lines = textwrap.wrap(text, width=width_chars, break_long_words=False, break_on_hyphens=False) or [""]
        leading = size * 1.3
        for line in lines:
            self.ensure(leading)
            self.page.text(self.LEFT + indent, self.y, line, size=size, font=font)
            self.y += leading
        self.y += after

    def table(self, rows: list[list[str]], widths: list[float], size: float = 9, header: bool = True) -> None:
        """A ruled table; each cell's text wraps inside its column."""
        x_edges = [self.LEFT]
        for w in widths:
            x_edges.append(x_edges[-1] + w)
        leading = size * 1.3
        for r, row in enumerate(rows):
            # Never split a word: a broken "$1,900.00" would no longer read as an amount.
            wrapped = [
                textwrap.wrap(c, width=max(4, int((w - 8) / (size * 0.52))), break_long_words=False, break_on_hyphens=False) or [""]
                for c, w in zip(row, widths)
            ]
            h = max(len(w) for w in wrapped) * leading + 8
            self.ensure(h)
            top = self.y
            self.page.line(x_edges[0], top, x_edges[-1], top)
            font = "bold" if header and r == 0 else "regular"
            for i, lines in enumerate(wrapped):
                for j, line in enumerate(lines):
                    self.page.text(x_edges[i] + 4, top + 4 + j * leading, line, size=size, font=font)
            for x in x_edges:
                self.page.line(x, top, x, top + h)
            self.y = top + h
            self.page.line(x_edges[0], self.y, x_edges[-1], self.y)
        self.y += 10

    def to_bytes(self) -> bytes:
        return self.doc.to_bytes()
