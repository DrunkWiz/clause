# Clause

Health insurance assistant for ML Build Challenge 3. Deadline Sat 10 Oct 2026, 2:45pm SGT.
Full brief: @docs/BRIEF.md

## Non-negotiables

- The model never writes free prose that reaches the user. Every model output is a list of claims, each with citations `{doc, clause_id, quote}`. The grounding verifier checks every citation; a claim that fails is dropped or shown as unsupported, never as fact.
- Deadlines, reason codes, notice completeness and No Surprises checks are deterministic code. Each rule lives in a table with its regulation citation beside it. The model only extracts inputs.
- The test suite runs with no network and no API key. Use a fake model gateway and offline fixtures.
- User documents are never stored server-side.
- Denial letters and EOBs in the repo are synthetic and labelled as such. Plan documents are real public ones.
- Keys live only in `.env` (gitignored) and the deploy environment, never in the frontend bundle.

## Build order

1. Clause index + grounding verifier, with tests (Mon–Tue)
2. The four rules, with citations and tests (Wed)
3. Appeal drafter + side-by-side highlight UI (Thu)

Cut order if behind: the "before care" coverage check first, then the EOB check. The appeal flow must survive.

## How to work

- Propose a plan before starting a new module and wait for approval.
- Run the tests after every change and report the counts.
- When a fact about insurance rules is uncertain, say so and leave a TODO with what needs verifying. Do not guess a deadline.
