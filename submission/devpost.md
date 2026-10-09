# Devpost submission: Clause

Paste each section into the matching Devpost field. Devpost's editor accepts Markdown.

## Project name (pick one)

1. **Clause** (recommended: it matches the app, repo and video)
2. Clause: Fight Your Denial, Line by Line
3. Clause: The Appeal That Cites Its Sources

## Elevator pitch (200 characters max)

> Clause reads your health plan and denial letter, works out your appeal deadline, finds what the insurer left out, and drafts an appeal in which every sentence is checked against its source.

## Built with (tags)

python, pdfplumber, gemini, featherless, react, vite, pdf.js, render

## Links

- Live demo: https://clause-p7uk.onrender.com
- Video: *(your YouTube link)*
- Code: https://github.com/DrunkWiz/clause *(make the repo public first)*

---

## About the project

> **Note:** The live demo runs on a free Render instance. The initial load may take 30–60 seconds to wake the server, but subsequent requests and bundled demo cases are fast.

> Clause gives information about your own plan documents, not legal or medical advice. It applies federal minimums only; your state may give you more.

### The problem

In 2023, insurers on HealthCare.gov denied 19% of in-network claims, and consumers appealed fewer than 1% of those denials (KFF).

People aren't losing appeals so much as never filing them. The person holding a denial letter usually doesn't know:

- the deadline to appeal
- what the insurer was legally required to tell them
- which clause in a 150-page Evidence of Coverage supports their case

A general chatbot is the wrong tool here. A confident, made-up clause or deadline in a medical appeal is worse than no help at all.

### What it does

Pick a sample denial letter (or upload your own PDF) and your plan. Clause then:

- **Reads the letter.** It finds the notice date, the type of claim and the reason for denial, and links each one to the line it came from.
- **Computes your deadlines in code.** That's 180 days to file an internal appeal, the insurer's decision window (72 hours urgent, 30 days pre-service, 60 days post-service), then four months to request external review. Each deadline links to the paragraph of federal regulation it comes from.
- **Checks that the notice is complete.** It tests the letter against the 15 elements federal rules require. An element counts as present only if Clause can quote it from the letter. A missing element, such as the plan provision the denial relies on, becomes an appeal point.
- **Drafts the appeal.** Every sentence cites your letter, your plan or a federal rule. Click a sentence and the source page opens with the exact passage highlighted. Edit a sentence and it is checked again. Clause also lists the evidence to attach.
- **Checks an Explanation of Benefits (EOB).** It explains claim adjustment reason codes in plain language and flags No Surprises Act problems. Examples are emergency care charged at out-of-network cost-sharing, or balance billing by an out-of-network provider at an in-network facility.

Clause drafts the letter; you decide what to send. It never contacts an insurer or provider.

### How it stays honest

This is the design decision that carries the project: **the model may only say what it can point to, and code checks the pointing.**

1. **Every paragraph gets an address.** Plan documents, the letter or EOB, and the federal regulations are split into clauses. Each clause has an id, a page, line-level bounding boxes and its exact text.
2. **The model never writes free prose.** Gemini returns claims in the form `{text, citations: [{doc, clause_id, quote}]}`.
3. **A grounding verifier checks every citation**, using deterministic code:
   - The clause must exist and belong to the cited document.
   - The quote must appear in the clause word for word, after normalisation.
   - The quote must be at least four words long.
   - Every amount, percentage, day count and hour count in the sentence must appear in a cited quote.

   A sentence that fails is greyed out with the reason and left out of the copied letter. It is never shown as fact.
4. **Rules are code, not model.** Appeal deadlines, notice completeness, reason codes and No Surprises Act checks are deterministic rule tables. They cite regulation text that is indexed like any other document, so the rules' own sources pass the same verifier. The model only extracts the inputs, and code reads dates and amounts from verified quotes rather than trusting the model's value.

**What it does not prove:** a real quote doesn't mean the claim follows from it. "Experimental treatments are covered", citing the exclusion that begins "For experimental or investigational treatment(s)…", would pass the verifier. We record this case in our labelled test set and say so in the README.

### How we built it

