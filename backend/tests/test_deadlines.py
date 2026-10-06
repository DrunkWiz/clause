import unittest
from datetime import date

from clause.rules import deadlines as dl
from clause.rules.base import Ref, regs, rule_claim
from clause.verify.verifier import verify_claim


def by_id(items, id_):
    return next(d for d in items if d.id == id_)


class RuleTableTest(unittest.TestCase):
    """Every regulation reference must verify against the fetched text."""

    def test_every_ref_verifies(self):
        for ref in dl.all_refs():
            with self.subTest(ref.label):
                r = verify_claim(rule_claim("t", "Regulation text.", ref), regs())
                self.assertTrue(r.supported, (ref.label, r.citations[0].reason))
                clause = regs().get(r.citations[0].clause_id)
                self.assertEqual(clause.label, ref.label)

    def test_wrong_quote_is_rejected(self):
        bad = Ref("29 CFR 2560.503-1(h)(3)(i)", "Provide claimants at least 90 days following receipt of a notification")
        self.assertFalse(verify_claim(rule_claim("t", "x", bad), regs()).supported)

    def test_unknown_label_raises(self):
        with self.assertRaises(KeyError):
            Ref("45 CFR 999.1(a)", "anything at all here").citation()


class OutputVerifiesTest(unittest.TestCase):
    SCENARIOS = [
        dict(notice_received=date(2026, 10, 5), care=dl.POST_SERVICE),
        dict(notice_received=date(2026, 10, 5), care=dl.PRE_SERVICE, appeal_received=date(2026, 11, 2)),
        dict(notice_received=date(2026, 10, 5), care=dl.URGENT, appeal_received=date(2026, 10, 6), final_denial_received=date(2026, 10, 8)),
        dict(notice_received=date(2026, 6, 1), care=dl.POST_SERVICE, final_denial_received=date(2027, 7, 25)),  # Thanksgiving
        dict(notice_received=date(2026, 6, 1), care=dl.POST_SERVICE, final_denial_received=date(2026, 9, 2)),  # weekend
    ]

    def test_every_claim_verifies(self):
        for s in self.SCENARIOS:
            for d in dl.appeal_deadlines(**s):
                for claim in d.claims:
                    with self.subTest(s=s, id=d.id):
                        r = verify_claim(claim, regs())
                        self.assertTrue(r.supported, (claim["text"], r.reason, r.missing_numbers, [c.reason for c in r.citations]))
                        self.assertEqual(claim["source"], "rule")

    def test_to_dict(self):
        d = dl.appeal_deadlines(date(2026, 10, 5), dl.POST_SERVICE)[0].to_dict()
        self.assertEqual(d["due"], "2027-04-03")


class InternalAppealTest(unittest.TestCase):
    def test_180_days(self):
        d = by_id(dl.appeal_deadlines(date(2026, 10, 5), dl.POST_SERVICE), "internal_appeal_filing")
        self.assertEqual(d.due, date(2027, 4, 3))
        self.assertIn("180 days", d.claims[0]["text"])
        self.assertIn("Saturday, April 3, 2027", d.claims[0]["text"])

    def test_no_weekend_extension_for_internal_appeal(self):
        d = by_id(dl.appeal_deadlines(date(2026, 10, 5), dl.POST_SERVICE), "internal_appeal_filing")
        self.assertEqual(d.due, date(2027, 4, 3))  # a Saturday: not moved
        self.assertTrue(any("no extension" in n for n in d.notes))
        weekday = by_id(dl.appeal_deadlines(date(2026, 10, 7), dl.POST_SERVICE), "internal_appeal_filing")
        self.assertFalse(any("no extension" in n for n in weekday.notes))

    def test_180_days_across_leap_day(self):
        d = by_id(dl.appeal_deadlines(date(2027, 12, 1), dl.POST_SERVICE), "internal_appeal_filing")
        self.assertEqual(d.due, date(2028, 5, 29))

    def test_decision_windows(self):
        received = date(2026, 11, 2)
        expected = {dl.URGENT: date(2026, 11, 5), dl.PRE_SERVICE: date(2026, 12, 2), dl.POST_SERVICE: date(2027, 1, 1)}
        for care, due in expected.items():
            d = by_id(dl.appeal_deadlines(date(2026, 10, 5), care, appeal_received=received), "internal_appeal_decision")
            self.assertEqual(d.due, due, care)

    def test_decision_unknown_until_appeal_received(self):
        d = by_id(dl.appeal_deadlines(date(2026, 10, 5), dl.PRE_SERVICE), "internal_appeal_decision")
        self.assertIsNone(d.due)
        self.assertIn("30 days", d.claims[0]["text"])

    def test_urgent_says_72_hours(self):
        d = by_id(dl.appeal_deadlines(date(2026, 10, 5), dl.URGENT), "internal_appeal_decision")
        self.assertIn("72 hours", d.claims[0]["text"])

    def test_bad_care_type(self):
        with self.assertRaises(ValueError):
            dl.appeal_deadlines(date(2026, 10, 5), "emergency")


