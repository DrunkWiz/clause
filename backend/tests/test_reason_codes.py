import unittest

from clause.index.model import ClauseIndex, Document
from clause.rules import reason_codes as rc
from clause.rules.base import regs, rule_claim
from clause.rules.notice import EXPERIMENTAL, MEDICAL_NECESSITY, MISSING_INFORMATION, OTHER
from clause.verify.verifier import NUMBER_NOT_IN_QUOTE, verify_claim
from tests.fixtures.make_mini_index import build_clause

DOC = "eob-demo"
LINES = [
    "Adjustment CO-45: $640.00 charge exceeds the contracted amount",
    "Adjustment PR-1: $900.00 applied to your deductible",
    "Adjustment PR-2: $60.00 coinsurance for this service",
    "Patient may owe: $960.00 for this claim",
    "Adjustment CO-50 1,200.00 not medically necessary per payer",
]


def eob_index():
    idx = ClauseIndex()
    idx.add_document(
        Document(DOC, "eob-demo.pdf", "3" * 64, ((612.0, 792.0),)),
        [build_clause(DOC, 1, i + 1, [t], 72 + 20 * i) for i, t in enumerate(LINES)],
    )
    return idx.merge(regs())


INDEX = eob_index()


def cit(n, quote=None):
    return {"doc": DOC, "clause_id": f"{DOC}#p1.{n}", "quote": quote or LINES[n - 1]}


CO45 = {"group": "CO", "code": "45", "amount": "640.00", "citation": cit(1)}
PR1 = {"group": "PR", "code": "1", "amount": "900", "citation": cit(2)}
PR2 = {"group": "PR", "code": "2", "amount": "60.00", "citation": cit(3)}
OWES = {"amount": "960.00", "citation": cit(4)}
CO50 = {"group": "CO", "code": "50", "amount": "1200", "citation": cit(5)}


def supported(claim):
    r = verify_claim(claim, INDEX)
    return r.supported, r


class TableTest(unittest.TestCase):
    def test_refs_verify(self):
        for ref in rc.all_refs():
            self.assertTrue(verify_claim(rule_claim("t", "Group codes.", ref), regs()).supported, ref.quote)

    def test_codes_well_formed(self):
        for code, c in rc.CARCS.items():
            self.assertTrue(code.isdigit() and code == c.code and not code.startswith("0"))
            self.assertTrue(c.meaning and c.next_step)


class ExplainTest(unittest.TestCase):
    def test_contractual_obligation_is_the_providers(self):
        e = rc.explain(CO45)
        self.assertTrue(e.known)
        (claim,) = e.claims
        self.assertIn("$640.00", claim["text"])
        self.assertIn("the provider, not you", claim["text"])
        ok, r = supported(claim)
        self.assertTrue(ok, r)

    def test_patient_responsibility(self):
        (claim,) = rc.explain(PR1).claims
        self.assertIn("responsibility to you", claim["text"])
        self.assertTrue(supported(claim)[0])

    def test_amount_without_dollar_sign(self):
        (claim,) = rc.explain(CO50).claims
        self.assertIn("1,200.00", claim["text"])
        self.assertNotIn("$", claim["text"])
        self.assertTrue(supported(claim)[0])

    def test_wrong_extracted_amount_is_caught(self):
        bad = dict(CO45, amount="650.00")
        ok, r = supported(rc.explain(bad).claims[0])
        self.assertFalse(ok)
        self.assertEqual(r.reason, NUMBER_NOT_IN_QUOTE)

    def test_other_groups_make_no_responsibility_claim(self):
        self.assertEqual(rc.explain({"group": "OA", "code": "18", "citation": cit(1)}).claims, ())
        self.assertEqual(rc.explain({"group": "PI", "code": "45", "citation": cit(1)}).claims, ())

    def test_no_citation_no_claim(self):
        self.assertEqual(rc.explain({"group": "CO", "code": "45", "amount": "1"}).claims, ())

    def test_unknown_code(self):
        e = rc.explain({"group": "co", "code": "0999"})
        self.assertFalse(e.known)
        self.assertEqual((e.group, e.code), ("CO", "999"))
        self.assertIn("x12.org", e.to_dict()["x12_url"])

    def test_leading_zeros(self):
        self.assertEqual(rc.explain({"group": "CO", "code": "050"}).code, "50")


class BasisTest(unittest.TestCase):
    def test_basis(self):
        self.assertEqual(rc.denial_basis([{"code": "50"}]), MEDICAL_NECESSITY)
        self.assertEqual(rc.denial_basis([{"code": "16"}, {"code": "55"}]), EXPERIMENTAL)
        self.assertEqual(rc.denial_basis([{"code": "16"}]), MISSING_INFORMATION)
        self.assertEqual(rc.denial_basis([{"code": "197"}, {"code": "xyz"}]), OTHER)
        self.assertEqual(rc.denial_basis([]), OTHER)


class PatientShareTest(unittest.TestCase):
    def test_matches(self):
        self.assertEqual(rc.check_patient_share([CO45, PR1, PR2], OWES), [])

    def test_mismatch(self):
        (claim,) = rc.check_patient_share([CO45, PR1], OWES)
        self.assertEqual(claim["rule_id"], "reason_code.pr_mismatch")
        self.assertIn("$960.00", claim["text"])
        self.assertIn("$900.00", claim["text"])
        ok, r = supported(claim)
        self.assertTrue(ok, r)

    def test_no_pr_lines(self):
        (claim,) = rc.check_patient_share([CO45], OWES)
        self.assertEqual(claim["rule_id"], "reason_code.no_pr")
        self.assertTrue(supported(claim)[0])

    def test_nothing_owed_or_missing(self):
        self.assertEqual(rc.check_patient_share([CO45], {"amount": "0", "citation": cit(4)}), [])
        self.assertEqual(rc.check_patient_share([CO45], None), [])
        self.assertEqual(rc.check_patient_share([CO45], {"amount": "x", "citation": cit(4)}), [])
        self.assertEqual(rc.check_patient_share([CO45], {"amount": "960"}), [])


if __name__ == "__main__":
    unittest.main()
