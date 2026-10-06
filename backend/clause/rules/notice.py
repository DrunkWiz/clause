"""Does a denial notice contain what federal rules require?

Individual-market issuers must meet 29 CFR 2560.503-1(g) (applied by 45 CFR
147.136(b)(3)(i)) and the extra notice rules in 147.136(b)(3)(ii)(E).

Absence is the default. The model may mark an element present only by quoting
the letter, and that quote is checked by the grounding verifier. An element
with no verified quote is reported as "not found in this letter", never as
"the insurer broke the law".

Not checked (TODO): the statement of the right to bring a civil action under
ERISA section 502(a) in 2560.503-1(g)(1)(iv). ERISA covers employer plans;
whether it carries over to individual-market issuers is not settled here.
"""

from __future__ import annotations

from dataclasses import dataclass

from clause.index.model import ClauseIndex
from clause.rules.base import Ref, rule_claim
from clause.rules.deadlines import INTERNAL_APPEAL, URGENT
from clause.verify.verifier import ClaimResult, verify_claim

# When an element is required
ALWAYS = "always"
IF_URGENT = "urgent"
IF_POST_SERVICE = "post_service"
IF_MISSING_INFO = "missing_information"
IF_CLINICAL = "clinical"  # medical necessity or experimental
INFORMATIONAL = "informational"  # "if any" / "if relied upon": cannot be judged missing from the letter

# Denial bases (from the letter or the reason code)
MEDICAL_NECESSITY = "medical_necessity"
EXPERIMENTAL = "experimental"
MISSING_INFORMATION = "missing_information"
OTHER = "other"
BASES = (MEDICAL_NECESSITY, EXPERIMENTAL, MISSING_INFORMATION, OTHER)

AS_GROUP_PLAN = INTERNAL_APPEAL[1]  # 147.136(b)(3)(i): issuer treated as a group health plan


@dataclass(frozen=True)
class Element:
    id: str
    title: str  # what to look for, in plain words
    requirement: str  # the rule claim shown to the person; must be supported by `refs`
    refs: tuple[Ref, ...]
    applies: str = ALWAYS


