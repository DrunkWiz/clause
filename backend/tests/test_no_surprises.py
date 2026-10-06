import unittest

from clause.index.model import ClauseIndex, Document
from clause.rules import no_surprises as nsa
from clause.rules.base import regs, rule_claim
from clause.verify.verifier import verify_claim
from tests.fixtures.make_mini_index import build_clause

DOC = "bill-demo"
LINES = [
    "Emergency room visit, out-of-network: 50% coinsurance applied",
    "Amount billed by provider above plan payment: balance due from patient",
]


def index():
    idx = ClauseIndex()
    idx.add_document(Document(DOC, "bill-demo.pdf", "4" * 64, ((612.0, 792.0),)), [build_clause(DOC, 1, i + 1, [t], 72 + 20 * i) for i, t in enumerate(LINES)])
    return idx.merge(regs())


INDEX = index()
OON = {"doc": DOC, "clause_id": f"{DOC}#p1.1", "quote": LINES[0]}
BALANCE = {"doc": DOC, "clause_id": f"{DOC}#p1.2", "quote": LINES[1]}


def all_verify(test, result):
    for c in result.claims + result.flags:
        r = verify_claim(c, INDEX)
        test.assertTrue(r.supported, (c["text"], r.reason, r.missing_numbers, [x.reason for x in r.citations]))


class TableTest(unittest.TestCase):
    def test_every_ref_verifies(self):
        for ref in nsa.all_refs():
            with self.subTest(ref.label):
                r = verify_claim(rule_claim("t", "Regulation text.", ref), regs())
                self.assertTrue(r.supported, (ref.label, r.citations[0].reason))


class EmergencyTest(unittest.TestCase):
    def test_protected_and_flags_out_of_network_cost_sharing(self):
        r = nsa.check_bill(nsa.EMERGENCY, provider_in_network=False, out_of_network_cost_sharing=OON, balance_bill=BALANCE)
        self.assertEqual(r.status, nsa.PROTECTED)
        self.assertEqual([f["rule_id"] for f in r.flags], ["nsa.flag.cost_sharing", "nsa.flag.balance_bill"])
        all_verify(self, r)

    def test_no_flags_without_evidence(self):
        r = nsa.check_bill(nsa.EMERGENCY, provider_in_network=False)
        self.assertEqual(r.flags, ())

    def test_consent_adds_post_stabilization_caveat(self):
        r = nsa.check_bill(nsa.EMERGENCY, provider_in_network=False, consent_signed=True)
        self.assertIn("nsa.er.post_stabilization", [c["rule_id"] for c in r.claims])
        all_verify(self, r)


class FacilityTest(unittest.TestCase):
    def check(self, **kw):
        return nsa.check_bill(nsa.NONEMERGENCY_AT_IN_NETWORK_FACILITY, provider_in_network=False, facility_in_network=True, **kw)

    def test_anesthesiologist_protected_despite_consent(self):
        r = self.check(specialty="Anesthesiology", consent_signed=True, balance_bill=BALANCE)
        self.assertEqual(r.status, nsa.PROTECTED)
        cited = [c["label"] for claim in r.claims for c in claim["citations"]]
        self.assertIn("45 CFR 149.420(b)(1)(i)", cited)
        self.assertEqual(len(r.flags), 1)
        all_verify(self, r)

    def test_lab_is_diagnostic(self):
        r = self.check(specialty="Clinical laboratory", consent_signed=True)
        self.assertEqual(r.status, nsa.PROTECTED)
        self.assertIn("45 CFR 149.420(b)(1)(iii)", [c["label"] for claim in r.claims for c in claim["citations"]])

    def test_unforeseen_urgent_need(self):
        r = self.check(specialty="Orthopedic surgery", consent_signed=True, unforeseen_urgent=True)
        self.assertEqual(r.status, nsa.PROTECTED)
        all_verify(self, r)

    def test_no_in_network_option(self):
        r = self.check(specialty="Orthopedic surgery", consent_signed=True, no_in_network_option=True)
        self.assertEqual(r.status, nsa.PROTECTED)

    def test_signed_consent_may_waive(self):
        r = self.check(specialty="Orthopedic surgery", consent_signed=True, balance_bill=BALANCE)
        self.assertEqual(r.status, nsa.MAY_HAVE_WAIVED)
        self.assertEqual(r.flags, ())
        self.assertTrue(any("consent form" in n for n in r.notes))

    def test_consent_unknown(self):
        r = self.check(specialty="Orthopedic surgery", balance_bill=BALANCE)
        self.assertEqual(r.status, nsa.PROTECTED_UNLESS_CONSENT)
        self.assertIn("unless you validly consented", r.flags[0]["text"])
        all_verify(self, r)

    def test_out_of_network_facility_not_covered(self):
        r = nsa.check_bill(nsa.NONEMERGENCY_AT_IN_NETWORK_FACILITY, provider_in_network=False, facility_in_network=False, balance_bill=BALANCE)
        self.assertEqual((r.status, r.flags), (nsa.NOT_COVERED, ()))

    def test_in_network_provider_not_covered(self):
        r = nsa.check_bill(nsa.NONEMERGENCY_AT_IN_NETWORK_FACILITY, provider_in_network=True, facility_in_network=True)
        self.assertEqual(r.status, nsa.NOT_COVERED)


class OtherSettingsTest(unittest.TestCase):
    def test_air_ambulance(self):
        r = nsa.check_bill(nsa.AIR_AMBULANCE, provider_in_network=False, out_of_network_cost_sharing=OON, balance_bill=BALANCE)
        self.assertEqual(r.status, nsa.PROTECTED)
        self.assertEqual([f["rule_id"] for f in r.flags], ["nsa.flag.cost_sharing"])  # no balance-bill rule cited for air here
        all_verify(self, r)

    def test_ground_ambulance(self):
        r = nsa.check_bill(nsa.GROUND_AMBULANCE, provider_in_network=False, balance_bill=BALANCE)
        self.assertEqual((r.status, r.claims, r.flags), (nsa.NOT_COVERED, (), ()))
        self.assertEqual(len(r.notes), 1)
        self.assertIn("ground ambulances", r.notes[0])

    def test_bad_setting(self):
        with self.assertRaises(ValueError):
            nsa.check_bill("spa", provider_in_network=False)

    def test_specialty_matching(self):
        self.assertEqual(nsa.ancillary_category("Emergency Medicine"), "emergency_anesthesia_pathology_radiology_neonatology")
        self.assertEqual(nsa.ancillary_category("Hospitalist"), "assistant_surgeon_hospitalist_intensivist")
        self.assertIsNone(nsa.ancillary_category("Dermatology"))
        self.assertIsNone(nsa.ancillary_category(None))


if __name__ == "__main__":
    unittest.main()
