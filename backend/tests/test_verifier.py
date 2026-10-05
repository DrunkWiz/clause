import copy
import json
import unittest
from pathlib import Path

from clause.index.model import ClauseIndex
from clause.verify import verifier as v
from clause.verify.normalise import norm

INDEX = ClauseIndex.from_json((Path(__file__).parent / "fixtures" / "mini_index.json").read_text(encoding="utf-8"))

SBC = "sbc-demo"
DEN = "denial-demo"


def cite(clause_id, quote, doc=None):
    return {"doc": doc or clause_id.split("#")[0], "clause_id": clause_id, "quote": quote}


def check(clause_id, quote, doc=None):
    return v.verify_citation(cite(clause_id, quote, doc), INDEX)


def claim(text, *citations):
    return v.verify_claim({"text": text, "citations": list(citations)}, INDEX)


class CitationTest(unittest.TestCase):
    def assertOk(self, r):
        self.assertTrue(r.ok, r)
        self.assertIsNone(r.reason)

    def assertFails(self, r, reason):
        self.assertFalse(r.ok, r)
        self.assertEqual(r.reason, reason)
        self.assertEqual(r.spans, ())
        self.assertEqual(r.highlights, ())

    def test_exact_quote(self):
        self.assertOk(check("denial-demo#p1.1", "the service is not covered"))

    def test_unknown_clause(self):
        self.assertFails(check("denial-demo#p9.9", "the service is not covered"), v.UNKNOWN_CLAUSE)

    def test_doc_mismatch(self):
        self.assertFails(check("denial-demo#p1.1", "the service is not covered", doc=SBC), v.DOC_MISMATCH)

    def test_quote_in_a_different_clause(self):
        # Real text from denial-demo#p1.2, but cited against p1.1.
        self.assertFails(check("denial-demo#p1.1", "180 calendar days of the date"), v.QUOTE_NOT_IN_CLAUSE)

    def test_paraphrase(self):
        self.assertFails(check("denial-demo#p1.1", "the service is not included"), v.QUOTE_NOT_IN_CLAUSE)

    def test_dropped_negation(self):
        self.assertFails(check("sbc-demo#p1.3", "Benefits are covered for cosmetic surgery"), v.QUOTE_NOT_IN_CLAUSE)

    def test_too_short(self):
        self.assertFails(check("denial-demo#p1.1", "covered"), v.QUOTE_TOO_SHORT)
        self.assertFails(check("denial-demo#p1.1", "is not covered"), v.QUOTE_TOO_SHORT)

    def test_whole_short_clause_allowed(self):
        self.assertOk(check("sbc-demo#p2.3", "Not covered."))

    def test_partial_word_does_not_match(self):
        self.assertFails(check("denial-demo#p1.1", "have denied your clai"), v.QUOTE_NOT_IN_CLAUSE)

    def test_normalisation_cases_pass(self):
        self.assertOk(check("sbc-demo#p1.3", "Benefits are not covered for cosmetic surgery or services"))
        self.assertOk(check("sbc-demo#p2.2", "If you don't get prior authorization, benefits will be reduced by 50%"))
        self.assertOk(check("denial-demo#p1.2", "You may appeal within 180 calendar days"))
        self.assertOk(check("sbc-demo#p1.1", "overall deductible? $1500 individual"))
        self.assertOk(check("sbc-demo#p1.2", "Specialist visit - $80.50 copay"))

    def test_decimal_mismatch(self):
        self.assertFails(check("sbc-demo#p1.2", "Specialist visit - $8050 copay"), v.QUOTE_NOT_IN_CLAUSE)

    def test_ellipsis_in_order(self):
        self.assertOk(check("sbc-demo#p2.2", "Prior authorization is required for ... benefits will be reduced by 50%"))
        self.assertOk(check("sbc-demo#p2.2", "Prior authorization is required for…benefits will be reduced"))

    def test_ellipsis_out_of_order(self):
        self.assertFails(check("sbc-demo#p2.2", "benefits will be reduced by ... Prior authorization is required"), v.QUOTE_NOT_IN_CLAUSE)

    def test_ellipsis_fragment_too_short(self):
        self.assertFails(check("sbc-demo#p2.2", "Prior authorization is required ... by 50%"), v.QUOTE_TOO_SHORT)

    def test_leading_ellipsis_ignored(self):
        self.assertOk(check("sbc-demo#p2.2", "...benefits will be reduced by 50%"))

    def test_quote_spanning_two_clauses(self):
        self.assertFails(check("denial-demo#p1.1", "not covered under your plan. You may appeal"), v.QUOTE_NOT_IN_CLAUSE)

    def test_empty_quote(self):
        self.assertFails(check("denial-demo#p1.1", ""), v.EMPTY_QUOTE)
        self.assertFails(check("denial-demo#p1.1", "   \n "), v.EMPTY_QUOTE)
        self.assertFails(check("denial-demo#p1.1", "..."), v.EMPTY_QUOTE)

    def test_quote_longer_than_clause(self):
        clause = INDEX.get("denial-demo#p1.1")
        self.assertFails(check(clause.clause_id, clause.text + " and more words besides"), v.QUOTE_NOT_IN_CLAUSE)

    def test_malformed_citation(self):
        for bad in (None, "x", 3, [], {"doc": DEN, "clause_id": "denial-demo#p1.1"}, {"doc": DEN, "clause_id": 5, "quote": "a b c d"}):
            r = v.verify_citation(bad, INDEX)
            self.assertFalse(r.ok)
            self.assertEqual(r.reason, v.MALFORMED)

    def test_extra_fields_ignored(self):
        c = cite("denial-demo#p1.1", "the service is not covered")
        c["confidence"] = 0.9
        self.assertOk(v.verify_citation(c, INDEX))


