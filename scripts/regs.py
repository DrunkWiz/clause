"""Fetch regulation text and build the regulations index.

    python scripts/regs.py fetch   # downloads into data/regs/raw (network)
    python scripts/regs.py build   # data/regs/raw -> data/regs/regs_index.json (offline)
"""

from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from clause.index.regs import SOURCES, build_regs_index  # noqa: E402

RAW = ROOT / "data" / "regs" / "raw"
OUT = ROOT / "data" / "regs" / "regs_index.json"


def fetch() -> None:
    import gzip

    RAW.mkdir(parents=True, exist_ok=True)
    for s in SOURCES:
        # eCFR refuses requests that do not accept compression.
        req = urllib.request.Request(s.url, headers={"Accept-Encoding": "gzip", "User-Agent": "clause-build/1"})
        with urllib.request.urlopen(req, timeout=90) as r:
            data = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                data = gzip.decompress(data)
        (RAW / s.raw_file).write_bytes(data)
        print(f"fetched {s.raw_file} ({len(data)} bytes)")


def build() -> None:
    idx = build_regs_index(RAW)
    OUT.write_text(idx.to_json(indent=1), encoding="utf-8", newline="\n")
    for doc in idx.documents.values():
        n = sum(1 for c in idx.clauses.values() if c.doc_id == doc.doc_id)
        print(f"{doc.title}: {n} clauses")


if __name__ == "__main__":
    {"fetch": fetch, "build": build}[sys.argv[1]]()
