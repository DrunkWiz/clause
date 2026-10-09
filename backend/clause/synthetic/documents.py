"""The synthetic denial letters and EOBs for the demo and tests.

These are made up. They name the real plan they relate to, so the demo can
cite real plan text, but they are not written as if from the insurer: no
letterhead or logo, and every page says it is a synthetic test document not
issued by any insurer. People, providers, addresses and claim numbers are
fictional.

Each block can carry a `tag`: a notice element id (see clause.rules.notice),
or a fact key for EOBs. The generator uses tags to write ground truth.
"""

from __future__ import annotations

from dataclasses import dataclass, field

HEADER = "SYNTHETIC TEST DOCUMENT — written for the Clause demo. Not issued by any insurer. Not a real notice."


@dataclass(frozen=True)
class P:
    text: str
    tag: str = ""
    bold: bool = False
    size: float = 10


@dataclass(frozen=True)
class T:
    rows: tuple[tuple[str, ...], ...]
    widths: tuple[float, ...]
    tags: tuple[str, ...] = ()  # one per row ("" for none)


@dataclass(frozen=True)
class SyntheticDoc:
    doc_id: str
    kind: str  # "denial" | "eob"
    plan_docs: tuple[str, ...]  # doc ids of the real plan documents it relates to
    title: str
    blocks: tuple
    truth: dict = field(default_factory=dict)  # facts not tied to one block


def _addr(name: str, member_id: str, street: str, city: str) -> tuple[P, ...]:
    return (
        P(name),
        P(f"Member ID: {member_id}"),
        P(street),
        P(city),
    )


# --------------------------------------------------------------- denials

AMBETTER_DENIAL = SyntheticDoc(
    doc_id="synthetic-denial-ambetter-tx",
    kind="denial",
    plan_docs=("ambetter-tx-silver-sbc-2026", "ambetter-tx-eoc-2026"),
    title="Denial: lumbar MRI, medical necessity (plan provision not named)",
    truth={"notice_date": "2026-09-21", "care": "post_service", "basis": "medical_necessity", "gaps": ["plan_provision"]},
    blocks=(
        P("September 21, 2026", tag="notice_date"),
        *_addr("Jordan Reyes", "SYN-4410-2291", "1200 Example Lane", "Austin, TX 78701"),
        P("Your plan: Ambetter Health Solutions Silver 5000 (plan ID 43480TX0010001). Sent by: Member Appeals Unit (synthetic sender)."),
        P("Notice of Adverse Benefit Determination", bold=True, size=13),
        P("Claim number: SYN-CLM-20260914-0071"),
        P("Date of service: September 2, 2026", tag="date_of_service"),
        P("Provider: Lakeside Imaging Center", tag="provider_name"),
        P("Claim amount: $1,840.00", tag="claim_amount"),
        P(
            "We have denied payment for the MRI of the lumbar spine (CPT 72148) because the service was not medically "
            "necessary. Our reviewer found that your records did not show six weeks of conservative treatment, such as "
            "physical therapy, before imaging was ordered.",
            tag="reason",
        ),
        P("Denial code CO-50: the service is not covered because it was not found to be medically necessary.", tag="denial_code"),
        P(
            "You may ask for a copy of the clinical criteria and the reviewer's clinical rationale used in this decision, "
            "free of charge.",
            tag="clinical_explanation",
        ),
        P(
            "You may request the diagnosis code and the treatment code for this claim, and what each code means, at no cost.",
            tag="codes_on_request",
        ),
        P("Your appeal rights", bold=True, size=11),
        P(
            "You or someone you name to act for you may file an internal appeal within 180 days after you receive this "
            "notice. We will decide a post-service appeal within 30 calendar days after we receive it.",
            tag="review_procedures",
        ),
        P(
            "To start an appeal, send a written request and any records that support it to Member Appeals Unit, PO Box "
            "0000, Austin, TX 78700. If we uphold this denial, you may ask for an external review by an Independent Review "
            "Organization that is not part of your plan.",
            tag="appeal_and_external_review",
        ),
        P(
            "For free help with your appeal, you may contact the consumer help line of the Texas Department of Insurance.",
            tag="consumer_assistance",
        ),
    ),
)