class SpanTest(unittest.TestCase):
    def test_span_maps_to_original_text(self):
        cases = [
            ("sbc-demo#p2.2", "If you don't get prior authorization, benefits"),
            ("sbc-demo#p1.3", "Benefits are not covered for cosmetic"),
            ("denial-demo#p1.2", "appeal within 180 calendar days"),
            ("sbc-demo#p1.1", "deductible? $1500 individual / $3000"),
        ]
        for clause_id, quote in cases:
            r = check(clause_id, quote)
            self.assertTrue(r.ok, r)
            text = INDEX.get(clause_id).text
            (s, e), = r.spans
            self.assertEqual(norm(text[s:e]), norm(quote), (clause_id, text[s:e]))

    def test_one_line_highlight(self):
        r = check("denial-demo#p1.1", "We have denied your claim")
        self.assertEqual([h.bbox for h in r.highlights], [INDEX.get("denial-demo#p1.1").lines[0].bbox])
        self.assertEqual(r.highlights[0].page, 1)

    def test_highlight_crossing_line_break(self):
        r = check("sbc-demo#p2.2", "required for outpatient surgery")
        lines = INDEX.get("sbc-demo#p2.2").lines
        self.assertEqual([h.bbox for h in r.highlights], [lines[0].bbox, lines[1].bbox])

    def test_table_row_highlights_one_cell(self):
        r = check("sbc-demo#p2.1", "$40 Copay / visit; deductible does not apply")
        self.assertEqual([h.bbox for h in r.highlights], [INDEX.get("sbc-demo#p2.1").lines[1].bbox])

    def test_ellipsis_gives_two_spans(self):
        r = check("sbc-demo#p2.2", "Prior authorization is required for ... benefits will be reduced by 50%")
        self.assertEqual(len(r.spans), 2)
        self.assertLess(r.spans[0][1], r.spans[1][0])


