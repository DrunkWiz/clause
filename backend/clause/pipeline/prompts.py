"""Prompts for the three model tasks, and the shape checks for their output.

The model reads and locates; it never writes free prose that reaches the
user. Every task returns JSON in which each statement carries citations
`{doc, clause_id, quote}`, and code verifies every one.
"""

from __future__ import annotations

from clause.index.model import Clause
from clause.rules.notice import ELEMENTS

CITATION_RULES = """\
Citation rules (strict):
- Every citation is {"doc": <doc id>, "clause_id": <clause id>, "quote": <text>}.
- clause_id is the full id shown in square brackets, including the part before "#".
  Example: for the line "[plan-eoc#p26.6] Medically necessary means ...", cite {"doc": "plan-eoc", "clause_id": "plan-eoc#p26.6", "quote": "Medically necessary means"}.
- The quote must be copied exactly, word for word, from that one clause. Do not paraphrase, fix typos or join two clauses.
- Quote at least 4 consecutive words, unless the whole clause is shorter.
- Use "..." inside a quote only to skip words within the same clause.
- Only cite clauses that appear in the input, using their exact ids.
"""


def clauses_block(clauses: list[Clause], max_chars: int = 1500) -> str:
    lines = []
    for c in clauses:
        text = " ".join(c.text.split())
        if len(text) > max_chars:
            text = text[:max_chars] + " [...]"
        lines.append(f"[{c.clause_id}] {text}")
    return "\n".join(lines)


# ------------------------------------------------------------ denial facts

DENIAL_SYSTEM = f"""\
You read a health insurance denial letter and locate facts in it. You do not give advice.
Return JSON only, with this shape:
{{
  "facts": [
    {{"field": "notice_date", "citations": [...]}},
    {{"field": "care", "value": "urgent" | "pre_service" | "post_service", "citations": [...]}},
    {{"field": "basis", "value": "medical_necessity" | "experimental" | "missing_information" | "other", "citations": [...]}},
    {{"field": "service", "value": "<the denied service, in the letter's words>", "citations": [...]}},
    {{"field": "reason", "value": "<the stated reason, in the letter's words>", "citations": [...]}}
  ],
  "elements": [
    {{"element": "<element id>", "citations": [...]}}
  ]
}}
For notice_date, quote the letter's date line exactly.
care: "urgent" if the letter treats the request as urgent or expedited; "pre_service" if the care has not happened yet; otherwise "post_service".
For "elements", list each of these that the letter actually contains, citing where. Leave out any you cannot find. Never guess.
Element ids:
{chr(10).join(f"- {e.id}: {e.title}" for e in ELEMENTS)}

{CITATION_RULES}"""


def denial_user(letter: list[Clause]) -> str:
    return f"Denial letter clauses:\n{clauses_block(letter)}"


def validate_denial(data) -> None:
    if not isinstance(data, dict) or not isinstance(data.get("facts"), list) or not isinstance(data.get("elements", []), list):
        raise ValueError("expected {facts: [...], elements: [...]}")


# ---------------------------------------------------------------- EOB facts

EOB_SYSTEM = f"""\
You read a health insurance Explanation of Benefits (EOB) and locate facts in it. You do not give advice.
Return JSON only, with this shape:
{{
  "lines": [{{"group": "CO" | "PR" | "OA" | "PI", "code": "<number>", "amount": "<amount as printed>", "citations": [...]}}],
  "patient_owes": {{"amount": "<amount as printed>", "citations": [...]}} | null,
  "setting": {{"value": "emergency" | "nonemergency_at_in_network_facility" | "air_ambulance" | "ground_ambulance" | "other", "citations": [...]}},
  "provider_in_network": {{"value": true | false, "citations": [...]}},
  "facility_in_network": {{"value": true | false | null, "citations": [...]}},
  "specialty": {{"value": "<specialty of the out-of-network provider, or null>", "citations": [...]}},
  "out_of_network_cost_sharing": {{"citations": [...]}} | null,
  "balance_bill": {{"citations": [...]}} | null
}}
lines: one entry per adjustment (group code and reason code, e.g. "PR-2"), with the amount on that line.
out_of_network_cost_sharing: cite where the EOB says out-of-network cost-sharing was applied, or null.
balance_bill: cite where the EOB says a provider may bill more than your cost-sharing, or null.
If something is not in the EOB, use null. Never guess.

{CITATION_RULES}"""


def eob_user(eob: list[Clause]) -> str:
    return f"EOB clauses:\n{clauses_block(eob)}"


def validate_eob(data) -> None:
    if not isinstance(data, dict) or not isinstance(data.get("lines"), list):
        raise ValueError("expected {lines: [...], ...}")


# ------------------------------------------------------------ appeal draft

SECTIONS = (
    ("denial", "What was denied"),
    ("plan", "What my plan says"),
    ("grounds", "Why the denial should be reversed"),
    ("request", "What I am asking for"),
)

DRAFT_SYSTEM = f"""\
You help a health plan member draft an internal appeal of a denial. You write only claims that the member's own documents support.
Return JSON only:
{{"sections": [{{"id": "<section id>", "claims": [{{"text": "<one or two sentences, first person, as the member>", "citations": [...]}}]}}]}}
Section ids, in order:
{chr(10).join(f"- {sid}: {title}" for sid, title in SECTIONS)}
Rules:
- Every claim must be supported by its citations. A claim without citations will be thrown away.
- Cite the denial letter for what was denied and why, and the plan documents for coverage terms, definitions, exclusions and the appeal process.
- Do not state medical facts, diagnoses, test results or history that are not in the documents. Do not predict the outcome.
- Any number, amount, percentage or number of days in a claim must appear in a quote you cite.
- Keep each claim short and specific. 2 to 5 claims per section.
- Do not mention deadlines or missing notice elements; those are added separately.

{CITATION_RULES}"""


def draft_user(letter: list[Clause], plan: list[Clause], facts: dict) -> str:
    known = "\n".join(f"- {k}: {v}" for k, v in facts.items() if v)
    return (
        f"Facts already checked:\n{known}\n\n"
        f"Denial letter clauses:\n{clauses_block(letter)}\n\n"
        f"Plan document clauses (selected):\n{clauses_block(plan)}"
    )


def validate_draft(data) -> None:
    if not isinstance(data, dict) or not isinstance(data.get("sections"), list):
        raise ValueError("expected {sections: [...]}")
    for s in data["sections"]:
        if not isinstance(s, dict) or not isinstance(s.get("claims"), list):
            raise ValueError("each section needs claims")
