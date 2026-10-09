# Demo video script (2:09)

The recorded video is `submission/clause-demo.mp4` (1920x1080, narrated with the Kokoro `am_echo` voice, generated locally, captions burned in). `clause-demo.srt` holds the same captions for YouTube. To narrate it yourself instead, read the right-hand column at the times shown; each line fits in its slot at a calm pace.

Recorded on 10 Oct 2026 against the local server with the bundled demo cases, which replay saved Gemini responses (the app shows "From a saved Gemini response"). The countdown reads 161 days on that date.

| Time | On screen | Narration |
| --- | --- | --- |
| 00:00 | Title card: 1 in 5 in-network claims denied, fewer than 1 in 100 appealed (KFF, 2023). | In 2023, insurers on HealthCare.gov denied nearly one in five in-network claims. |
| 00:07 |  | Fewer than one in a hundred of those denials were appealed. |
| 00:11 | Home page. Cursor moves over the headline. | Clause is for the person holding that denial letter. |
| 00:15 | Click the first denial card, "Denial: lumbar MRI, medical necessity". | It reads their own plan and their letter, and it only says what it can point to. |
| 00:20 |  | Here's a synthetic denial for an MRI, checked against a real Ambetter plan from Texas. |
| 00:26 | Click "From the letter" beside the notice date. The letter opens on the right with the date highlighted. | Gemini reads the key facts from the letter, and each one links to the line it came from. |
| 00:31 | Point at the countdown (161 days on 10 Oct), then click the 147.136(b)(3)(i) citation. The regulation opens, highlighted. | The appeal deadline is computed by code, not by the model, and it cites the federal regulation it comes from. |
| 00:38 | Scroll to "Is the denial notice complete?". Point at "1 missing". | Clause also checks the letter against everything a federal denial notice must include. |
| 00:44 | Point at "The plan provision the denial is based on: Not found", click "The rule". 29 CFR 2560.503-1(g)(1)(ii) opens. | This one never names the plan provision it relies on. That gap is an appeal point in itself. |
| 00:50 | Scroll to "Your appeal, drafted". | Then Gemini drafts the appeal. But it never writes free prose. |
| 00:54 |  | Every sentence must quote the passage it rests on, and code checks that quote, word for word. |
| 01:00 | Click "My plan covers medically necessary radiology services...". The plan's EOC opens at page 99, highlighted. | Click any sentence, and the plan page opens with the passage highlighted. |
| 01:05 | Click the pencil on "The denied claim is for $1,840.00...". | What if a sentence says something the documents don't? |
| 01:08 | Select 1,840.00 and type 2,400.00. | Change the claim amount to one the letter never mentions. |
| 01:12 | Click "Save and re-check". The sentence is struck through: "It mentions $2,400, but the quoted text doesn't." | The verifier rejects it. It's greyed out with the reason, and left out of the letter. |
| 01:17 | Click "All cases", then the EOB card "out-of-network emergency room". | The same pipeline checks an explanation of benefits. |
| 01:22 | Click the first flag. The EOB line opens, highlighted. Point at "Protected by the No Surprises Act". | This out-of-network emergency visit was charged out-of-network cost-sharing. Under the No Surprises Act, it shouldn't be, so Clause flags it. |
| 01:30 | Architecture slide: documents, clause index, Gemini Flash, grounding verifier, side-by-side view; four rules; provider chain. | Under the hood, every paragraph of the plan, the letter and the federal regulations gets an address. |
| 01:36 |  | Gemini Flash extracts and drafts, with a fallback chain behind it. |
| 01:41 |  | A grounding verifier checks every citation, and four rule tables handle deadlines, notice gaps, reason codes and surprise billing, in plain code. |
| 01:50 |  | Two hundred and twenty tests run with no network and no API key. |
| 01:55 | Real / synthetic / not claimed slide, with the disclaimer. | The plans and regulations are real. The denial letters and benefit statements are synthetic, and labelled that way. |
| 02:02 |  | Clause never contacts your insurer. It drafts. You decide what to send. |