class ClaimTest(unittest.TestCase):
    def test_supported(self):
        r = claim("The letter says the service isn't covered.", cite("denial-demo#p1.1", "the service is not covered"))
        self.assertTrue(r.supported)
        self.assertIsNone(r.reason)

    def test_no_citations(self):
        for cits in (None, []):
            r = v.verify_claim({"text": "Your plan covers this.", "citations": cits}, INDEX)
            self.assertFalse(r.supported)
            self.assertEqual(r.reason, v.NO_CITATIONS)

    def test_one_good_one_bad_is_unsupported(self):
        r = claim(
            "The service was denied and you can appeal.",
            cite("denial-demo#p1.1", "the service is not covered"),
            cite("denial-demo#p1.2", "you can appeal at any time"),
        )
        self.assertFalse(r.supported)
        self.assertEqual(r.reason, v.CITATION_FAILED)
        self.assertEqual([c.ok for c in r.citations], [True, False])

    def test_wrong_amount(self):
        r = claim("Primary care visits cost $50 per visit.", cite("sbc-demo#p2.1", "$40 Copay / visit; deductible does not apply"))
        self.assertFalse(r.supported)
        self.assertEqual(r.reason, v.NUMBER_NOT_IN_QUOTE)
        self.assertEqual(r.missing_numbers, ("$50",))

    def test_amount_with_separator(self):
        r = claim("Your deductible is $1,500 for one person.", cite("sbc-demo#p1.1", "overall deductible? $1500 individual"))
        self.assertTrue(r.supported, r)

    def test_days_not_in_quote(self):
        r = claim("You have 180 days to appeal.", cite("denial-demo#p1.1", "We have denied your claim"))
        self.assertFalse(r.supported)
        self.assertEqual(r.missing_numbers, ("180 days",))

    def test_days_in_quote(self):
        r = claim("You have 180 days to appeal.", cite("denial-demo#p1.2", "appeal within 180 calendar days"))
        self.assertTrue(r.supported, r)

    def test_percent(self):
        ok = claim("Imaging is 20% coinsurance.", cite("sbc-demo#p2.4", "Coinsurance for imaging is 20%"))
        bad = claim("Imaging is 30% coinsurance.", cite("sbc-demo#p2.4", "Coinsurance for imaging is 20%"))
        self.assertTrue(ok.supported)
        self.assertEqual(bad.missing_numbers, ("30%",))

    def test_number_may_come_from_any_citation(self):
        r = claim(
            "Imaging is 20% coinsurance and visits are $40.",
            cite("sbc-demo#p2.4", "Coinsurance for imaging is 20%"),
            cite("sbc-demo#p2.1", "$40 Copay / visit; deductible does not apply"),
        )
        self.assertTrue(r.supported, r)

    def test_malformed_claims(self):
        for bad in (None, "text", [], {"citations": []}, {"text": "", "citations": []}, {"text": "x", "citations": "nope"}):
            r = v.verify_claim(bad, INDEX)
            self.assertFalse(r.supported)
            self.assertEqual(r.reason, v.MALFORMED)


class ReportTest(unittest.TestCase):
    RESPONSE = {
        "claims": [
            {"text": "The claim was denied as not covered.", "citations": [cite("denial-demo#p1.1", "the service is not covered")]},
            {"text": "You have 60 days to appeal.", "citations": [cite("denial-demo#p1.2", "appeal within 180 calendar days")]},
        ]
    }

    def test_counts(self):
        r = v.verify(self.RESPONSE, INDEX)
        self.assertIsNone(r.error)
        self.assertEqual((len(r.supported), len(r.unsupported)), (1, 1))
        self.assertEqual(r.rejection_rate, 0.5)

    def test_accepts_json_string_and_bare_list(self):
        a = v.verify(json.dumps(self.RESPONSE), INDEX)
        b = v.verify(self.RESPONSE["claims"], INDEX)
        self.assertEqual(a, b)
        self.assertEqual(a, v.verify(self.RESPONSE, INDEX))

    def test_unreadable_response(self):
        for bad in ("not json", "{\"claims\": 3}", None, 7, b"\xff", {"other": []}):
            r = v.verify(bad, INDEX)
            self.assertEqual(r.error, v.MALFORMED)
            self.assertEqual(r.claims, ())
            self.assertEqual(r.rejection_rate, 0.0)

    def test_input_not_modified(self):
        before = copy.deepcopy(self.RESPONSE)
        v.verify(self.RESPONSE, INDEX)
        self.assertEqual(self.RESPONSE, before)

    def test_deterministic(self):
        self.assertEqual(v.verify(self.RESPONSE, INDEX).to_dict(), v.verify(self.RESPONSE, INDEX).to_dict())

    def test_to_dict_is_json(self):
        d = v.verify(self.RESPONSE, INDEX).to_dict()
        self.assertEqual(json.loads(json.dumps(d)), d)


if __name__ == "__main__":
    unittest.main()
