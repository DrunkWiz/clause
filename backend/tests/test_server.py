"""The HTTP API, served on a local port, with the model chain replaced by
recorded responses so nothing touches the network."""

import json
import os
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from clause import server
from clause.model.providers import Chain, RecordedProvider
from clause.synthetic import truth as tr

ROOT = Path(__file__).resolve().parents[2]

try:
    import pdfplumber  # noqa: F401
except ImportError:
    pdfplumber = None


def recorded_chain(record=False):
    return Chain([RecordedProvider()])


class ServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["CLAUSE_QUIET"] = "1"
        cls.patch = mock.patch.object(server, "default_chain", recorded_chain)
        cls.patch.start()
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.base = f"http://127.0.0.1:{cls.httpd.server_address[1]}"
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.patch.stop()

    def request(self, path, data=None, headers=None, method=None):
        if isinstance(data, (dict, list)):
            data = json.dumps(data).encode()
            headers = {"Content-Type": "application/json", **(headers or {})}
        req = urllib.request.Request(self.base + path, data=data, headers=headers or {}, method=method)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, r.headers, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.headers, e.read()

    def json(self, path, data=None, **kw):
        status, _, body = self.request(path, data, **kw)
        return status, json.loads(body)

    def test_health_and_demo_list(self):
        self.assertEqual(self.json("/api/health"), (200, {"ok": True, "providers": ["recorded"]}))
        status, data = self.json("/api/demo")
        self.assertEqual(status, 200)
        self.assertEqual(len(data["cases"]), 5)

    def test_demo_denial(self):
        status, r = self.json("/api/demo/synthetic-denial-ambetter-tx", {})
        self.assertEqual(status, 200)
        self.assertEqual(r["notice"]["not_found"], ["plan_provision"])
        self.assertEqual(r["deadlines"][0]["due"], "2027-03-20")
        self.assertTrue(r["enclosures"])

    def test_demo_eob(self):
        status, r = self.json("/api/demo/synthetic-eob-ambetter-er", {})
        self.assertEqual((status, r["no_surprises"]["status"]), (200, "protected"))

    def test_unknown_demo(self):
        self.assertEqual(self.json("/api/demo/nope", {})[0], 404)

    def test_files(self):
        status, headers, body = self.request("/files/synthetic/synthetic-denial-ambetter-tx.pdf")
        self.assertEqual((status, headers["Content-Type"]), (200, "application/pdf"))
        self.assertTrue(body.startswith(b"%PDF"))
        self.assertEqual(self.request("/files/plans/..%2F..%2FCLAUDE.md")[0], 404)
        self.assertEqual(self.request("/files/../CLAUDE.md")[0] in (400, 404), True)
        status, _, body = self.request("/assets/..%2F..%2F..%2FCLAUDE.md")
        self.assertNotIn(b"Non-negotiables", body)  # never a file outside the built frontend

    def test_head(self):
        self.assertEqual(self.request("/", method="HEAD")[0], 200)

    def test_demo_prefers_recording_unless_live(self):
        chain = server.demo_chain(live=False)
        self.assertEqual(chain.providers[0].name, "recorded")

    def test_regulation_text(self):
        status, r = self.json("/api/regulations/45-cfr-147-136")
        self.assertEqual(status, 200)
        self.assertTrue(any(c.get("label") == "45 CFR 147.136(d)(2)(i)" for c in r["clauses"]))

    @unittest.skipIf(pdfplumber is None, "pdfplumber not installed")
    def test_upload_then_case(self):
        pdf = (ROOT / "data" / "synthetic" / "synthetic-denial-fidelis-ny.pdf").read_bytes()
        status, _, body = self.request("/api/index", pdf, headers={"X-Filename": "my letter.pdf", "Content-Type": "application/pdf"})
        self.assertEqual(status, 200)
        idx = json.loads(body)
        self.assertEqual(idx["documents"][0]["doc_id"], "upload-my-letter")
        # An uploaded letter gets a different doc id from the bundled one, so
        # there is no recording for it: the recorded-only chain must fail cleanly.
        status, r = self.json("/api/case", {"kind": "denial", "document": idx, "plan_docs": ["fidelis-ny-silver-contract-2026"]})
        self.assertEqual(status, 502)
        self.assertIn("model could not be reached", r["error"])

    def test_upload_rejects_non_pdf(self):
        status, _, body = self.request("/api/index", b"hello", headers={"Content-Type": "application/pdf"})
        self.assertEqual(status, 400)

    def test_case_needs_plan(self):
        idx = json.loads((ROOT / "data" / "indexes" / "synthetic-denial-kaiser-ga.json").read_text(encoding="utf-8"))
        self.assertEqual(self.json("/api/case", {"document": idx, "plan_docs": []})[0], 400)
        self.assertEqual(self.json("/api/case", {"document": idx, "plan_docs": ["../secrets"]})[0], 400)

    def test_verify_edited_claim(self):
        t = tr.load_truth("synthetic-denial-ambetter-tx")
        cit = tr.citation(t, "claim_amount")
        docs = ["synthetic-denial-ambetter-tx", "ambetter-tx-eoc-2026"]
        status, ok = self.json("/api/verify", {"docs": docs, "claim": {"text": "The claim was $1,840.00.", "citations": [cit]}})
        self.assertEqual((status, ok["supported"]), (200, True))
        status, bad = self.json("/api/verify", {"docs": docs, "claim": {"text": "The claim was $2,000.00.", "citations": [cit]}})
        self.assertEqual((bad["supported"], bad["reason"], bad["missing_numbers"]), (False, "number_not_in_quote", ["$2,000"]))
        self.assertEqual(bad["source"], "edited")

    def test_bad_requests(self):
        self.assertEqual(self.request("/api/verify", b"{not json", headers={"Content-Type": "application/json"})[0], 400)
        self.assertEqual(self.json("/api/verify", {"claim": "x"})[0], 400)
        self.assertEqual(self.json("/api/nope", {})[0], 404)
        self.assertEqual(self.json("/api/nope")[0], 404)


if __name__ == "__main__":
    unittest.main()
