import unittest
from pathlib import Path

from clause.index.model import Clause, ClauseIndex, Document, make_clause_id
from tests.fixtures import make_mini_index

FIXTURE = Path(__file__).parent / "fixtures" / "mini_index.json"


class ModelTest(unittest.TestCase):
    def test_clause_id_format(self):
        self.assertEqual(make_clause_id("kaiser-ga-hmo-eoc-2026", 31, 4), "kaiser-ga-hmo-eoc-2026#p31.4")

    def test_fixture_is_current(self):
        # mini_index.json must match its generator.
        self.assertEqual(ClauseIndex.from_json(FIXTURE.read_text(encoding="utf-8")).to_dict(), make_mini_index.build().to_dict())

    def test_json_round_trip(self):
        idx = make_mini_index.build()
        again = ClauseIndex.from_json(idx.to_json())
        self.assertEqual(again.to_dict(), idx.to_dict())
        self.assertEqual(list(again.clauses), list(idx.clauses))

    def test_lines_point_into_text(self):
        for c in make_mini_index.build().clauses.values():
            for line in c.lines:
                self.assertTrue(0 <= line.start < line.end <= len(c.text), c.clause_id)

    def test_duplicate_clause_rejected(self):
        idx = ClauseIndex()
        c = Clause("d#p1.1", "d", 1, (0, 0, 1, 1), "x")
        with self.assertRaises(ValueError):
            idx.add_document(Document("d", "d.pdf", "", ((1, 1),)), [c, c])

    def test_clause_from_other_doc_rejected(self):
        idx = ClauseIndex()
        with self.assertRaises(ValueError):
            idx.add_document(Document("d", "d.pdf", "", ((1, 1),)), [Clause("e#p1.1", "e", 1, (0, 0, 1, 1), "x")])

    def test_orphan_clause_rejected(self):
        with self.assertRaises(ValueError):
            ClauseIndex.from_dict({"documents": [], "clauses": [Clause("e#p1.1", "e", 1, (0, 0, 1, 1), "x").to_dict()]})

    def test_merge(self):
        a = make_mini_index.build()
        b = ClauseIndex()
        b.add_document(Document("other", "o.pdf", "", ((1, 1),)), [Clause("other#p1.1", "other", 1, (0, 0, 1, 1), "x")])
        merged = a.merge(b)
        self.assertEqual(len(merged.clauses), len(a.clauses) + 1)
        with self.assertRaises(ValueError):
            a.merge(a)


if __name__ == "__main__":
    unittest.main()
