"""HTTP API and static file server. Stdlib only.

    python -m clause.server            (from backend/; PORT defaults to 8000)

Privacy: uploaded documents are read in memory and never written to disk or
logged. The browser keeps the case (localStorage); the server keeps nothing
about a person between requests. Model keys stay here, never sent to clients.

Routes
  GET  /api/health
  GET  /api/demo                       bundled synthetic cases
  POST /api/demo/<case_id>             run a bundled case   {overrides?, live?}
  POST /api/index                      PDF bytes -> clause index (X-Filename header)
  POST /api/case                       {kind, document: <index>, plan_docs: [ids], overrides?}
  POST /api/verify                     {claim, documents?: [<index>], docs?: [ids]}
  GET  /files/{plans,synthetic,regs}/<file>.pdf
  GET  /*                              the built frontend (frontend/dist)
"""

from __future__ import annotations

import json
import os
import re
import threading
import traceback
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from clause.index.model import ClauseIndex
from clause.model.providers import Chain, ProviderError, RecordedProvider, default_chain, load_env
from clause.pipeline import demo
from clause.pipeline.case import check, run_denial, run_eob
from clause.rules.base import regs

ROOT = Path(__file__).resolve().parents[2]
DIST = ROOT / "frontend" / "dist"
FILES = {"plans": ROOT / "data" / "plans", "synthetic": ROOT / "data" / "synthetic", "regs": ROOT / "data" / "regs" / "raw"}
MAX_UPLOAD = 15 * 1024 * 1024
MAX_JSON = 30 * 1024 * 1024
TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css",
         ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon", ".json": "application/json",
         ".pdf": "application/pdf", ".woff2": "font/woff2", ".map": "application/json"}

_demo_cache: dict[str, dict] = {}  # results for the bundled synthetic cases only
_demo_lock = threading.Lock()


def bundled_index(doc_ids: list[str]) -> ClauseIndex:
    idx = ClauseIndex()
    for d in doc_ids:
        if not re.fullmatch(r"[a-z0-9-]+", d or "") or not (demo.INDEXES / f"{d}.json").exists():
            raise ValueError(f"unknown document: {d}")
        idx = idx.merge(demo.load_index(d))
    return idx


def demo_chain(live: bool) -> Chain:
    """For the bundled synthetic cases, saved Gemini responses answer first
    (instant), and the live providers only if there is no recording. With
    live=True the live providers go first, as for uploads. Results always say
    which one answered."""
    chain = default_chain()
    if live:
        return chain
    recorded = [p for p in chain.providers if isinstance(p, RecordedProvider)]
    others = [p for p in chain.providers if not isinstance(p, RecordedProvider)]
    return Chain(recorded + others)


def run_case(kind: str, document: ClauseIndex, plan: ClauseIndex, overrides: dict, chain: Chain | None = None) -> dict:
    chain = chain or default_chain()
    if kind == "eob":
        return run_eob(document, plan, chain)
    return run_denial(document, plan, chain, overrides=overrides)


