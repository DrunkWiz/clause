# Decisions

Short log of choices that shape the code. Newest last.

## 2026-10-05 — Clause index and verifier

- **PDF library: pdfplumber** (MIT). Word-level bounding boxes and table detection. PyMuPDF rejected for its AGPL licence, which would complicate the revenue model. Only `backend/clause/index/extract.py` imports it.
- **Clause ids** look like `<doc_id>#p<page>.<n>`. They are deterministic, and the index records each document's sha256 and the extractor version.
- **Line-level boxes** are stored for each clause, as character offsets into its text, so the UI highlights only the quoted lines.
- **Page-level fallback**: a page that segments badly becomes one clause and is flagged.
- **Mixed citations**: if any citation on a claim fails, the claim is unsupported. A made-up quote is a warning sign.
- **Number consistency in v1**: every money amount, percentage or day count in a claim's text must appear in one of its verified quotes.
- **Minimum quote length**: 4 normalised words, unless the quote is the whole clause. Ellipsis fragments must appear in order and each meet the minimum.
- **Normalisation**: NFKC; plain quotes and dashes; soft hyphens and zero-width characters removed; line-break hyphens joined; hyphens dropped; other punctuation stripped; whitespace collapsed; case folded. Commas between digits are dropped; decimal points and `%` are kept.
- **Test runner: stdlib `unittest`**, with no network and no key.
- **Known limit, stated in the README**: the verifier proves a quote is in the cited clause, not that the claim follows from it.

## 2026-10-06 — Extraction against the real plans

- **Hidden text**: characters under 3pt and non-upright characters are dropped. The Kaiser SBC header carries 1pt text.
- **Columns**: a vertical gutter in the middle 30–70% of the page, crossed by at most 2% of words, with at least 15% of words on each side. Lines that cross it, such as running headers, are kept whole and placed before or after the columns.
- **Paragraph breaks**: a vertical gap above 0.6× line height, a font size change of more than 1pt, a bullet, a numbered item ("3.", "a)", "(iv)"), or a dot-leader line (tables of contents).
- **Tables**: one clause per row, cells joined with " | ". Tables nested in another table's cell are dropped, because they repeat its text. Sub-rows are folded back into their row when they sit inside its band, or when they are touching one-line rows that don't start a new sentence. Each sub-line stays its own highlight box.
- **No text lost**: words are left out of paragraph text only when a captured table cell contains them, not merely because they sit inside a table's box.
- **Number check widened**: hours now count alongside days, and spelled-out numbers (one to twenty, thirty, forty-five, sixty, ninety) count too. Plan documents say "five business days" and "72 hours".
- **Known extraction limit**: the "Important Questions" block on SBC page 1 comes out one clause per line, because pdfplumber returns it as several separate tables with vertically centred labels. Each line can be cited; only a quote spanning two lines fails. It mostly affects "before care", which is first on the cut list.
- **Grounding set**: 20 good, 18 bad and 2 limitation claims against the real Ambetter Texas SBC and EOC. All bad claims are rejected for the expected reason, and the false-rejection rate on good claims is 0/20. The good claims are hand-written, so this rate is optimistic until real model output is measured on Thursday.
