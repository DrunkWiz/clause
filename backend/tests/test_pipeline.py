"""Model chain and the case pipeline, offline: fake providers and the
recorded responses in data/recorded. No network, no key."""

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from clause.model.providers import Chain, FakeProvider, Provider, ProviderError, RecordedProvider, parse_json
from clause.pipeline import prompts
from clause.pipeline.case import canonical_citations, parse_date, run_denial, run_eob
from clause.pipeline.demo import CASES, case_indexes
from clause.pipeline.retrieve import select
from clause.synthetic import truth as tr


class Failing(FakeProvider):
    name = "failing"

    def __init__(self):
        super().__init__(lambda task, user: (_ for _ in ()).throw(ProviderError("down")))


class ChainTest(unittest.TestCase):
    def test_parse_json(self):
        self.assertEqual(parse_json('```json\n{"a": 1}\n```'), {"a": 1})
        self.assertEqual(parse_json('Sure! {"a": [1, 2]} hope that helps'), {"a": [1, 2]})
        with self.assertRaises(ValueError):
            parse_json("no json here")

    def test_falls_through_to_next_provider(self):
        ok = FakeProvider(lambda t, u: {"ok": True})
        r = Chain([Failing(), ok]).run("t", "s", "u")
        self.assertEqual((r.data, r.provider), ({"ok": True}, "fake"))
        self.assertEqual([a.ok for a in r.attempts], [False, True])

    def test_bad_shape_moves_on(self):
        bad = FakeProvider(lambda t, u: {"nope": 1})
        good = FakeProvider(lambda t, u: {"sections": []})
        r = Chain([bad, good]).run("t", "s", "u", prompts.validate_draft)
        self.assertEqual(r.data, {"sections": []})
        self.assertFalse(r.attempts[0].ok)

    def test_all_fail(self):
        with self.assertRaises(ProviderError):
            Chain([Failing(), Failing()]).run("t", "s", "u")

    def test_recording_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            rec = RecordedProvider(Path(d))

            class Live(Provider):  # stands in for a real provider; fakes are never recorded
                name = "live"

                def complete(self, task, system, user):
                    return '{"x": 1}'

            Chain([Live()], record_to=rec).run("task", "sys", "user")
            self.assertEqual(Chain([rec]).run("task", "sys", "user").data, {"x": 1})
            with self.assertRaises(ProviderError):
                Chain([rec]).run("task", "sys", "different user")


class HelpersTest(unittest.TestCase):
    def test_parse_date(self):
        self.assertEqual(parse_date("September 21, 2026"), date(2026, 9, 21))
        self.assertEqual(parse_date("Dated 10/02/2026."), date(2026, 10, 2))
        self.assertIsNone(parse_date("February 30, 2026"))
        self.assertIsNone(parse_date("no date"))

    def test_canonical_citations(self):
        data = {"sections": [{"claims": [{"citations": [{"doc": "d", "clause_id": "p2.3", "quote": "q"}, {"doc": "d", "clause_id": "d#p1.1", "quote": "q"}, {"doc": "d", "clause_id": "x2.3", "quote": "q"}]}]}]}
        canonical_citations(data)
        ids = [c["clause_id"] for c in data["sections"][0]["claims"][0]["citations"]]
        self.assertEqual(ids, ["d#p2.3", "d#p1.1", "x2.3"])

    def test_retrieval_finds_the_definition(self):
        _, plan = case_indexes("synthetic-denial-ambetter-tx")
        picked = select(list(plan.clauses.values()), ["medically necessary means definition accepted standards of medicine"], 10, 10)
        self.assertIn("ambetter-tx-eoc-2026#p26.6", [c.clause_id for c in picked])


RECORDED = Chain([RecordedProvider()])


