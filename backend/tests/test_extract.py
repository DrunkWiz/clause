"""Extraction against the real plan PDFs committed in data/plans (offline)."""

import unittest
from functools import lru_cache
from pathlib import Path

from clause.index.model import TABLE_ROW, ClauseIndex
from clause.verify.normalise import norm

PLANS = Path(__file__).resolve().parents[2] / "data" / "plans"

try:
    from clause.index.extract import doc_id_for, extract_pdf
except ImportError:  # pdfplumber not installed
    extract_pdf = None


@lru_cache(maxsize=None)
def extract(name):
    path = PLANS / name
    return extract_pdf(path.read_bytes(), path.name)


@unittest.skipIf(extract_pdf is None, "pdfplumber not installed")
class ExtractTest(unittest.TestCase):
    def test_doc_id(self):
        self.assertEqual(doc_id_for("Kaiser GA HMO EOC 2026.pdf"), "kaiser-ga-hmo-eoc-2026")

    def test_sbc_structure_and_invariants(self):
        doc, clauses = extract("ambetter-tx-silver-sbc-2026.pdf")
        self.assertEqual(len(doc.page_sizes), 9)
        self.assertEqual(len(doc.sha256), 64)
        ids = [c.clause_id for c in clauses]
        self.assertEqual(len(ids), len(set(ids)))
        for c in clauses:
            w, h = doc.page_sizes[c.page - 1]
            x0, top, x1, bottom = c.bbox
            self.assertTrue(-1 <= x0 <= x1 <= w + 1 and -1 <= top <= bottom <= h + 1, c.clause_id)
            self.assertTrue(c.text.strip(), c.clause_id)
            for line in c.lines:
                self.assertTrue(0 <= line.start < line.end <= len(c.text), c.clause_id)
        self.assertGreater(sum(c.kind == TABLE_ROW for c in clauses), 50)

    def test_sbc_service_row_is_whole(self):
        _, clauses = extract("ambetter-tx-silver-sbc-2026.pdf")
        rows = [c for c in clauses if norm(c.text).startswith("if you visit a health care provider s office")]
        self.assertEqual(len(rows), 1)
        text = norm(rows[0].text)
        self.assertIn("primary care visit to treat an injury or illness", text)
        self.assertIn("$40 copay visit deductible does not apply", text)
        # The Limitations cell continues over several sub-rows; all of it is kept.
        self.assertIn("covered in full deductible does not apply", text)

    def test_no_duplicate_text_from_nested_tables(self):
        _, clauses = extract("ambetter-tx-silver-sbc-2026.pdf")
        page2 = [norm(c.text) for c in clauses if c.page == 2]
        self.assertFalse(any(t == "$40 copay visit" for t in page2))

    def test_hidden_text_dropped(self):
        _, clauses = extract("kaiser-ga-gold-hmo-sbc-2026.pdf")
        self.assertFalse(any("SC0KKCIP" in c.text for c in clauses))
        self.assertIn("Signature Gold HMO", clauses[1].text)

    def test_two_columns_not_interleaved(self):
        _, clauses = extract("kaiser-ga-hmo-eoc-2026.pdf")
        p31 = [c.text for c in clauses if c.page == 31]
        self.assertTrue(any(t.startswith("Except as prohibited by law, Prior Authorization is not a\nguarantee of payment") for t in p31))
        self.assertFalse(any("Prior Authorization is not a Health Education" in t for t in p31))

    def test_running_header_kept_whole(self):
        _, clauses = extract("kaiser-ga-hmo-eoc-2026.pdf")
        self.assertIn("Kaiser Foundation Health Plan of Georgia, Inc.", [c.text for c in clauses if c.page == 31])

    def test_deterministic_ids(self):
        path = PLANS / "fidelis-ny-silver-sbc-2026.pdf"
        a = extract_pdf(path.read_bytes(), path.name)
        b = extract_pdf(path.read_bytes(), path.name)
        self.assertEqual([c.to_dict() for c in a[1]], [c.to_dict() for c in b[1]])

    def test_index_round_trip(self):
        doc, clauses = extract("fidelis-ny-silver-sbc-2026.pdf")
        idx = ClauseIndex()
        idx.add_document(doc, clauses)
        self.assertEqual(ClauseIndex.from_json(idx.to_json()).to_dict(), idx.to_dict())


if __name__ == "__main__":
    unittest.main()
