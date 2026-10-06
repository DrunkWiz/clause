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
- **Grounding set (2026-10-06)**: 20 good, 18 bad and 2 limitation claims against the real Ambetter Texas SBC and EOC. All bad claims are rejected for the expected reason, and the false-rejection rate on good claims is 0/20. The good claims are hand-written, so this rate is optimistic until real model output is measured on Thursday.

## 2026-10-06 — Rules

- **Regulations are documents.** eCFR text, 5 U.S.C. 6103 and one CMS guidance PDF are indexed like plan documents. Each clause carries its paragraph citation as a `label`, taken from eCFR's own `data-title` attributes, not parsed from paragraph markers. Rule outputs use the same claim shape as model output and cite this text, so the grounding verifier checks the rules' sources too. Every rule table has a test that verifies each reference.
- **Individual market only.** All three plans are marketplace plans. Employer (ERISA) plan rules are out of scope.
- **Federal minimums only.** State rules can be stricter (for example, Ambetter's EOC promises a 30-day decision under Texas law). Plan-stated deadlines will come from the drafter on Thursday, as cited plan text.
- **Counting from the letter date.** The rules count from receipt. We count from the date given (normally the letter date), which can only be earlier, so our deadlines are never later than the real ones.
- **No weekend roll-over for the 180-day appeal.** Only the external-review filing rule has one (147.136(d)(2)(i)). If day 180 lands on a weekend or holiday, the person is told to file before it.
- **Federal holidays are the 6103(a) dates.** The Friday/Monday observed rules in 6103(b) apply "for the purpose of statutes relating to pay and leave of employees". When the external review date is extended, the interface still recommends filing by the unextended date.
- **Notice completeness: absence is the default.** An element counts as present only with a verified quote from the letter. A missing element is shown as "not found in this letter". Deemed exhaustion (147.136(b)(3)(ii)(F)) is offered as "you may be able to", with its de minimis exception stated.
- **Notice TODO**: the ERISA civil-action statement in 2560.503-1(g)(1)(iv) is not checked, because it is unclear that it applies to individual-market issuers.
- **Reason codes**: code numbers are from X12. X12's descriptions are copyrighted, so the meanings are our own wording and are shown as explanation, not cited fact. The CO/PR meaning is cited to CMS MLN905367, which is Medicare guidance; for private plans the interface says "ask".
- **Money in rule claims** must come from a quoted line of the person's EOB or bill. A rule never states a computed sum, so the number check still applies, and a wrongly extracted amount is rejected.
- **No Surprises**: the rule decides whether a protection applies and flags out-of-network cost-sharing or balance billing on protected care. It does not compute allowed amounts, because the qualifying payment amount is not public. Ground ambulance is outside the federal rules and is shown as a note.