ELEMENTS: tuple[Element, ...] = (
    Element(
        "reason",
        "The specific reason for the denial",
        "A denial notice must give the specific reason for the denial.",
        (Ref("29 CFR 2560.503-1(g)(1)(i)", "The specific reason or reasons for the adverse determination"), AS_GROUP_PLAN),
    ),
    Element(
        "plan_provision",
        "The plan provision the denial is based on",
        "A denial notice must point to the specific plan provisions the decision is based on.",
        (Ref("29 CFR 2560.503-1(g)(1)(ii)", "Reference to the specific plan provisions on which the determination is based"), AS_GROUP_PLAN),
    ),
    Element(
        "denial_code",
        "The denial code and what it means",
        "A denial notice must include the denial code and its meaning.",
        (Ref("45 CFR 147.136(b)(3)(ii)(E)(3)", "includes the denial code and its corresponding meaning"),),
    ),
    Element(
        "date_of_service",
        "The date of service",
        "A denial notice must identify the claim, including the date of service.",
        (Ref("45 CFR 147.136(b)(3)(ii)(E)(1)", "information sufficient to identify the claim involved (including the date of service"),),
    ),
    Element(
        "provider_name",
        "The name of the health care provider",
        "A denial notice must identify the claim, including the name of the health care provider.",
        (Ref("45 CFR 147.136(b)(3)(ii)(E)(1)", "information sufficient to identify the claim involved (including the date of service, the name of the health care provider"),),
    ),
    Element(
        "claim_amount",
        "The claim amount",
        "A denial notice must identify the claim, including the claim amount where there is one.",
        (Ref("45 CFR 147.136(b)(3)(ii)(E)(1)", "the name of the health care provider, the claim amount (if applicable)"),),
        IF_POST_SERVICE,
    ),
    Element(
        "codes_on_request",
        "A statement that diagnosis and treatment codes are available on request",
        "A denial notice must say that the diagnosis and treatment codes, and their meanings, are available on request.",
        (
            Ref(
                "45 CFR 147.136(b)(3)(ii)(E)(1)",
                "a statement describing the availability, upon request, of the diagnosis code and its corresponding "
                "meaning, and the treatment code and its corresponding meaning",
            ),
        ),
    ),
    Element(
        "review_procedures",
        "How the appeal process works and its time limits",
        "A denial notice must describe the review procedures and their time limits.",
        (Ref("29 CFR 2560.503-1(g)(1)(iv)", "A description of the plan's review procedures and the time limits applicable to such procedures"), AS_GROUP_PLAN),
    ),
    Element(
        "appeal_and_external_review",
        "How to start an internal appeal and an external review",
        "A denial notice must describe the internal appeal and external review processes, including how to start an appeal.",
        (
            Ref(
                "45 CFR 147.136(b)(3)(ii)(E)(4)",
                "The issuer must provide a description of available internal appeals and external review processes, "
                "including information regarding how to initiate an appeal",
            ),
        ),
    ),
    Element(
        "consumer_assistance",
        "Contact details for a consumer assistance office or ombudsman",
        "A denial notice must give contact details for any applicable consumer assistance office or ombudsman.",
        (
            Ref(
                "45 CFR 147.136(b)(3)(ii)(E)(5)",
                "The issuer must disclose the availability of, and contact information for, any applicable office of "
                "health insurance consumer assistance or ombudsman",
            ),
        ),
    ),
    Element(
        "information_needed",
        "What extra information would complete the claim, and why",
        "When a claim is denied for missing information, the notice must say what is needed and why.",
        (
            Ref(
                "29 CFR 2560.503-1(g)(1)(iii)",
                "A description of any additional material or information necessary for the claimant to perfect the "
                "claim and an explanation of why such material or information is necessary",
            ),
            AS_GROUP_PLAN,
        ),
        IF_MISSING_INFO,
    ),
    Element(
        "clinical_explanation",
        "The clinical reasoning, or an offer to provide it free",
        "When a denial is based on medical necessity or experimental treatment, the notice must explain the clinical "
        "judgment or say it will be provided free of charge on request.",
        (
            Ref(
                "29 CFR 2560.503-1(g)(1)(v)(B)",
                "If the adverse benefit determination is based on a medical necessity or experimental treatment or "
                "similar exclusion or limit, either an explanation of the scientific or clinical judgment for the "
                "determination",
            ),
            Ref("29 CFR 2560.503-1(g)(1)(v)(B)", "or a statement that such explanation will be provided free of charge upon request"),
            AS_GROUP_PLAN,
        ),
        IF_CLINICAL,
    ),
    Element(
        "expedited_process",
        "How the expedited (urgent) review works",
        "For an urgent care denial, the notice must describe the expedited review process.",
        (
            Ref("29 CFR 2560.503-1(g)(1)(vi)", "a description of the expedited review process applicable to such claims"),
            AS_GROUP_PLAN,
        ),
        IF_URGENT,
    ),
    Element(
        "internal_criterion",
        "Any internal rule or guideline used, or an offer to provide it free",
        "If the insurer relied on an internal rule or guideline, the notice must include it or say a copy is free on request.",
        (
            Ref(
                "29 CFR 2560.503-1(g)(1)(v)(A)",
                "If an internal rule, guideline, protocol, or other similar criterion was relied upon in making the "
                "adverse determination",
            ),
            AS_GROUP_PLAN,
        ),
        INFORMATIONAL,
    ),
    Element(
        "issuer_standard",
        "The standard the insurer used, if any",
        "The notice must describe the insurer's standard, if any, used to deny the claim.",
        (Ref("45 CFR 147.136(b)(3)(ii)(E)(3)", "as well as a description of the issuer's standard, if any, that was used in denying the claim"),),
        INFORMATIONAL,
    ),
)
ELEMENT_IDS = tuple(e.id for e in ELEMENTS)

