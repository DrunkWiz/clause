"""The synthetic letters and EOBs, and the rules run on their ground truth."""

import unittest
from datetime import date
from pathlib import Path

from clause.index.model import ClauseIndex
from clause.rules import no_surprises as nsa
from clause.rules import notice, reason_codes
from clause.rules.base import regs
from clause.synthetic import truth as tr
from clause.synthetic.documents import ALL, HEADER
from clause.verify.verifier import verify_claim

ROOT = Path(__file__).resolve().parents[2]

try:
    from clause.synthetic.generate import render
except ImportError:  # pdfplumber missing
    render = None


def index(*doc_ids) -> ClauseIndex:
    idx = ClauseIndex()
    for d in doc_ids:
        idx = idx.merge(ClauseIndex.from_json((ROOT / "data" / "indexes" / f"{d}.json").read_text(encoding="utf-8")))
    return idx


DENIALS = [d for d in ALL if d.kind == "denial"]
EOBS = [d for d in ALL if d.kind == "eob"]


class GeneratedFilesTest(unittest.TestCase):
    @unittest.skipIf(render is None, "pdfplumber not installed")
    def test_committed_pdfs_match_generator(self):
        for d in ALL:
            with self.subTest(d.doc_id):
                self.assertEqual(render(d), (ROOT / "data" / "synthetic" / f"{d.doc_id}.pdf").read_bytes(), "run: python scripts/make_synthetic.py")

    def test_every_page_says_synthetic(self):
        for d in ALL:
            idx = index(d.doc_id)
            pages = {c.page for c in idx.clauses.values()}
            marked = {c.page for c in idx.clauses.values() if c.text == HEADER}
            self.assertEqual(pages, marked, d.doc_id)

    def test_truth_citations_verify(self):
        for d in ALL:
            t = tr.load_truth(d.doc_id)
            idx = index(d.doc_id)
            self.assertTrue(t["synthetic"])
            for tag in t["tags"]:
                claim = {"text": "Located.", "citations": [tr.citation(t, tag)]}
                self.assertTrue(verify_claim(claim, idx).supported, (d.doc_id, tag))

    def test_plan_documents_exist(self):
        for d in ALL:
            for p in d.plan_docs:
                self.assertTrue((ROOT / "data" / "indexes" / f"{p}.json").exists(), p)


class DenialRulesTest(unittest.TestCase):
    def test_notice_gaps_are_exactly_the_planned_ones(self):
        for d in DENIALS:
            with self.subTest(d.doc_id):
                t = tr.load_truth(d.doc_id)
                report = notice.check_notice(tr.notice_findings(t), index(d.doc_id), care=t["care"], basis=t["basis"])
                self.assertEqual(sorted(e.element.id for e in report.not_found), sorted(t["gaps"]))
                self.assertEqual(report.exhaustion is not None, bool(t["gaps"]))

    def test_ambetter_letter_hides_the_plan_provision(self):
        t = tr.load_truth("synthetic-denial-ambetter-tx")
        self.assertNotIn("plan_provision", t["tags"])
        self.assertEqual(t["gaps"], ["plan_provision"])

    def test_notice_dates_are_on_the_letter(self):
        for d in DENIALS:
            t = tr.load_truth(d.doc_id)
            tag = t["tags"]["notice_date"]["text"]
            nd = date.fromisoformat(t["notice_date"])
            self.assertEqual(tag, f"{nd:%B} {nd.day}, {nd.year}")


class EobRulesTest(unittest.TestCase):
    def test_er_eob_flags_no_surprises(self):
        t = tr.load_truth("synthetic-eob-ambetter-er")
        idx = index(t["doc_id"], *t["plan_docs"]).merge(regs())
        r = nsa.check_bill(
            t["setting"],
            t["provider_in_network"],
            out_of_network_cost_sharing=tr.citation(t, "out_of_network_cost_sharing"),
            balance_bill=tr.citation(t, "balance_bill"),
        )
        self.assertEqual(r.status, nsa.PROTECTED)
        self.assertEqual(len(r.flags), 2)
        for c in r.claims + r.flags:
            self.assertTrue(verify_claim(c, idx).supported, c["text"])
        # The PR lines add up to what the EOB says is owed.
        self.assertEqual(reason_codes.check_patient_share(tr.eob_lines(t), tr.patient_owes(t)), [])

    def test_surgery_eob_flags_anesthesia_and_mismatch(self):
        t = tr.load_truth("synthetic-eob-fidelis-surgery")
        idx = index(t["doc_id"]).merge(regs())
        r = nsa.check_bill(
            t["setting"],
            t["provider_in_network"],
            facility_in_network=t["facility_in_network"],
            specialty=t["specialty"],
            balance_bill=tr.citation(t, "balance_bill"),
        )
        self.assertEqual(r.status, nsa.PROTECTED)
        self.assertEqual([f["rule_id"] for f in r.flags], ["nsa.flag.balance_bill"])
        (mismatch,) = reason_codes.check_patient_share(tr.eob_lines(t), tr.patient_owes(t))
        for c in [*r.claims, *r.flags, mismatch, *(x for l in tr.eob_lines(t) for x in reason_codes.explain(l).claims)]:
            res = verify_claim(c, idx)
            self.assertTrue(res.supported, (c["text"], res.reason, res.missing_numbers))


if __name__ == "__main__":
    unittest.main()
