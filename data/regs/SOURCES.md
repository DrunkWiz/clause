# Regulation sources

Text the rules cite, indexed into `regs_index.json` so rule outputs pass the same grounding verifier as everything else. US government works, in the public domain.

- **Refetch:** `python scripts/regs.py fetch`
- **Rebuild the index (offline):** `python scripts/regs.py build`
- **Freshness check:** a test fails if the committed index doesn't match the raw files.

| File | What | Source | As of |
| --- | --- | --- | --- |
| `raw/45-cfr-147.136.html` | Internal claims, appeals and external review | eCFR renderer API | 2026-10-01 |
| `raw/29-cfr-2560.503-1.html` | Claims procedure: notice content, appeal and decision time limits | eCFR renderer API | 2026-09-30 |
| `raw/45-cfr-149.110.html` | No Surprises: emergency services | eCFR renderer API | 2026-10-01 |
| `raw/45-cfr-149.120.html` | No Surprises: out-of-network providers at in-network facilities | eCFR renderer API | 2026-10-01 |
| `raw/45-cfr-149.130.html` | No Surprises: air ambulance | eCFR renderer API | 2026-10-01 |
| `raw/45-cfr-149.410.html` | Balance billing: emergency services | eCFR renderer API | 2026-10-01 |
| `raw/45-cfr-149.420.html` | Balance billing at in-network facilities; notice and consent exceptions | eCFR renderer API | 2026-10-01 |
| `raw/5-usc-6103.htm` | Legal public holidays | GovInfo, US Code 2024 edition | 2024 ed. |
| `raw/cms-mln905367.pdf` | CMS "Remittance Advice Resources and FAQs" (MLN905367): meaning of group codes CO and PR. This is guidance, not regulation, and is written for Medicare. | cms.gov | fetched 2026-10-06 |

Full URLs are listed in `backend/clause/index/regs.py` (`SOURCES`).

## Figures checked against this text (2026-10-06)

| Figure | Citation |
| --- | --- |
| At least 180 days to file an internal appeal | 29 CFR 2560.503-1(h)(3)(i), applied to individual coverage by 45 CFR 147.136(b)(3)(i) |
| One level of internal appeal (individual market) | 45 CFR 147.136(b)(3)(ii)(G) |
| Appeal decision: 72 hours urgent, 30 days pre-service, 60 days post-service | 29 CFR 2560.503-1(i)(2)(i), (ii), (iii)(A) |
| External review request within four months; first day of the fifth month if no matching date; extended past a Saturday, Sunday or federal holiday | 45 CFR 147.136(d)(2)(i) |
| A state process must allow at least four months | 45 CFR 147.136(c)(2)(vi) |
| External review decision: 45 days standard, 72 hours expedited | 45 CFR 147.136(d)(2)(iii)(B)(6), (d)(3)(iv) |
| Federal holidays are the dates in 6103(a); the observed-day rules in 6103(b) cover pay and leave only | 5 U.S.C. 6103 |
| Notice contents | 29 CFR 2560.503-1(g)(1); 45 CFR 147.136(b)(3)(ii)(E)(1)–(5) |
| Deemed exhaustion, with the de minimis exception | 45 CFR 147.136(b)(3)(ii)(F)(1)–(2) |
| No Surprises protections and the no-consent-exception list | 45 CFR 149.110, 149.120, 149.130, 149.410, 149.420(b) |

Claim adjustment reason code numbers were checked against https://x12.org/codes/claim-adjustment-reason-codes on 2026-10-06. Their descriptions are X12 copyright and are not copied into the repo.
