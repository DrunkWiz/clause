# Clause — project brief

[ML Build Challenge 3](https://ml-build-challenge-3.devpost.com/) · solo · drafted 5 Oct 2026. Deadline **Sat 10 Oct, 2:45pm SGT** (11:45pm PDT on 9 Oct, per the overview; the rules page says 10 Oct, 9pm PDT, so plan to the earlier one). Working time: about five days, overlapping Threshold's week 3.

Judged on technical implementation 30%, creativity 20%, impact 20%, design 15%, documentation 15%. Sponsor tools count under technical.

## One line

A health insurance assistant that reads your own plan and only tells you what it can point to: whether something is covered, whether your EOB is right, and how to appeal a denial before the deadline passes.

## Who it's for

The person holding a denial letter who doesn't know they can fight it. HealthCare.gov insurers denied 19% of in-network claims in 2023, and consumers appealed about 1% of those ([KFF](https://www.kff.org/private-insurance/healthcare-gov-insurers-denied-nearly-1-in-5-in-network-claims-in-2023-but-information-about-reasons-is-limited-in-public-data/)). A separate KFF survey found only 40% of consumers knew they had the right to appeal.

People aren't losing appeals so much as never filing them. The same person also can't tell whether a procedure will be covered before it happens, or whether an EOB is wrong after it arrives. Those three moments are one problem: not knowing what your own plan says.

US-only for the hackathon. The judges are US-based engineers, and most will have fought an insurer themselves. Note that patients rarely file claims; providers do. So the product starts where patients actually get stuck, not at filing.

## The spine: one index, three moments

One pipeline with three outputs reads as a product; three separate features read as unfinished.

```
  Your documents                          Clause index
  plan summary, evidence of coverage  →   every paragraph: id, doc, page,
  EOB or denial letter (synthetic)        bounding box, exact text
                                                  │
              ┌───────────────────────────────────┼───────────────────────────┐
              ↓                                   ↓                           ↓
        BEFORE CARE                          AFTER CARE                 AFTER A DENIAL
        Will this be covered?                Is this EOB right?         Deadline, notice check,
        prior auth, cost-sharing,            reason codes and No        then a drafted appeal
        network status from the plan         Surprises rules in code    with every claim cited
              │                                   │                           │
              └───────────────────────────────────┼───────────────────────────┘
                                                  ↓
                          GROUNDING VERIFIER
                          each claim's quote must appear in the clause it cites;
                          a claim that fails is dropped or greyed out
                                                  ↓
                          SIDE-BY-SIDE VIEW
                          generated text | source page with its highlight
```

The four rules run inside the EOB and appeal moments as plain code; the model only extracts their inputs. If time runs short, cut "before care" first, then the EOB check. The appeal is the hero of the demo and must survive.

## The design decision that carries the project

**The model may only say what it can point to, and code checks the pointing.** The model never returns free prose. It returns a list of claims, each carrying citations:

```
{ text, citations: [ { doc, clause_id, quote } ] }
```

Plain code then checks every citation: the clause id must exist in the index, and the quoted span must appear in that clause after whitespace and punctuation normalisation. A claim that fails is never shown as fact. It is dropped, or shown greyed out as "not supported by your documents." The interface puts the generated text on one side and the source pages on the other, with every sentence linked to its highlight.

This is the Voucher Kaki and Threshold lesson in its strongest form: model for reading and judgement, code for correctness. "Grounded" stops being a promise and becomes a test that can fail, which is the answer to the judge question about hallucinated medical or legal claims. The verifier is small, deterministic and unit-testable, so it carries a disproportionate share of the 30% technical score.

## Rules that are code, not model

Four checks run as plain deterministic code. The model extracts the inputs (a date, a code, a place of service); the rule decides. Each rule is a table in the repo with its regulatory source beside it, and each gets its own tests.

| Rule | Input | Output |
| --- | --- | --- |
| Appeal deadlines | Denial letter date, urgency, pre- or post-service | Last day for internal appeal (180 days), insurer's decision window (72 hours urgent, 30 days pre-service, 60 days post-service), then 4 months to request external review |
| Reason codes | Standard claim adjustment reason codes on the EOB | Plain-language meaning and the next step, e.g. missing prior authorisation, medical necessity, missing information |
| Notice completeness | Denial letter, as extracted fields | Missing required elements, such as the specific plan provision relied on or the appeal and external review instructions. A missing element is an appeal point in itself |
| No Surprises Act | Place and type of service, network status, cost-sharing billed | Flags emergency care, or certain out-of-network care at in-network facilities, billed above in-network cost-sharing |

All figures above are from memory of the federal rules for non-grandfathered plans. **Verify each against the regulation text when coding it**, and record the citation in the rule table. State rules can be stricter; the tool says it applies federal minimums only.

## What is real and what is synthetic

Said plainly in the README, the Devpost text and the video, as with Threshold.

| Piece | Status |
| --- | --- |
| Plan documents | **Real.** Marketplace plans publish their Summary of Benefits and Coverage and Evidence of Coverage. Use two or three real ones from different insurers. |
| Denial letters | **Synthetic.** Real ones carry someone's health data. Generated from a template that follows the required notice format, with deliberate gaps in some. Generator in the repo. |
| EOBs | **Synthetic**, same generator, using real reason codes. |
| Rules | **Real** federal rules, each cited to its regulation. |
| Model calls | **Real**, live, with a fallback rung. |
| Outcomes | **Not claimed.** We cannot say any appeal drafted here succeeded, because none has been sent. |

The tool drafts; the person sends. It never contacts an insurer or provider, the same "witness, not controller" position as Threshold.

## Stack

Reuse what already works from Voucher Kaki, so the days go into the product rather than the plumbing.

- **Backend:** Python, stdlib wherever possible. PDF text extraction is the one place a dependency earns its keep; pick one library and say so, rather than claiming zero.
- **Frontend:** React + Vite. pdf.js renders the source pages and draws the highlights.
- **Model:** Gemini Flash as the main rung, **Featherless** as the fallback, behind the same `Provider` chain as Voucher Kaki. That gives sponsor-tool credit for an afternoon's work.
- **Clause index:** each paragraph gets an id, a document, a page, a bounding box and its exact text. Everything downstream reads from it.
- **Privacy:** documents are processed in memory and never stored server-side; the case lives in `localStorage`. "Your records go nowhere" is the answer to the first judge question.
- **Tests:** offline fixtures, a fake model gateway, no network in the suite. The verifier and the four rules carry most of the tests.

## Five days

The appeal flow must work end to end by Thursday night; Friday is for the video and the write-up, not code. Saturday morning is buffer only.

| Day (SGT) | Ships |
| --- | --- |
| Mon 5 – Tue 6 Oct | Clause index and grounding verifier, with tests. Pick the real plans and test extraction on them first. |
| Wed 7 Oct | The four rules in code, each with its citation and tests. Re-read the submission form. |
| Thu 8 Oct | Appeal drafter and the side-by-side highlight interface. End to end by night. |
| Fri 9 Oct | Video, Devpost write-up, README. No new code. |
| Sat 10 Oct, until 2:45pm | Buffer and submit. |

Cut order if behind: "before care" first, then the EOB check. Threshold's week 3 (6–12 Oct) runs alongside.

## The video, in beats

Lead with the denial letter, not the architecture. Most judges stop watching around ninety seconds.

1. **0:00–0:15.** A denial letter on screen. "One in five claims denied. One in a hundred appealed."
2. **0:15–1:00.** Upload the letter and the plan. The deadline appears, counting down. The notice-completeness check flags that the letter never names the plan clause it relies on.
3. **1:00–1:40.** The appeal drafts. Click any sentence and the plan page opens with the clause highlighted. Show one sentence the verifier rejected, greyed out, and say why it isn't there.
4. **1:40–2:10.** The other two moments, quickly: a coverage question answered from the plan, and an EOB flagged under the No Surprises Act.
5. **2:10–2:40.** Architecture in thirty seconds: clause index, verifier, rules, provider chain.
6. **2:40–3:00.** What is real, what is synthetic, said plainly.

## Submission checklist

Re-read the Devpost submission requirements on Wednesday; this list is from the brief, not the form.

- [ ] Public repo with licence, README and the "real vs synthetic" table
- [ ] Live demo link, working with the bundled synthetic letters and no upload needed
- [ ] Demo video under 3 minutes
- [ ] Devpost text mapped to the five judging criteria, in their order
- [ ] Sponsor tools named, and where Featherless sits in the chain
- [ ] Disclaimer in the product: information about your plan, not legal or medical advice
- [ ] Test suite runs with no network and no key

## Revenue model

The patient uses it free; someone with a budget and a reason pays. Revenue isn't judged here, but it answers "who keeps this alive?" and makes the impact claim believable.

| Payer | Why they pay |
| --- | --- |
| Hospital financial counselling teams | Unpaid denied bills become their bad debt; faster appeals recover revenue |
| Independent patient advocates | Turns hours of document reading into minutes per case |
| Employers, as a benefit | Fewer employees stuck in billing disputes; sold through benefits platforms |

Others already work on denial appeals. Enforced grounding is the differentiator, and it is also what a hospital's compliance team would ask for first.

## Known risks

1. **Threshold slips.** These days are Threshold's week 3, its hardest. Decide today which Threshold work moves to week 4, and protect the 19 Oct freeze.
2. **PDF extraction is messier than it looks.** Plan documents have tables, columns and footnotes. Test on the real plans on Monday, and fall back to page-level citations if paragraph-level ones break.
3. **Rules stated wrong.** A wrong deadline harms the exact person this is for. Every rule cites its regulation, and the interface says to confirm dates with the insurer.
4. **Read as legal or medical advice.** The product explains the person's own documents and drafts a letter they choose to send. It never predicts an outcome.
5. **Verifier too strict.** Normalisation that is too tight rejects good claims and leaves an empty letter. Tune it on the synthetic set and report the rejection rate honestly.

## Open

- **Name.** "Clause" is the working title, because every sentence it writes rests on one. Alternatives welcome.
- **Main model.** Gemini Flash is assumed because the Voucher Kaki provider code exists. Confirm the key and quota still work.
- **Which plans.** Pick two or three real marketplace plans from different insurers on Monday, before writing the extractor.
- **Submission rules.** Confirm on the Devpost page whether a project started inside the challenge window has any extra requirements.
