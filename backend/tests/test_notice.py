import unittest

from clause.index.model import ClauseIndex
from clause.rules import notice as n
from clause.rules.base import regs
from clause.verify.verifier import verify_claim
from tests.fixtures.make_mini_index import build_clause
from clause.index.model import Document

DOC = "letter-demo"

# A synthetic denial letter with every element, one clause each.
LETTER_TEXT = {
    "reason": "We denied this claim because the MRI was not medically necessary for your condition.",
    "plan_provision": "This decision is based on Section 7.4, Medical Necessity, of your Evidence of Coverage.",
    "denial_code": "Denial code CO-50: these are non-covered services because this is not deemed a medical necessity.",
    "date_of_service": "Date of service: March 3, 2026.",
    "provider_name": "Provider: Lakeside Imaging Center.",
    "claim_amount": "Claim amount: $1,840.00.",
    "codes_on_request": "You may ask us for the diagnosis code and treatment code for this claim and what they mean.",
    "review_procedures": "You may appeal within 180 days of receiving this letter and we will decide within 60 days.",
    "appeal_and_external_review": "To start an appeal, write to us; if we uphold the denial you may ask for an independent external review.",
    "consumer_assistance": "For help, contact the Texas Department of Insurance consumer help line at 1-800-252-3439.",
    "clinical_explanation": "We will give you the clinical reasons for this decision free of charge if you ask.",
}
IDS = list(LETTER_TEXT)


def letter_index(skip=()):
    idx = ClauseIndex()
    clauses = [build_clause(DOC, 1, i + 1, [LETTER_TEXT[k]], 72 + 30 * i) for i, k in enumerate(IDS) if k not in skip]
    idx.add_document(Document(DOC, "letter-demo.pdf", "2" * 64, ((612.0, 792.0),)), clauses)
    return idx


def finding(idx, element, quote_words=8):
    """A model finding quoting the start of the clause holding `element`."""
    text = LETTER_TEXT[element]
    clause = next(c for c in idx.clauses.values() if c.text == text)
    quote = " ".join(text.split()[:quote_words])
    return {"element": element, "text": f"The letter includes: {n.ELEMENTS[n.ELEMENT_IDS.index(element)].title}.", "citations": [{"doc": DOC, "clause_id": clause.clause_id, "quote": quote}]}


def status(report, eid):
    return next(e.status for e in report.elements if e.element.id == eid)


class RuleTableTest(unittest.TestCase):
    def test_every_requirement_claim_verifies(self):
        for e in n.ELEMENTS:
            with self.subTest(e.id):
                r = verify_claim(n.rule_claim("t", e.requirement, *e.refs), regs())
                self.assertTrue(r.supported, (e.id, r.reason, r.missing_numbers, [c.reason for c in r.citations]))

    def test_exhaustion_refs_verify(self):
        r = verify_claim(n.rule_claim("t", "Deemed exhaustion.", *n.DEEMED_EXHAUSTION), regs())
        self.assertTrue(r.supported)

    def test_ids_unique(self):
        self.assertEqual(len(n.ELEMENT_IDS), len(set(n.ELEMENT_IDS)))


class CheckNoticeTest(unittest.TestCase):
    def complete(self, idx=None, skip_findings=()):
        idx = idx or letter_index()
        return idx, [finding(idx, k) for k in IDS if k not in skip_findings]

    def test_complete_letter_has_no_gaps(self):
        idx, findings = self.complete()
        r = n.check_notice(findings, idx, care="post_service", basis=n.MEDICAL_NECESSITY)
        self.assertEqual(r.not_found, ())
        self.assertIsNone(r.exhaustion)
        self.assertEqual(status(r, "internal_criterion"), n.CHECK)
        self.assertEqual(status(r, "expedited_process"), n.NOT_APPLICABLE)
        self.assertEqual(status(r, "information_needed"), n.NOT_APPLICABLE)

    def test_each_missing_element_is_reported_alone(self):
        for k in IDS:
            with self.subTest(k):
                idx = letter_index(skip=(k,))
                findings = [finding(idx, x) for x in IDS if x != k]
                r = n.check_notice(findings, idx, care="post_service", basis=n.MEDICAL_NECESSITY)
                self.assertEqual([e.element.id for e in r.not_found], [k])
                self.assertIsNotNone(r.exhaustion)

    def test_invented_quote_does_not_count(self):
        idx = letter_index(skip=("plan_provision",))
        findings = [finding(idx, x) for x in IDS if x != "plan_provision"]
        # The model claims the provision is there, quoting text that is not in the letter.
        findings.append({"element": "plan_provision", "text": "The letter cites the plan.", "citations": [{"doc": DOC, "clause_id": f"{DOC}#p1.1", "quote": "This decision is based on Section 7.4 of your plan"}]})
        r = n.check_notice(findings, idx, care="post_service", basis=n.MEDICAL_NECESSITY)
        self.assertEqual([e.element.id for e in r.not_found], ["plan_provision"])

    def test_conditional_elements(self):
        idx, findings = self.complete()
        pre = n.check_notice(findings, idx, care="pre_service", basis=n.OTHER)
        self.assertEqual(status(pre, "claim_amount"), n.PRESENT)  # found anyway
        idx2 = letter_index(skip=("claim_amount", "clinical_explanation"))
        f2 = [finding(idx2, x) for x in IDS if x not in ("claim_amount", "clinical_explanation")]
        pre2 = n.check_notice(f2, idx2, care="pre_service", basis=n.OTHER)
        self.assertEqual(status(pre2, "claim_amount"), n.NOT_APPLICABLE)
        self.assertEqual(status(pre2, "clinical_explanation"), n.NOT_APPLICABLE)
        self.assertEqual(pre2.not_found, ())

    def test_urgent_needs_expedited_process(self):
        idx, findings = self.complete()
        r = n.check_notice(findings, idx, care="urgent", basis=n.MEDICAL_NECESSITY)
        self.assertEqual([e.element.id for e in r.not_found], ["expedited_process"])

    def test_missing_information_basis(self):
        idx, findings = self.complete()
        r = n.check_notice(findings, idx, care="post_service", basis=n.MISSING_INFORMATION)
        self.assertEqual([e.element.id for e in r.not_found], ["information_needed"])

    def test_malformed_and_unknown_findings(self):
        idx, findings = self.complete()
        findings += [None, "x", {"element": "made_up", "text": "t", "citations": []}]
        r = n.check_notice(findings, idx, care="post_service", basis=n.MEDICAL_NECESSITY)
        self.assertEqual(r.not_found, ())
        self.assertEqual(r.unknown_findings, ("made_up",))
        self.assertEqual(n.check_notice("not a list", idx, care="post_service").not_found[0].element.id, "reason")

    def test_bad_basis(self):
        with self.assertRaises(ValueError):
            n.check_notice([], letter_index(), care="post_service", basis="vibes")

    def test_report_claims_verify(self):
        idx = letter_index(skip=("plan_provision",))
        r = n.check_notice([finding(idx, x) for x in IDS if x != "plan_provision"], idx, care="post_service", basis=n.MEDICAL_NECESSITY)
        for e in r.elements:
            self.assertTrue(verify_claim(e.requirement, regs()).supported, e.element.id)
        self.assertTrue(verify_claim(r.exhaustion, regs()).supported)
        d = r.to_dict()
        self.assertEqual(d["not_found"], ["plan_provision"])


if __name__ == "__main__":
    unittest.main()