class FourMonthsTest(unittest.TestCase):
    def test_regulation_example(self):
        # 147.136(d)(2)(i): "if the date of receipt of the notice is October 30,
        # because there is no February 30, the request must be filed by March 1."
        self.assertEqual(dl.add_months_rule(date(2026, 10, 30), 4), date(2027, 3, 1))

    def test_corresponding_date(self):
        self.assertEqual(dl.add_months_rule(date(2026, 11, 15), 4), date(2027, 3, 15))
        self.assertEqual(dl.add_months_rule(date(2027, 1, 31), 4), date(2027, 5, 31))

    def test_leap_years(self):
        self.assertEqual(dl.add_months_rule(date(2026, 10, 29), 4), date(2027, 3, 1))
        self.assertEqual(dl.add_months_rule(date(2027, 10, 29), 4), date(2028, 2, 29))

    def test_across_year_end(self):
        self.assertEqual(dl.add_months_rule(date(2026, 8, 31), 4), date(2026, 12, 31))
        self.assertEqual(dl.add_months_rule(date(2026, 9, 30), 4), date(2027, 1, 30))
        self.assertEqual(dl.add_months_rule(date(2026, 12, 31), 4), date(2027, 5, 1))


class FilingDayTest(unittest.TestCase):
    def test_holidays_2026(self):
        h = dl.federal_holidays(2026)
        self.assertEqual(
            sorted(h),
            [date(2026, 1, 1), date(2026, 1, 19), date(2026, 2, 16), date(2026, 5, 25), date(2026, 6, 19), date(2026, 7, 4),
             date(2026, 9, 7), date(2026, 10, 12), date(2026, 11, 11), date(2026, 11, 26), date(2026, 12, 25)],
        )

    def test_weekday_unchanged(self):
        self.assertEqual(dl.next_filing_day(date(2027, 3, 1)), (date(2027, 3, 1), []))

    def test_weekend_rolls_to_monday(self):
        self.assertEqual(dl.next_filing_day(date(2027, 1, 2)), (date(2027, 1, 4), ["saturday", "sunday"]))

    def test_holiday_after_weekend(self):
        # May 29 2027 is a Saturday; Monday May 31 is Memorial Day.
        self.assertEqual(dl.next_filing_day(date(2027, 5, 29)), (date(2027, 6, 1), ["saturday", "sunday", "memorial"]))

    def test_observed_day_is_not_a_holiday_here(self):
        # July 4 2027 is a Sunday. The Monday "observed" holiday comes from
        # 6103(b), which covers pay and leave only, so Monday is a filing day.
        self.assertEqual(dl.next_filing_day(date(2027, 7, 4)), (date(2027, 7, 5), ["sunday"]))


class ExternalReviewTest(unittest.TestCase):
    def test_unknown_until_final_denial(self):
        d = by_id(dl.appeal_deadlines(date(2026, 10, 5), dl.POST_SERVICE), "external_review_filing")
        self.assertIsNone(d.due)
        self.assertEqual(len(d.claims), 2)

    def test_plain_date(self):
        d = by_id(dl.appeal_deadlines(date(2026, 6, 1), dl.POST_SERVICE, final_denial_received=date(2026, 10, 30)), "external_review_filing")
        self.assertEqual(d.due, date(2027, 3, 1))
        self.assertIsNone(d.unextended)

    def test_weekend_extension_and_safe_date(self):
        d = by_id(dl.appeal_deadlines(date(2026, 6, 1), dl.POST_SERVICE, final_denial_received=date(2026, 9, 2)), "external_review_filing")
        self.assertEqual((d.due, d.unextended), (date(2027, 1, 4), date(2027, 1, 2)))
        self.assertTrue(any("Saturday, January 2, 2027" in n for n in d.notes))
        labels = [c["label"] for c in d.claims[0]["citations"]]
        self.assertIn("45 CFR 147.136(d)(2)(i)", labels)

    def test_holiday_extension_cites_the_holiday(self):
        d = by_id(dl.appeal_deadlines(date(2026, 6, 1), dl.POST_SERVICE, final_denial_received=date(2027, 7, 25)), "external_review_filing")
        self.assertEqual(d.due, date(2027, 11, 26))
        quotes = [c["quote"] for c in d.claims[0]["citations"]]
        self.assertIn("Thanksgiving Day, the fourth Thursday in November.", quotes)

    def test_decision_standard_and_expedited(self):
        std = by_id(dl.appeal_deadlines(date(2026, 10, 5), dl.POST_SERVICE), "external_review_decision")
        exp = by_id(dl.appeal_deadlines(date(2026, 10, 5), dl.URGENT), "external_review_decision")
        self.assertIn("45 days", std.claims[0]["text"])
        self.assertIn("72 hours", exp.claims[0]["text"])


if __name__ == "__main__":
    unittest.main()