KAISER_DENIAL = SyntheticDoc(
    doc_id="synthetic-denial-kaiser-ga",
    kind="denial",
    plan_docs=("kaiser-ga-gold-hmo-sbc-2026", "kaiser-ga-hmo-eoc-2026"),
    title="Denial: knee arthroscopy, no prior authorization (complete notice)",
    truth={"notice_date": "2026-10-01", "care": "post_service", "basis": "other", "gaps": []},
    blocks=(
        P("October 1, 2026", tag="notice_date"),
        *_addr("Sam Whitfield", "SYN-7702-1150", "48 Sample Street", "Decatur, GA 30030"),
        P("Your plan: KP GA Signature Gold HMO (plan ID 89942GA0130002). Sent by: Claims Review (synthetic sender)."),
        P("Notice of Adverse Benefit Determination", bold=True, size=13),
        P("Claim number: SYN-CLM-20260903-1182"),
        P("Date of service: August 27, 2026", tag="date_of_service"),
        P("Provider: Northside Surgical Center", tag="provider_name"),
        P("Claim amount: $6,420.00", tag="claim_amount"),
        P(
            "We have denied payment for an outpatient knee arthroscopy because prior authorization was not obtained "
            "before the procedure.",
            tag="reason",
        ),
        P("Denial code CO-197: prior authorization was required for this service and was not on file.", tag="denial_code"),
        P(
            "This decision is based on the Prior Authorization requirements in Section 7, Benefits, of your Evidence of "
            "Coverage.",
            tag="plan_provision",
        ),
        P(
            "You may request the diagnosis code and the treatment code for this claim, and what each code means, at no cost.",
            tag="codes_on_request",
        ),
        P("Your appeal rights", bold=True, size=11),
        P(
            "You may file an internal appeal within 180 days after you receive this notice. We will decide a post-service "
            "appeal within 60 days after we receive it.",
            tag="review_procedures",
        ),
        P(
            "To start an appeal, write to Member Appeals, PO Box 0000, Atlanta, GA 30300, and include any records that "
            "support your request. If we uphold this denial, you may ask for an external review by an independent "
            "reviewer.",
            tag="appeal_and_external_review",
        ),
        P(
            "For free help, you may contact Consumer Services at the Georgia Office of Commissioner of Insurance and Safety "
            "Fire.",
            tag="consumer_assistance",
        ),
    ),
)

FIDELIS_DENIAL = SyntheticDoc(
    doc_id="synthetic-denial-fidelis-ny",
    kind="denial",
    plan_docs=("fidelis-ny-silver-sbc-2026", "fidelis-ny-silver-contract-2026"),
    title="Urgent denial: proton beam therapy, experimental (expedited process missing)",
    truth={
        "notice_date": "2026-10-02",
        "care": "urgent",
        "basis": "experimental",
        "gaps": ["clinical_explanation", "expedited_process"],
    },
    blocks=(
        P("October 2, 2026", tag="notice_date"),
        *_addr("Alex Moreno", "SYN-3318-6604", "9 Placeholder Road", "Albany, NY 12203"),
        P("Your plan: Ambetter from Fidelis Care Silver. Sent by: Utilization Review (synthetic sender)."),
        P("Notice of Adverse Benefit Determination — Urgent Pre-Service Request", bold=True, size=13),
        P("Request number: SYN-UR-20261001-0447"),
        P("Requested date of service: October 12, 2026", tag="date_of_service"),
        P("Provider: Hudson Valley Proton Center", tag="provider_name"),
        P(
            "We have denied the urgent request for proton beam therapy because we consider it experimental or "
            "investigational for your condition.",
            tag="reason",
        ),
        P("Denial code UM-EXP-02: experimental or investigational treatment.", tag="denial_code"),
        P(
            "This decision is based on the exclusion for experimental or investigational treatment in the Exclusions and "
            "Limitations section of your Contract.",
            tag="plan_provision",
        ),
        P(
            "You may request the diagnosis code and the treatment code for this request, and what each code means, at no "
            "cost.",
            tag="codes_on_request",
        ),
        P("Your appeal rights", bold=True, size=11),
        P(
            "You may file an internal appeal within 180 days after you receive this notice. We will decide a pre-service "
            "appeal within 30 days after we receive it.",
            tag="review_procedures",
        ),
        P(
            "To start an appeal, write to Utilization Review Appeals, PO Box 0000, Albany, NY 12200. If we uphold this "
            "denial, you may ask for an external appeal by an independent reviewer.",
            tag="appeal_and_external_review",
        ),
        P(
            "For free help, you may contact New York's health insurance consumer assistance program.",
            tag="consumer_assistance",
        ),
    ),
)

# ------------------------------------------------------------------ EOBs

_EOB_COLS = ("Service", "Provider", "Billed", "Allowed", "Plan paid", "Adjustment", "Amount")
_EOB_W = (90.0, 104.0, 52.0, 52.0, 52.0, 58.0, 60.0)  # sums to the 468pt text width