class RecordedCasesTest(unittest.TestCase):
    """The whole pipeline on the bundled cases, replaying recorded model output."""

    def test_denials(self):
        for cid, d in CASES.items():
            if d.kind != "denial":
                continue
            with self.subTest(cid):
                t = tr.load_truth(cid)
                r = run_denial(*case_indexes(cid), RECORDED)
                self.assertEqual(r["answered_by"], {"extract": "recorded", "draft": "recorded"})
                self.assertEqual(r["facts"]["notice_date"]["value"], t["notice_date"])
                self.assertEqual(r["facts"]["care"]["value"], t["care"])
                self.assertEqual(r["facts"]["basis"]["value"], t["basis"])
                self.assertEqual(sorted(r["notice"]["not_found"]), sorted(t["gaps"]))
                self.assertTrue(all(c["supported"] for dd in r["deadlines"] for c in dd["claims"]))
                ids = [s["id"] for s in r["letter"]["sections"]]
                self.assertEqual(ids[-1], "request")
                self.assertEqual("procedure" in ids, bool(t["gaps"]))
                self.assertGreater(r["stats"]["model_claims"], 3)
                json.dumps(r)  # the API returns it as JSON
                for c in (c for s in r["letter"]["sections"] for c in s["claims"] if c["supported"]):
                    for cit in c["citations"]:
                        self.assertIn(cit["clause_id"], r["clauses"])
                        self.assertTrue(cit["highlights"])

    def test_er_eob(self):
        r = run_eob(*case_indexes("synthetic-eob-ambetter-er"), RECORDED)
        self.assertEqual(r["no_surprises"]["status"], "protected")
        self.assertEqual(len(r["no_surprises"]["flags"]), 2)
        self.assertTrue(all(f["supported"] for f in r["no_surprises"]["flags"]))
        self.assertEqual(r["patient_share"], [])

    def test_surgery_eob(self):
        r = run_eob(*case_indexes("synthetic-eob-fidelis-surgery"), RECORDED)
        self.assertEqual(r["no_surprises"]["status"], "protected")
        self.assertEqual([f["rule_id"] for f in r["no_surprises"]["flags"]], ["nsa.flag.balance_bill"])
        (flag,) = r["patient_share"]
        self.assertTrue(flag["supported"])
        self.assertIn("$950.00", flag["text"])


class FakeModelTest(unittest.TestCase):
    """A fake model that fabricates: the verifier must catch it."""

    def test_fabricated_quote_and_wrong_amount_are_rejected(self):
        cid = "synthetic-denial-ambetter-tx"
        t = tr.load_truth(cid)
        letter_cit = tr.citation(t, "claim_amount")

        def model(task, user):
            if task == "denial_extract":
                return {
                    "facts": [{"field": "notice_date", "citations": [tr.citation(t, "notice_date")]}],
                    "elements": [{"element": e["element"], "citations": e["citations"]} for e in tr.notice_findings(t)],
                }
            return {
                "sections": [
                    {"id": "denial", "claims": [
                        {"text": "The claim was for $1,840.00.", "citations": [letter_cit]},
                        {"text": "The claim was for $2,000.00.", "citations": [letter_cit]},
                    ]},
                    {"id": "plan", "claims": [
                        {"text": "The plan covers every MRI.", "citations": [{"doc": "ambetter-tx-eoc-2026", "clause_id": "ambetter-tx-eoc-2026#p26.6", "quote": "all MRI scans are always covered by this plan"}]},
                        {"text": "No citation at all.", "citations": []},
                    ]},
                ]
            }

        r = run_denial(*case_indexes(cid), Chain([FakeProvider(model)]))
        claims = {c["text"]: c for s in r["letter"]["sections"] for c in s["claims"]}
        self.assertTrue(claims["The claim was for $1,840.00."]["supported"])
        self.assertEqual(claims["The claim was for $2,000.00."]["reason"], "number_not_in_quote")
        self.assertEqual(claims["The plan covers every MRI."]["reason"], "citation_failed")
        self.assertEqual(claims["No citation at all."]["reason"], "no_citations")
        self.assertEqual(r["stats"], {"model_claims": 4, "supported": 1, "rejected": 3, "rejection_rate": 0.75})
        # Defaults when the model gives no care/basis: post-service, unconfirmed.
        self.assertEqual((r["facts"]["care"]["value"], r["facts"]["care"]["confirmed"]), ("post_service", False))

    def test_overrides_win(self):
        cid = "synthetic-denial-ambetter-tx"

        def model(task, user):
            return {"facts": [], "elements": []} if task == "denial_extract" else {"sections": []}

        r = run_denial(*case_indexes(cid), Chain([FakeProvider(model)]), overrides={"notice_date": "2026-10-01", "care": "urgent"})
        self.assertEqual(r["facts"]["notice_date"], {"value": "2026-10-01", "confirmed": False, "entered": True, "citations": []})
        self.assertEqual(r["facts"]["care"]["value"], "urgent")
        self.assertEqual(r["deadlines"][0]["due"], "2027-03-30")


if __name__ == "__main__":
    unittest.main()
