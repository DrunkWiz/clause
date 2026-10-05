"""The labelled grounding set: real plan text, hand-written claims.

Every 'bad' claim must be rejected for the expected reason. The share of
'good' claims rejected is the false-rejection rate the README reports.
'limitation' claims are false but pass, and are kept here so that what the
verifier cannot catch is written down and tested, not hidden.
"""

import json
import unittest
from pathlib import Path

from clause.index.model import ClauseIndex
from clause.verify import verifier as v

ROOT = Path(__file__).resolve().parents[2]
SET = json.loads((Path(__file__).parent / "fixtures" / "grounding_set.json").read_text(encoding="utf-8"))

# The good set is written to pass; raise this only with a reason in docs/decisions.md.
MAX_FALSE_REJECTION = 0.0


def load_index() -> ClauseIndex:
    idx = ClauseIndex()
    for name in SET["indexes"]:
        idx = idx.merge(ClauseIndex.from_json((ROOT / "data" / "indexes" / name).read_text(encoding="utf-8")))
    return idx


class GroundingSetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = load_index()
        cls.results = {c["id"]: (c, v.verify_claim(c["claim"], cls.index)) for c in SET["cases"]}

    def cases(self, label):
        return [(case, r) for case, r in self.results.values() if case["label"] == label]

    def test_every_bad_claim_rejected_for_the_right_reason(self):
        for case, r in self.cases("bad"):
            with self.subTest(case["id"]):
                self.assertFalse(r.supported, case["claim"]["text"])
                self.assertEqual(r.reason, case["reason"])

    def test_false_rejection_rate(self):
        good = self.cases("good")
        rejected = [(case["id"], r.reason, [c.reason for c in r.citations]) for case, r in good if not r.supported]
        rate = len(rejected) / len(good)
        self.assertLessEqual(rate, MAX_FALSE_REJECTION, f"good claims rejected: {rejected}")

    def test_known_limitations_pass(self):
        # False claims with real quotes and no numbers get through. This is
        # the documented limit of the verifier, not a bug to hide.
        for case, r in self.cases("limitation"):
            with self.subTest(case["id"]):
                self.assertTrue(r.supported)

    def test_set_is_balanced(self):
        self.assertGreaterEqual(len(self.cases("good")), 20)
        self.assertGreaterEqual(len(self.cases("bad")), 15)

    def test_highlights_land_on_the_cited_page(self):
        for case, r in self.cases("good"):
            for c in r.citations:
                clause = self.index.get(c.clause_id)
                self.assertTrue(c.highlights)
                self.assertTrue(all(h.page == clause.page for h in c.highlights))


if __name__ == "__main__":
    unittest.main()