- **Backend:** a Python 3.11 standard-library HTTP server. pdfplumber is the only runtime dependency; we chose it over PyMuPDF because of PyMuPDF's AGPL licence.
- **PDF parsing of real plan documents:**
  - two-column layout detection
  - filtering out hidden text (one plan's summary carries 1-point text)
  - one clause per table row, with nested duplicate tables dropped
  - line-level boxes, so the interface highlights only the quoted lines
- **Retrieval:** BM25 over plan clauses, written with the standard library.
- **Model chain:** Gemini 3.5 Flash through the REST API, with JSON output at temperature 0.
  - **Featherless** is the second rung, through its OpenAI-compatible API. It is used whenever a Featherless key is set; the public demo currently runs without one.
  - Saved Gemini responses are the last rung, so the demo keeps working if the quota runs out.
  - The interface always says which model answered.
- **Regulations** come from eCFR (45 CFR 147.136, 45 CFR 149, 29 CFR 2560.503-1), GovInfo (5 U.S.C. 6103, for federal holidays) and CMS guidance, and are indexed like any other document.
- **Frontend:** React 19 and Vite. pdf.js renders the source pages, and highlights are positioned from the clause boxes.
- **Synthetic letters and EOBs** come from a plain-Python PDF writer and go through the same extractor as the real plans. Each one has a ground-truth file recording its deliberate gaps.
- **Tests:** 220 tests that run with no network and no API key, using fake model providers.
- **Deployment:** Render's free tier.

### Who it's for

- **The person holding a denial letter** who doesn't know they can fight it. That person is the primary user, and Clause is free for them.
- **Patient advocates and hospital financial counselling teams**, who turn hours of document reading into minutes per case. Unpaid denied bills become a hospital's bad debt.
- **Employers**, as a benefit for employees stuck in billing disputes.

### Challenges we ran into

- **Real plan PDFs are messy:**
  - two-column Evidence of Coverage documents
  - hidden text in a plan summary
  - tables nested inside tables
  - tables of contents that run into one paragraph

  We tested extraction on the real documents before writing anything else.
- **The model split clause ids** into a document plus `p26.6`, and at first 0 of 9 claims verified. We fixed the prompt and added one narrow join for exactly that shape. The verifier itself stayed strict.
- **Deadlines had to be exactly right.** A wrong deadline harms exactly the person this is for, so we checked every rule against the regulation text:
  - We count from the letter date, which is never later than the date of receipt, so our deadlines are never later than the real ones.
  - Only the external-review rule rolls over weekends and holidays.
  - Federal holidays come from 5 U.S.C. 6103(a).
- **Showing the verifier honestly.** On real Gemini output, 0 of 27 drafted sentences were rejected across three letters. So the demo doesn't rely on the model failing. Instead, you can edit a sentence and watch the verifier reject it.

### Accomplishments we're proud of

- **"Grounded" is a test that can fail, not a promise.** We built a labelled set of 20 good, 18 bad and 2 limitation claims against the real Ambetter Texas documents. Every bad claim is rejected for the expected reason, and 0 of 20 good claims are falsely rejected.
- **The rules cite their own sources,** and those sources pass the same verifier as everything else.
- **Your documents are never stored.** Uploads are processed in memory, and your case lives only in your browser.

### What we learned

- Code should handle correctness and the model should handle reading. Every time we moved a decision out of the model and into a tested rule, the product got more trustworthy and easier to test.
- Hiding failure doesn't build trust; showing it does. A greyed-out sentence with its reason is more convincing than a perfect-looking letter.

### What's next

- **"Before care" coverage questions** ("will this be covered?"), answered from the plan with the same verifier. We cut this first to protect the appeal flow.
- **State-specific rules**, which can be stricter than the federal minimums.
- **Employer (ERISA) plans**, which follow different rules.
- **OCR for scanned letters.**
- **A Featherless key** in production.

### What is real and what is synthetic

| Piece | Status |
| --- | --- |
| Plan documents | **Real.** Public 2026 documents from Ambetter (Texas), Kaiser Permanente (Georgia) and Fidelis Care (New York) |
| Regulations | **Real** federal text, each rule cited to its paragraph |
| Denial letters and EOBs | **Synthetic.** Three letters and two EOBs from our generator, labelled on every page and never written as if from the insurer |
| Model calls | **Real.** Demo cases open from saved Gemini responses for speed; "Run again with the live model" calls Gemini live. The interface always says which answered |
| Outcomes | **Not claimed.** No appeal drafted here has been sent |

### For the judges, criterion by criterion

- **Technical implementation:**
  - a clause index over real PDFs
  - a deterministic grounding verifier
  - four rule tables citing indexed regulations
  - a Gemini → Featherless → saved-response provider chain
  - 220 offline tests
- **Creativity:** the model is only allowed to point, and code checks the pointing. The rules' own legal sources go through the same check.
- **Impact:** it targets the gap between denials and appeals. It gives the deadline, the notice gaps and a ready letter, so filing an appeal becomes a few minutes' work.
- **Design:** generated text sits on one side and the source page on the other. Every sentence links to its highlight, and rejected sentences are greyed out with the reason.
- **Documentation:** the README, the decision log (`docs/decisions.md`), source lists for every plan and regulation, and this table of what's real.
