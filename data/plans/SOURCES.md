# Plan documents

Real, public 2026 plan documents, published by each insurer. They were fetched on 2026-10-05 and have not been modified.

| File | Insurer | Document | Source |
| --- | --- | --- | --- |
| `ambetter-tx-silver-sbc-2026.pdf` | Ambetter Health of Texas (Centene) | Summary of Benefits and Coverage, plan 43480TX0010001-00 (Silver) | https://api.centene.com/SBC/2026/43480TX0010001-00.pdf |
| `ambetter-tx-eoc-2026.pdf` | Ambetter Health of Texas (Centene) | Evidence of Coverage 43480TX001-2026 | https://api.centene.com/EOC/2026/43480TX001.pdf |
| `kaiser-ga-gold-hmo-sbc-2026.pdf` | Kaiser Permanente Georgia | Summary of Benefits and Coverage, plan 89942GA0130002-03 (Signature Gold HMO) | https://healthy.kaiserpermanente.org/content/dam/kporg/final/documents/health-plan-documents/summary-of-benefits/ga/individual-family/2026/89942GA0130002-03-en-2026.pdf |
| `kaiser-ga-hmo-eoc-2026.pdf` | Kaiser Permanente Georgia | Individual and family HMO Evidence of Coverage | https://healthy.kaiserpermanente.org/content/dam/kporg/final/documents/health-plan-documents/eoc/ga/individual-family/2026/on-hmo-ga-en.pdf |
| `fidelis-ny-silver-sbc-2026.pdf` | Fidelis Care (New York) | Summary of Benefits and Coverage, Silver | https://www.fideliscare.org/Portals/0/Members/SummaryofBenefits/SBC_Silver_2026.pdf |
| `fidelis-ny-silver-contract-2026.pdf` | Fidelis Care (New York) | HMO subscriber contract, Silver (Dep 25) | https://www.fideliscare.org/Portals/0/Members/SubscriberContracts/Silver_Dep%2025_2026.pdf |

## Pairing checks (2026-10-06)

- **Ambetter TX:** the SBC is for plan 43480TX0010001-00, and the EOC form number is 43480TX001-2026. They share the same plan prefix.
- **Fidelis NY:** the contract's Schedule of Benefits (p.117, "Silver") shows a $2,450 / $4,900 deductible, the same as the SBC. The first contract I fetched was "Silver 250" (Silver Enhanced 73%, $1,855 deductible), which didn't match, so it was replaced.
- **Kaiser GA:** the EOC is Kaiser Georgia's general individual and family HMO document, and the SBC is for one plan under it (Signature Gold HMO). TODO: confirm the EOC applies to Signature Gold. The cover doesn't name the plan.

## Extraction notes (pdfplumber 0.11.10)

- **SBCs** are landscape (792×612) and mostly tables. `find_tables()` returns one row per service, with spanned cells left empty.
- **Kaiser SBC** has hidden 1-point text across the header. Characters smaller than 3pt must be dropped.
- **Kaiser EOC** is two columns, and plain `extract_text()` merges lines across them. The Ambetter EOC and Fidelis contract are one column.
