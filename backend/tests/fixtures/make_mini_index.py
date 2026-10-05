"""Regenerates mini_index.json, the hand-built index the verifier tests use.

Run from backend/:  python -m tests.fixtures.make_mini_index
The text is made up for tests; it is not from any real plan.
"""

from pathlib import Path

from clause.index.model import PARAGRAPH, TABLE_ROW, Clause, ClauseIndex, Document, Line, make_clause_id

HERE = Path(__file__).parent


def build_clause(doc_id, page, n, parts, top, kind=PARAGRAPH, sep="\n"):
    """`parts` are the clause's lines (or table cells); boxes are laid out
    one line per 14pt, or side by side for table cells."""
    text, lines = "", []
    for i, part in enumerate(parts):
        if i:
            text += sep
        start = len(text)
        text += part
        if kind == TABLE_ROW:
            bbox = (36.0 + 200 * i, top, 230.0 + 200 * i, top + 24)
        else:
            bbox = (72.0, top + 14 * i, 540.0, top + 14 * i + 12)
        lines.append(Line(bbox, start, len(text)))
    x0 = min(l.bbox[0] for l in lines)
    return Clause(
        clause_id=make_clause_id(doc_id, page, n),
        doc_id=doc_id,
        page=page,
        bbox=(x0, min(l.bbox[1] for l in lines), max(l.bbox[2] for l in lines), max(l.bbox[3] for l in lines)),
        text=text,
        lines=tuple(lines),
        kind=kind,
    )


def build() -> ClauseIndex:
    idx = ClauseIndex()
    sbc = "sbc-demo"
    idx.add_document(
        Document(sbc, "sbc-demo.pdf", "0" * 64, ((792.0, 612.0), (792.0, 612.0))),
        [
            build_clause(sbc, 1, 1, ["What is the overall deductible? $1,500 individual / $3,000 family"], 72),
            build_clause(sbc, 1, 2, ["Specialist visit — $80.50 copay after the deductible"], 100),
            build_clause(sbc, 1, 3, ["Beneﬁts are not covered for cosmetic surgery or ser-", "vices related to it."], 130),
            build_clause(
                sbc,
                2,
                1,
                ["Primary care visit to treat an injury or illness", "$40 Copay / visit; deductible does not apply", "Not covered"],
                98,
                kind=TABLE_ROW,
                sep=" | ",
            ),
            build_clause(
                sbc,
                2,
                2,
                [
                    "Prior authorization is required for out-",
                    "patient surgery. If you don’t get prior au-",
                    "thorization, benefits will be reduced by 50%.",
                ],
                160,
            ),
            build_clause(sbc, 2, 3, ["Not covered"], 220),
            build_clause(sbc, 2, 4, ["Coinsurance for imaging is 20% after you meet the deductible."], 240),
        ],
    )
    den = "denial-demo"
    idx.add_document(
        Document(den, "denial-demo.pdf", "1" * 64, ((612.0, 792.0),)),
        [
            build_clause(den, 1, 1, ["We have denied your claim because the service is not covered", "under your plan."], 100),
            build_clause(den, 1, 2, ["You may ap­peal within  180 calendar days of the date", "of this notice."], 140),
        ],
    )
    return idx


if __name__ == "__main__":
    (HERE / "mini_index.json").write_text(build().to_json(indent=1), encoding="utf-8")
    print("wrote", HERE / "mini_index.json")
