import unittest
from pathlib import Path

from clause.index.model import ClauseIndex
from clause.index.regs import SOURCES, build_regs_index, parse_ecfr, parse_usc_6103
from clause.rules.base import REGS_INDEX, Ref, regs

RAW = Path(__file__).resolve().parents[2] / "data" / "regs" / "raw"

try:
    import pdfplumber  # noqa: F401
except ImportError:
    pdfplumber = None

ECFR_SAMPLE = """
<div id="p-147.136(d)(2)(i)">
<p class="indent-3" data-title="147.136(d)(2)(i)"><span class="paragraph-hierarchy"><span class="paren">(</span>i<span class="paren">)</span></span> <em class="paragraph-heading">Request for external review.</em>  A plan must allow a claimant
to file &amp; so on.</p></div>
<p data-title="147.136(d)(2)(iii)(B)(&lt;em&gt;6&lt;/em&gt;)">(6) The IRO must decide within 45 days.</p>
<p>An untitled example paragraph.</p>
<p data-title="147.136(d)(3)">   </p>
"""


class ParseEcfrTest(unittest.TestCase):
    def setUp(self):
        self.doc, self.clauses = parse_ecfr(ECFR_SAMPLE, 45, "147.136", "https://example.test")

    def test_labels_and_text(self):
        self.assertEqual(self.doc.doc_id, "45-cfr-147-136")
        self.assertEqual(self.doc.title, "45 CFR 147.136")
        self.assertEqual(
            [(c.label, c.text) for c in self.clauses],
            [
                ("45 CFR 147.136(d)(2)(i)", "(i) Request for external review. A plan must allow a claimant to file & so on."),
                ("45 CFR 147.136(d)(2)(iii)(B)(6)", "(6) The IRO must decide within 45 days."),
                ("45 CFR 147.136(d)(2)(iii)(B)(6)", "An untitled example paragraph."),  # inherits the last label
            ],
        )

    def test_clause_shape(self):
        c = self.clauses[0]
        self.assertEqual((c.clause_id, c.page, c.bbox), ("45-cfr-147-136#p1.1", 1, (0.0, 0.0, 0.0, 0.0)))
        self.assertEqual((c.lines[0].start, c.lines[0].end), (0, len(c.text)))


class ParseUscTest(unittest.TestCase):
    def test_holidays(self):
        doc, clauses = parse_usc_6103((RAW / "5-usc-6103.htm").read_text(encoding="utf-8", errors="replace"), "u")
        self.assertEqual(doc.doc_id, "5-usc-6103")
        texts = [c.text for c in clauses]
        self.assertEqual(texts[0], "(a) The following are legal public holidays:")
        self.assertEqual(len([c for c in clauses if c.label == "5 U.S.C. 6103(a)"]), 12)
        self.assertIn("Juneteenth National Independence Day, June 19.", texts)
        self.assertTrue(texts[-1].startswith("(b) For the purpose of statutes relating to pay and leave of employees"))


class RegsIndexTest(unittest.TestCase):
    def test_every_source_indexed(self):
        titles = {d.title for d in regs().documents.values()}
        self.assertEqual(len(regs().documents), len(SOURCES))
        self.assertIn("45 CFR 147.136", titles)
        self.assertIn("5 U.S.C. 6103", titles)

    def test_no_markup_in_labels(self):
        self.assertFalse([c.label for c in regs().clauses.values() if "<" in c.label or "&" in c.label])

    def test_ref_picks_the_clause_containing_the_quote(self):
        cit = Ref("5 U.S.C. 6103(a)", "Christmas Day, December 25.").citation()
        self.assertEqual(regs().get(cit["clause_id"]).text, "Christmas Day, December 25.")

    @unittest.skipIf(pdfplumber is None, "pdfplumber not installed")
    def test_committed_index_matches_raw_sources(self):
        built = build_regs_index(RAW)
        committed = ClauseIndex.from_json(REGS_INDEX.read_text(encoding="utf-8"))
        self.assertEqual(built.to_dict(), committed.to_dict(), "run: python scripts/regs.py build")


if __name__ == "__main__":
    unittest.main()