AMBETTER_ER_EOB = SyntheticDoc(
    doc_id="synthetic-eob-ambetter-er",
    kind="eob",
    plan_docs=("ambetter-tx-silver-sbc-2026", "ambetter-tx-eoc-2026"),
    title="EOB: out-of-network emergency room, out-of-network cost-sharing applied",
    truth={
        "setting": "emergency",
        "provider_in_network": False,
        "lines": [
            {"tag": "line_er_facility", "group": "PR", "code": "2", "amount": "800.00"},
            {"tag": "line_er_physician", "group": "PR", "code": "2", "amount": "300.00"},
        ],
        "patient_owes": {"tag": "patient_owes", "amount": "1100.00"},
        "plan_in_network_terms": "ambetter-tx-silver-sbc-2026#p3.9",
    },
    blocks=(
        P("Explanation of Benefits — This is not a bill", bold=True, size=13),
        P("Statement date: August 4, 2026"),
        *_addr("Jordan Reyes", "SYN-4410-2291", "1200 Example Lane", "Austin, TX 78701"),
        P("Your plan: Ambetter Health Solutions Silver 5000 (plan ID 43480TX0010001)."),
        P("Claim number: SYN-CLM-20260718-0310. Date of service: July 18, 2026."),
        P("Place of service: Hospital emergency department. Network status: out of network.", tag="setting"),
        T(
            rows=(
                _EOB_COLS,
                ("Emergency room visit, level 4", "Gulf Coast General Hospital", "$3,200.00", "$1,600.00", "$800.00", "PR-2", "$800.00"),
                ("Emergency physician services", "Bayside Emergency Physicians", "$1,150.00", "$600.00", "$300.00", "PR-2", "$300.00"),
            ),
            widths=_EOB_W,
            tags=("", "line_er_facility", "line_er_physician"),
        ),
        P(
            "Cost-sharing applied: out-of-network emergency room coinsurance of 50% of the allowed amount.",
            tag="out_of_network_cost_sharing",
        ),
        P("Total you may owe: $1,100.00", tag="patient_owes", bold=True),
        P(
            "Out-of-network providers may also bill you for the difference between their charges and the allowed amount, "
            "a total of $2,150.00 for this claim.",
            tag="balance_bill",
        ),
        P("Adjustment codes: PR-2 means coinsurance amount (patient responsibility)."),
    ),
)

FIDELIS_SURGERY_EOB = SyntheticDoc(
    doc_id="synthetic-eob-fidelis-surgery",
    kind="eob",
    plan_docs=("fidelis-ny-silver-sbc-2026", "fidelis-ny-silver-contract-2026"),
    title="EOB: out-of-network anesthesiologist at an in-network surgery center; amount owed does not match",
    truth={
        "setting": "nonemergency_at_in_network_facility",
        "provider_in_network": False,
        "facility_in_network": True,
        "specialty": "Anesthesiology",
        "lines": [
            {"tag": "line_surgeon", "group": "PR", "code": "3", "amount": "50.00"},
            {"tag": "line_surgeon_contract", "group": "CO", "code": "45", "amount": "1900.00"},
            {"tag": "line_anesthesia", "group": "OA", "code": "242", "amount": "900.00"},
        ],
        "patient_owes": {"tag": "patient_owes", "amount": "950.00"},
    },
    blocks=(
        P("Explanation of Benefits — This is not a bill", bold=True, size=13),
        P("Statement date: September 15, 2026"),
        *_addr("Alex Moreno", "SYN-3318-6604", "9 Placeholder Road", "Albany, NY 12203"),
        P("Your plan: Ambetter from Fidelis Care Silver."),
        P("Claim number: SYN-CLM-20260828-0522. Date of service: August 28, 2026."),
        P(
            "Place of service: Riverside Surgery Center (in network). Anesthesia by Metro Anesthesia Associates (out of network).",
            tag="setting",
        ),
        T(
            rows=(
                _EOB_COLS,
                ("Knee arthroscopy, surgeon", "Dr. Priya Lang, Riverside Orthopedics", "$4,000.00", "$2,100.00", "$2,050.00", "PR-3", "$50.00"),
                ("Knee arthroscopy, surgeon", "Dr. Priya Lang, Riverside Orthopedics", "", "", "", "CO-45", "$1,900.00"),
                ("Anesthesia", "Metro Anesthesia Associates", "$1,800.00", "$900.00", "$900.00", "OA-242", "$900.00"),
            ),
            widths=_EOB_W,
            tags=("", "line_surgeon", "line_surgeon_contract", "line_anesthesia"),
        ),
        P("Total you may owe: $950.00", tag="patient_owes", bold=True),
        P(
            "The out-of-network anesthesia provider may bill you for the amount above the allowed amount: $900.00.",
            tag="balance_bill",
        ),
        P("Adjustment codes: PR-3 copayment; CO-45 charge above the contracted amount; OA-242 provider not in network."),
    ),
)

ALL = (AMBETTER_DENIAL, KAISER_DENIAL, FIDELIS_DENIAL, AMBETTER_ER_EOB, FIDELIS_SURGERY_EOB)