DEEMED_EXHAUSTION = (
    Ref(
        "45 CFR 147.136(b)(3)(ii)(F)(1)",
        "In the case of an issuer that fails to adhere to all the requirements of this paragraph (b)(3) with respect "
        "to a claim, the claimant is deemed to have exhausted the internal claims and appeals process",
    ),
    Ref("45 CFR 147.136(b)(3)(ii)(F)(1)", "the claimant may initiate an external review"),
    Ref(
        "45 CFR 147.136(b)(3)(ii)(F)(2)",
        "will not be deemed exhausted based on de minimis violations that do not cause, and are not likely to cause, "
        "prejudice or harm to the claimant",
    ),
)

PRESENT = "present"
NOT_FOUND = "not_found"
NOT_APPLICABLE = "not_applicable"
CHECK = "check"  # informational: ask the insurer


@dataclass(frozen=True)
class ElementResult:
    element: Element
    status: str
    requirement: dict  # rule claim citing the regulation
    evidence: tuple[ClaimResult, ...] = ()  # verified findings from the letter

    def to_dict(self) -> dict:
        return {
            "id": self.element.id,
            "title": self.element.title,
            "status": self.status,
            "requirement": self.requirement,
            "evidence": [e.to_dict() for e in self.evidence],
        }


@dataclass(frozen=True)
class NoticeReport:
    elements: tuple[ElementResult, ...]
    exhaustion: dict | None  # rule claim, set when a required element was not found
    unknown_findings: tuple[str, ...] = ()  # element ids the model used that we do not know

    @property
    def not_found(self) -> tuple[ElementResult, ...]:
        return tuple(e for e in self.elements if e.status == NOT_FOUND)

    def to_dict(self) -> dict:
        return {
            "elements": [e.to_dict() for e in self.elements],
            "not_found": [e.element.id for e in self.not_found],
            "exhaustion": self.exhaustion,
            "unknown_findings": list(self.unknown_findings),
        }


def applies(element: Element, care: str, basis: str) -> str:
    """PRESENT-able ("required"), NOT_APPLICABLE or CHECK for this denial."""
    a = element.applies
    if a == INFORMATIONAL:
        return CHECK
    required = (
        a == ALWAYS
        or (a == IF_URGENT and care == URGENT)
        or (a == IF_POST_SERVICE and care == "post_service")
        or (a == IF_MISSING_INFO and basis == MISSING_INFORMATION)
        or (a == IF_CLINICAL and basis in (MEDICAL_NECESSITY, EXPERIMENTAL))
    )
    return "required" if required else NOT_APPLICABLE


def check_notice(findings, letter: ClauseIndex, care: str, basis: str = OTHER) -> NoticeReport:
    """findings: the model's list of `{element, text, citations}`, citations
    pointing into the denial letter. Malformed findings are ignored, which
    leaves their element unproven."""
    if basis not in BASES:
        raise ValueError(f"basis must be one of {BASES}, not {basis!r}")
    by_element: dict[str, list[ClaimResult]] = {}
    unknown: list[str] = []
    for f in findings if isinstance(findings, list) else []:
        if not isinstance(f, dict):
            continue
        eid = f.get("element")
        if eid not in ELEMENT_IDS:
            unknown.append(str(eid))
            continue
        result = verify_claim(f, letter)
        if result.supported:
            by_element.setdefault(eid, []).append(result)

    results = []
    for e in ELEMENTS:
        evidence = tuple(by_element.get(e.id, ()))
        need = applies(e, care, basis)
        if evidence:
            status = PRESENT
        elif need == "required":
            status = NOT_FOUND
        else:
            status = need
        results.append(ElementResult(e, status, rule_claim(f"notice.{e.id}", e.requirement, *e.refs), evidence))

    exhaustion = None
    if any(r.status == NOT_FOUND for r in results):
        exhaustion = rule_claim(
            "notice.deemed_exhaustion",
            "If an insurer does not follow these rules for your claim, you may be able to skip the internal appeal "
            "and go straight to external review. This does not apply to minor slips that did not harm you.",
            *DEEMED_EXHAUSTION,
        )
    return NoticeReport(tuple(results), exhaustion, tuple(unknown))
