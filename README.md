# Clause

A health insurance assistant that reads your own plan and only tells you what it can point to. Built for ML Build Challenge 3. The project brief is in [docs/BRIEF.md](docs/BRIEF.md).

**Work in progress.** So far: the clause index and the grounding verifier.

## Run the tests

The tests need no network and no API key.

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r backend/requirements.txt   # macOS/Linux: .venv/bin/python
cd backend && ../.venv/Scripts/python -m unittest discover -s tests -t .
```

Without pdfplumber installed, the tests against real PDFs are skipped and the rest still run.

## Rebuild the plan indexes

```bash
.venv/Scripts/python scripts/build_index.py data/plans/*.pdf --out data/indexes
```

To print every clause on one page, add `--dump <page>`.

## What the verifier proves, and what it doesn't

Every claim the model makes comes with citations `{doc, clause_id, quote}`. Plain code checks each one:

- the clause exists
- it belongs to the cited document
- the quote appears in it, after normalisation
- every money amount, percentage, day count and hour count in the claim appears in a cited quote

A claim that fails any check is never shown as fact.

It does **not** prove that a claim follows from its quote. "Experimental treatments are covered", citing the exclusion that begins "For experimental or investigational treatment(s)…", passes. The labelled set in `backend/tests/fixtures/grounding_set.json` records this case.

## Real and synthetic

| Piece | Status |
| --- | --- |
| Plan documents (`data/plans`) | **Real**, public 2026 documents from three insurers. See [data/plans/SOURCES.md](data/plans/SOURCES.md). |
| Denial letters and EOBs | **Synthetic**, not built yet. |
