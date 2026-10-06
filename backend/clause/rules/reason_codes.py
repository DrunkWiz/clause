"""Claim adjustment reason codes (CARCs) and group codes on an EOB.

The code numbers are X12's (https://x12.org/codes/claim-adjustment-reason-codes,
checked 2026-10-06). X12's descriptions are copyrighted, so the meanings
below are our own plain-language wording, not X12's text, and are shown as
explanation rather than as cited fact.

What a group code means is cited to CMS guidance (MLN905367) in the
regulations index. That guidance is written for Medicare; for private plans
the network contract decides who pays, so the interface says "ask".

Inputs are lines the model extracted from the EOB, each with a citation of
the EOB text it came from. Rule claims cite that text, so every code and
amount they mention is checked against the EOB by the grounding verifier.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from clause.rules.base import Ref, rule_claim
from clause.rules.notice import EXPERIMENTAL, MEDICAL_NECESSITY, MISSING_INFORMATION, OTHER

X12_URL = "https://x12.org/codes/claim-adjustment-reason-codes"
CMS = "CMS MLN905367 (Remittance Advice Resources and FAQs), p.2"
GROUP_ASSIGNS = Ref(CMS, "Group Codes assign financial responsibility for the unpaid portion of the claim/service-line balance")
CO_PR = Ref(
    CMS,
    "A Contractual Obligation (CO) Group Code assigns responsibility to the provider and Patient Responsibility (PR) "
    "Group Code assigns responsibility to the patient",
)


@dataclass(frozen=True)
class Group:
    code: str
    name: str
    responsible: str | None  # "provider" | "patient" | None (not assigned by the code alone)


GROUPS = {
    "CO": Group("CO", "contractual obligation", "provider"),
    "PR": Group("PR", "patient responsibility", "patient"),
    "OA": Group("OA", "other adjustment", None),
    "PI": Group("PI", "payer-initiated reduction", None),
}


@dataclass(frozen=True)
class Carc:
    code: str
    meaning: str  # our words
    next_step: str  # our words; actions to take, not legal conclusions
    basis: str = OTHER  # denial basis for the notice-completeness rule


CARCS = {
    c.code: c
    for c in (
        Carc("1", "This amount went toward your deductible.", "Check it against the deductible in your plan summary."),
        Carc("2", "This is your coinsurance share.", "Check the percentage against your plan summary."),
        Carc("3", "This is your copay.", "Check the amount against your plan summary."),
        Carc(
            "16",
            "The claim was missing information or had a billing error.",
            "Ask the provider's billing office to correct and resubmit the claim before you pay.",
            MISSING_INFORMATION,
        ),
        Carc("18", "The insurer sees this as a duplicate of a claim it already processed.", "Check that you are not being billed twice."),
        Carc("22", "The insurer thinks another plan should pay first.", "Tell the insurer whether you have other coverage."),
        Carc("27", "The service date is after the coverage ended.", "Check your coverage dates and contact the insurer if they are wrong."),
        Carc("29", "The claim was filed too late.", "Late filing is usually the provider's step. Ask the provider whether this can be billed to you."),
        Carc("39", "Prior authorization was requested and denied.", "You can appeal the authorization decision."),
        Carc(
            "45",
            "The charge is above the allowed or contracted amount.",
            "If the provider is in network, ask whether this amount is written off rather than billed to you.",
        ),
        Carc(
            "50",
            "The insurer decided the service was not medically necessary.",
            "This can be appealed. A letter from your doctor explaining why you needed it is usually the core of the appeal.",
            MEDICAL_NECESSITY,
        ),
        Carc(
            "55",
            "The insurer considers the treatment experimental or investigational.",
            "This can be appealed. Ask for the clinical criteria the insurer used.",
            EXPERIMENTAL,
        ),
        Carc("96", "The plan does not cover this charge.", "Ask which plan provision excludes it. The denial notice must name it."),
        Carc("97", "This is included in the payment for another service.", "Ask the provider whether it is being billed to you separately."),
        Carc("109", "The claim went to the wrong insurer.", "Give the provider your correct insurance details."),
        Carc("119", "You have reached the plan's limit for this service.", "Check the limit in your plan documents."),
        Carc("151", "The insurer thinks the records do not support this many services.", "Ask the provider to send supporting records."),
        Carc("167", "The diagnosis is not covered.", "Check the diagnosis code with your provider; a coding error is common."),
        Carc(
            "197",
            "Prior authorization or notification was missing.",
            "Ask the provider whether getting authorization was their job. This can be appealed.",
        ),
        Carc("204", "This service is not covered under your current plan.", "Ask which plan provision excludes it."),
        Carc(
            "242",
            "The provider is not in the plan's network.",
            "If this was emergency care, or care at an in-network hospital, check the No Surprises Act result.",
        ),
        Carc("243", "The service was not authorized by a network or primary care provider.", "Ask whether a referral was needed and who should have got it."),
    )
}


@dataclass(frozen=True)
class Explanation:
    group: str
    code: str
    known: bool
    meaning: str
    next_step: str
    basis: str
    claims: tuple[dict, ...]  # cited rule claims about responsibility

    def to_dict(self) -> dict:
        return {
            "group": self.group,
            "code": self.code,
            "known": self.known,
            "meaning": self.meaning,
            "next_step": self.next_step,
            "basis": self.basis,
            "x12_url": X12_URL,
            "claims": list(self.claims),
        }


def _money(line: dict) -> str | None:
    """The line's amount as "$1,234.56" if its quote shows a "$", else as a
    plain number, so the verifier's money check applies exactly when the EOB
    itself writes a dollar sign."""
    try:
        d = Decimal(str(line.get("amount")).replace(",", "").replace("$", ""))
    except (InvalidOperation, ValueError):
        return None
    quote = (line.get("citation") or {}).get("quote", "")
    return f"${d:,.2f}" if "$" in quote else f"{d:,.2f}"


def explain(line: dict) -> Explanation:
    """line: {group, code, amount?, citation}, as extracted from the EOB."""
    group = str(line.get("group", "")).upper().strip()
    code = str(line.get("code", "")).strip().lstrip("0") or "0"
    carc = CARCS.get(code)
    g = GROUPS.get(group)
    claims: list[dict] = []
    cit = line.get("citation")
    if g and g.responsible and isinstance(cit, dict):
        amount = _money(line)
        what = f"The {amount} adjustment" if amount else "This adjustment"
        whom = "the provider, not you" if g.responsible == "provider" else "you"
        claims.append(
            rule_claim(
                f"reason_code.group.{group}",
                f"{what} with code {group}-{code} is marked {g.name}, which assigns responsibility to {whom}.",
                cit,
                CO_PR,
            )
        )
    return Explanation(
        group=group,
        code=code,
        known=carc is not None,
        meaning=carc.meaning if carc else "We do not have a plain-language meaning for this code yet. Look it up on the X12 list.",
        next_step=carc.next_step if carc else "Ask the insurer what this code means for your claim.",
        basis=carc.basis if carc else OTHER,
        claims=tuple(claims),
    )


def denial_basis(lines: list[dict]) -> str:
    """The basis the notice rule should use, from the codes on the EOB."""
    bases = {CARCS[c].basis for c in (str(l.get("code", "")).lstrip("0") for l in lines) if c in CARCS}
    for b in (MEDICAL_NECESSITY, EXPERIMENTAL, MISSING_INFORMATION):
        if b in bases:
            return b
    return OTHER


def check_patient_share(lines: list[dict], patient_owes: dict | None) -> list[dict]:
    """Flag when what the EOB says you owe is not backed by PR adjustments.

    patient_owes: {amount, citation} for the EOB's "you may owe" figure.
    Returns rule claims (empty when nothing to flag)."""
    if not patient_owes or not isinstance(patient_owes.get("citation"), dict):
        return []
    try:
        owes = Decimal(str(patient_owes.get("amount")).replace(",", "").replace("$", ""))
    except (InvalidOperation, ValueError):
        return []
    if owes <= 0:
        return []
    owes_text = _money(patient_owes)
    pr = [l for l in lines if str(l.get("group", "")).upper() == "PR" and isinstance(l.get("citation"), dict)]
    if not pr:
        return [
            rule_claim(
                "reason_code.no_pr",
                f"The EOB says you may owe {owes_text}, but none of its adjustments are marked PR (patient "
                f"responsibility). Ask the insurer and provider why you are being asked to pay.",
                patient_owes["citation"],
                CO_PR,
            )
        ]
    total = Decimal(0)
    for l in pr:
        try:
            total += Decimal(str(l.get("amount")).replace(",", "").replace("$", ""))
        except (InvalidOperation, ValueError):
            return []
    if total == owes:
        return []
    amounts = ", ".join(a for a in (_money(l) for l in pr) if a)
    return [
        rule_claim(
            "reason_code.pr_mismatch",
            f"The EOB says you may owe {owes_text}, but the adjustments marked PR (patient responsibility) are "
            f"{amounts}. Ask the insurer to explain the difference.",
            patient_owes["citation"],
            *(l["citation"] for l in pr),
            GROUP_ASSIGNS,
            CO_PR,
        )
    ]


def all_refs() -> list[Ref]:
    return [GROUP_ASSIGNS, CO_PR]
