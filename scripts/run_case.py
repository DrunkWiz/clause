"""Run a bundled demo case through the live pipeline and print a summary.

    python scripts/run_case.py synthetic-denial-ambetter-tx [--record] [--json out.json]

--record saves the live model responses to data/recorded/, so the demo can
replay them when the live providers are unavailable.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from clause.model.providers import default_chain  # noqa: E402
from clause.pipeline.case import run_denial, run_eob  # noqa: E402
from clause.pipeline.demo import CASES, case_indexes  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("case", choices=sorted(CASES))
    ap.add_argument("--record", action="store_true")
    ap.add_argument("--json")
    args = ap.parse_args()

    doc, plan = case_indexes(args.case)
    chain = default_chain(record=args.record)
    result = (run_denial if CASES[args.case].kind == "denial" else run_eob)(doc, plan, chain)
    if args.json:
        Path(args.json).write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")

    print("answered by:", result["answered_by"])
    if result["kind"] == "denial":
        print("facts:", {k: (v["value"], v["confirmed"]) for k, v in result["facts"].items()})
        print("deadlines:", [(d["id"], d["due"]) for d in result["deadlines"]])
        print("notice not found:", result["notice"]["not_found"])
        print("stats:", result["stats"])
        for s in result["letter"]["sections"]:
            print(f"\n## {s['title']}")
            for c in s["claims"]:
                mark = {True: "OK ", False: "XX ", None: "-- "}[c["supported"]]
                why = "" if c["supported"] is not False else f"   <- {c['reason']} {[x['reason'] for x in c['citations'] if not x['ok']]} {c['missing_numbers']}"
                print(f"{mark}[{c['source']}] {c['text']}{why}")
    else:
        print("facts:", result["facts"])
        for l in result["lines"]:
            print(f"  {l['group']}-{l['code']} {l['amount']}: {l['meaning']}  claims ok: {[c['supported'] for c in l['claims']]}")
        print("patient share flags:", [(c["text"], c["supported"]) for c in result["patient_share"]])
        if result["no_surprises"]:
            print("no surprises:", result["no_surprises"]["status"], [(f["text"], f["supported"]) for f in result["no_surprises"]["flags"]])


if __name__ == "__main__":
    main()