class Handler(BaseHTTPRequestHandler):
    server_version = "clause"

    # Never log request bodies; the default access log has paths only.
    def log_message(self, fmt, *args):
        if os.environ.get("CLAUSE_QUIET") != "1":
            super().log_message(fmt, *args)

    # ------------------------------------------------------------ helpers

    def send_json(self, data, status=HTTPStatus.OK):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def error(self, status, message):
        self.send_json({"error": message}, status)

    def body(self, limit: int) -> bytes:
        n = int(self.headers.get("Content-Length") or 0)
        if n > limit:
            raise ValueError("request too large")
        return self.rfile.read(n)

    def json_body(self) -> dict:
        raw = self.body(MAX_JSON)
        data = json.loads(raw or b"{}")
        if not isinstance(data, dict):
            raise ValueError("expected a JSON object")
        return data

    def send_file(self, path: Path, cache: str = "public, max-age=3600"):
        data = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", TYPES.get(path.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", cache)
        self.end_headers()
        self.wfile.write(data)

    # -------------------------------------------------------------- routes

    def do_HEAD(self):
        """Health checks from hosting platforms: headers only."""
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0]
        try:
            if path == "/api/health":
                return self.send_json({"ok": True, "providers": [p.name for p in default_chain().providers]})
            if path == "/api/demo":
                return self.send_json({"cases": demo.list_cases()})
            m = re.fullmatch(r"/files/(plans|synthetic|regs)/([A-Za-z0-9._-]+\.pdf)", path)
            if m:
                f = FILES[m.group(1)] / m.group(2)
                return self.send_file(f) if f.is_file() else self.error(HTTPStatus.NOT_FOUND, "no such file")
            m = re.fullmatch(r"/api/regulations/([a-z0-9-]+)", path)
            if m:
                r = regs()
                clauses = [c.to_dict() for c in r.clauses.values() if c.doc_id == m.group(1)]
                if not clauses:
                    return self.error(HTTPStatus.NOT_FOUND, "no such regulation")
                return self.send_json({"document": r.documents[m.group(1)].to_dict(), "clauses": clauses})
            if path.startswith(("/api/", "/files/")):
                return self.error(HTTPStatus.NOT_FOUND, "no such route")
            return self.static(path)
        except Exception:
            traceback.print_exc()
            return self.error(HTTPStatus.INTERNAL_SERVER_ERROR, "server error")

    def static(self, path: str):
        if not DIST.exists():
            return self.error(HTTPStatus.NOT_FOUND, "frontend not built (cd frontend && npm run build)")
        rel = path.lstrip("/") or "index.html"
        f = (DIST / rel).resolve()
        if DIST.resolve() in f.parents and f.is_file():
            return self.send_file(f, "public, max-age=31536000, immutable" if "/assets/" in path else "no-cache")
        return self.send_file(DIST / "index.html", "no-cache")  # single-page app

    def do_POST(self):
        path = self.path.split("?")[0]
        try:
            m = re.fullmatch(r"/api/demo/([a-z0-9-]+)", path)
            if m:
                return self.demo_case(m.group(1))
            if path == "/api/index":
                return self.index_upload()
            if path == "/api/case":
                return self.case()
            if path == "/api/verify":
                return self.verify()
            return self.error(HTTPStatus.NOT_FOUND, "no such route")
        except ProviderError as e:
            return self.error(HTTPStatus.BAD_GATEWAY, f"The model could not be reached: {e}"[:400])
        except (ValueError, KeyError, json.JSONDecodeError) as e:
            return self.error(HTTPStatus.BAD_REQUEST, str(e)[:300])
        except Exception:
            traceback.print_exc()
            return self.error(HTTPStatus.INTERNAL_SERVER_ERROR, "server error")

    def demo_case(self, case_id: str):
        if case_id not in demo.CASES:
            return self.error(HTTPStatus.NOT_FOUND, "no such demo case")
        body = self.json_body()
        overrides = body.get("overrides") or {}
        live = bool(body.get("live"))
        key = json.dumps([case_id, overrides, live], sort_keys=True)
        with _demo_lock:
            cached = None if live else _demo_cache.get(key)  # a live run always calls the model
        if cached is None:
            doc, plan = demo.case_indexes(case_id)
            cached = run_case(demo.CASES[case_id].kind, doc, plan, overrides, demo_chain(live))
            with _demo_lock:
                _demo_cache[key] = cached
        return self.send_json(cached)

    def index_upload(self):
        from clause.index.extract import extract_pdf  # pdfplumber

        data = self.body(MAX_UPLOAD)
        if not data.startswith(b"%PDF"):
            raise ValueError("please upload a PDF")
        name = Path(self.headers.get("X-Filename") or "upload.pdf").name
        doc, clauses = extract_pdf(data, name, "upload-" + re.sub(r"[^a-z0-9]+", "-", Path(name).stem.lower()).strip("-")[:40])
        idx = ClauseIndex()
        idx.add_document(doc, clauses)
        return self.send_json(idx.to_dict())

    def case(self):
        body = self.json_body()
        document = ClauseIndex.from_dict(body["document"])
        plan = bundled_index(body.get("plan_docs") or [])
        for extra in body.get("plan_documents") or []:  # uploaded plan documents
            plan = plan.merge(ClauseIndex.from_dict(extra))
        if not plan.clauses:
            raise ValueError("choose or upload the plan documents")
        return self.send_json(run_case(body.get("kind", "denial"), document, plan, body.get("overrides") or {}))

    def verify(self):
        """Re-check one claim, e.g. after the person edits a drafted sentence."""
        body = self.json_body()
        idx = bundled_index(body.get("docs") or []).merge(regs())
        for extra in body.get("documents") or []:
            idx = idx.merge(ClauseIndex.from_dict(extra))
        claim = body.get("claim")
        if not isinstance(claim, dict):
            raise ValueError("claim must be an object")
        return self.send_json(check(claim, idx, claim.get("source") or "edited"))


def main():
    load_env()
    port = int(os.environ.get("PORT", "8000"))
    host = os.environ.get("HOST", "127.0.0.1")
    print(f"Clause on http://{host}:{port}")
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    main()
