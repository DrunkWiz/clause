"""No Surprises Act protections (45 CFR part 149), federal minimums only.

The rule decides whether a bill falls under a protection, from facts the
model extracts (with citations) from the EOB or bill. It cannot compute the
exact allowed cost-sharing, because the insurer's qualifying payment amount
is not public. So it flags out-of-network cost-sharing or balance billing on
protected care and points to the plan's own in-network terms.

Not covered here: ground ambulance (outside these federal rules; some states
cover it), and state surprise-billing laws, which can be stricter.
"""

from __future__ import annotations

from dataclasses import dataclass

from clause.rules.base import Ref, rule_claim

EMERGENCY = "emergency"
NONEMERGENCY_AT_IN_NETWORK_FACILITY = "nonemergency_at_in_network_facility"
AIR_AMBULANCE = "air_ambulance"
GROUND_AMBULANCE = "ground_ambulance"
OTHER = "other"
SETTINGS = (EMERGENCY, NONEMERGENCY_AT_IN_NETWORK_FACILITY, AIR_AMBULANCE, GROUND_AMBULANCE, OTHER)

# ---------------------------------------------------------------- rule table

ER_NO_PRIOR_AUTH = Ref("45 CFR 149.110(b)(1)", "Without the need for any prior authorization determination, even if the services are provided on an out-of-network basis.")
ER_ANY_NETWORK = Ref(
    "45 CFR 149.110(b)(2)",
    "Without regard to whether the health care provider furnishing the emergency services is a participating provider or a participating emergency facility",
)
ER_COST_SHARING = Ref(
    "45 CFR 149.110(b)(3)(ii)",
    "Without imposing cost-sharing requirements that are greater than the requirements that would apply if the services were provided by a participating provider or a participating emergency facility.",
)
ER_FACILITY_NO_BALANCE_BILL = Ref(
    "45 CFR 149.410(a)(1)",
    "A nonparticipating emergency facility must not bill, and must not hold liable, the participant, beneficiary, or enrollee for a payment amount for such emergency services",
)
ER_PROVIDER_NO_BALANCE_BILL = Ref(
    "45 CFR 149.410(a)(2)",
    "A nonparticipating provider must not bill, and must not hold liable, the participant, beneficiary, or enrollee for a payment amount for an emergency service",
)
ER_POST_STABILIZATION = Ref(
    "45 CFR 149.410(b)",
    "The requirements in paragraph (a) of this section do not apply with respect to items and services described in",
)

FACILITY_COVERED = Ref(
    "45 CFR 149.120(b)",
    "items and services (other than emergency services) furnished to a participant, beneficiary, or enrollee by a nonparticipating provider with respect to a visit at a participating health care facility, unless the provider has satisfied the notice and consent criteria",
)
FACILITY_COST_SHARING = Ref(
    "45 CFR 149.120(c)(1)",
    "Must not impose a cost-sharing requirement for the items and services that is greater than the cost-sharing requirement that would apply if the items or services had been furnished by a participating provider.",
)
FACILITY_NO_BALANCE_BILL = Ref(
    "45 CFR 149.420(a)",
    "must not bill, and must not hold liable, a participant, beneficiary, or enrollee of such plan or coverage for a payment amount for such an item or service furnished by such provider with respect to a visit at the facility that exceeds the cost-sharing requirement for such item or service",
)
NO_CONSENT_EXCEPTION = Ref(
    "45 CFR 149.420(b)",
    "The notice and consent criteria in paragraphs (c) through (i) of this section do not apply, and a nonparticipating provider specified in paragraph (a) of this section will always be subject to the prohibitions in paragraph (a) of this section, with respect to the following services",
)
ANCILLARY = {
    "emergency_anesthesia_pathology_radiology_neonatology": Ref(
        "45 CFR 149.420(b)(1)(i)",
        "Items and services related to emergency medicine, anesthesiology, pathology, radiology, and neonatology, whether provided by a physician or non-physician practitioner",
    ),
    "assistant_surgeon_hospitalist_intensivist": Ref(
        "45 CFR 149.420(b)(1)(ii)", "Items and services provided by assistant surgeons, hospitalists, and intensivists"
    ),
    "diagnostic": Ref("45 CFR 149.420(b)(1)(iii)", "Diagnostic services, including radiology and laboratory services"),
    "no_in_network_option": Ref(
        "45 CFR 149.420(b)(1)(iv)",
        "Items and services provided by a nonparticipating provider if there is no participating provider who can furnish such item or service at such facility",
    ),
}
UNFORESEEN = Ref(
    "45 CFR 149.420(b)(2)",
    "Items or services furnished as a result of unforeseen, urgent medical needs that arise at the time an item or service is furnished, regardless of whether the nonparticipating provider satisfied the notice and consent criteria",
)
AIR_COST_SHARING = Ref(
    "45 CFR 149.130(b)(1)",
    "The cost-sharing requirements with respect to the services must be the same requirements that would apply if the services were provided by a participating provider of air ambulance services.",
)

# Specialty keywords -> which ancillary category (149.420(b)(1)) they fall in.
SPECIALTY_KEYWORDS = {
    "emergency": "emergency_anesthesia_pathology_radiology_neonatology",
    "anesthes": "emergency_anesthesia_pathology_radiology_neonatology",
    "anaesthes": "emergency_anesthesia_pathology_radiology_neonatology",
    "patholog": "emergency_anesthesia_pathology_radiology_neonatology",
    "radiolog": "emergency_anesthesia_pathology_radiology_neonatology",
    "neonat": "emergency_anesthesia_pathology_radiology_neonatology",
    "assistant surgeon": "assistant_surgeon_hospitalist_intensivist",
    "hospitalist": "assistant_surgeon_hospitalist_intensivist",
    "intensivist": "assistant_surgeon_hospitalist_intensivist",
    "laborator": "diagnostic",
    "diagnostic": "diagnostic",
}

# ------------------------------------------------------------------ output

PROTECTED = "protected"
PROTECTED_UNLESS_CONSENT = "protected_unless_valid_consent"
MAY_HAVE_WAIVED = "may_have_waived_by_consent"
NOT_COVERED = "not_covered_by_these_rules"


@dataclass(frozen=True)
class NsaResult:
    status: str
    claims: tuple[dict, ...]  # why it is (or may be) protected, cited
    flags: tuple[dict, ...]  # problems found on the bill, cited
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {"status": self.status, "claims": list(self.claims), "flags": list(self.flags), "notes": list(self.notes)}


def ancillary_category(specialty: str | None) -> str | None:
    s = (specialty or "").lower()
    for key, cat in SPECIALTY_KEYWORDS.items():
        if key in s:
            return cat
    return None


def check_bill(
    setting: str,
    provider_in_network: bool,
    *,
    facility_in_network: bool | None = None,
    specialty: str | None = None,
    consent_signed: bool | None = None,
    unforeseen_urgent: bool = False,
    no_in_network_option: bool = False,
    out_of_network_cost_sharing: dict | None = None,
    balance_bill: dict | None = None,
    plan_in_network_terms: dict | None = None,
) -> NsaResult:
    """Does a federal No Surprises protection apply, and does the bill break it?

    out_of_network_cost_sharing / balance_bill: citations (into the EOB or
    bill) showing out-of-network cost-sharing was applied, or that the
    provider billed beyond cost-sharing. plan_in_network_terms: citation of
    the plan's in-network cost-sharing for this service (e.g. the SBC row).
    """
    if setting not in SETTINGS:
        raise ValueError(f"setting must be one of {SETTINGS}, not {setting!r}")

    claims: list[dict] = []
    status = NOT_COVERED
    cost_ref: Ref | None = None
    bill_ref: Ref | None = None
    notes: list[str] = []

    if setting == EMERGENCY:
        status = PROTECTED
        claims += [
            rule_claim("nsa.er.prior_auth", "Emergency care must be covered without prior authorization, even out of network.", ER_NO_PRIOR_AUTH),
            rule_claim("nsa.er.network", "Emergency care must be covered whether or not the provider or facility is in network.", ER_ANY_NETWORK),
            rule_claim("nsa.er.cost_sharing", "Your cost-sharing for out-of-network emergency care cannot be more than it would be in network.", ER_COST_SHARING),
            rule_claim(
                "nsa.er.balance_bill",
                "An out-of-network emergency facility or provider must not bill you more than that cost-sharing.",
                ER_FACILITY_NO_BALANCE_BILL,
                ER_PROVIDER_NO_BALANCE_BILL,
            ),
        ]
        cost_ref, bill_ref = ER_COST_SHARING, ER_PROVIDER_NO_BALANCE_BILL
        if consent_signed:
            claims.append(
                rule_claim(
                    "nsa.er.post_stabilization",
                    "Some care after you were stabilized is not protected if you validly agreed in writing to out-of-network billing.",
                    ER_POST_STABILIZATION,
                )
            )
            notes.append("You signed a consent form. Care before you were stabilized is still protected.")

    elif setting == NONEMERGENCY_AT_IN_NETWORK_FACILITY and facility_in_network and not provider_in_network:
        category = "no_in_network_option" if no_in_network_option else ancillary_category(specialty)
        claims.append(
            rule_claim(
                "nsa.facility.covered",
                "Care from an out-of-network provider during a visit to an in-network facility is protected unless the provider met the notice and consent rules.",
                FACILITY_COVERED,
            )
        )
        if category or unforeseen_urgent:
            status = PROTECTED
            refs = [NO_CONSENT_EXCEPTION]
            if category:
                refs.append(ANCILLARY[category])
            if unforeseen_urgent:
                refs.append(UNFORESEEN)
            claims.append(
                rule_claim(
                    "nsa.facility.no_consent_exception",
                    "For this kind of care, signing a consent form does not remove the protection.",
                    *refs,
                )
            )
        elif consent_signed:
            status = MAY_HAVE_WAIVED
            notes.append(
                "You signed a consent form, so this protection may not apply, if the form met the federal notice "
                "and consent rules. Ask the provider for a copy of what you signed."
            )
        else:
            status = PROTECTED_UNLESS_CONSENT
        claims += [
            rule_claim(
                "nsa.facility.cost_sharing",
                "Your cost-sharing for this care cannot be more than it would be with an in-network provider.",
                FACILITY_COST_SHARING,
            ),
            rule_claim(
                "nsa.facility.balance_bill",
                "The out-of-network provider must not bill you more than that cost-sharing.",
                FACILITY_NO_BALANCE_BILL,
            ),
        ]
        cost_ref, bill_ref = FACILITY_COST_SHARING, FACILITY_NO_BALANCE_BILL

    elif setting == AIR_AMBULANCE and not provider_in_network:
        status = PROTECTED
        claims.append(
            rule_claim(
                "nsa.air.cost_sharing",
                "Cost-sharing for an out-of-network air ambulance must be the same as for an in-network one.",
                AIR_COST_SHARING,
            )
        )
        cost_ref = AIR_COST_SHARING

    elif setting == GROUND_AMBULANCE:
        notes.append("Federal surprise-billing rules do not cover ground ambulances. Your state's rules may.")

    flags: list[dict] = []
    if status in (PROTECTED, PROTECTED_UNLESS_CONSENT):
        extra = [plan_in_network_terms] if isinstance(plan_in_network_terms, dict) else []
        unless = " unless you validly consented" if status == PROTECTED_UNLESS_CONSENT else ""
        if isinstance(out_of_network_cost_sharing, dict) and cost_ref:
            flags.append(
                rule_claim(
                    "nsa.flag.cost_sharing",
                    f"This bill applies out-of-network cost-sharing to care that must be charged at in-network cost-sharing{unless}.",
                    out_of_network_cost_sharing,
                    cost_ref,
                    *extra,
                )
            )
        if isinstance(balance_bill, dict) and bill_ref:
            flags.append(
                rule_claim(
                    "nsa.flag.balance_bill",
                    f"The provider is billing you more than your cost-sharing for care where that is not allowed{unless}.",
                    balance_bill,
                    bill_ref,
                    *extra,
                )
            )
    if setting != GROUND_AMBULANCE:
        notes.append("Federal minimums only. Your state may give more protection.")
    return NsaResult(status, tuple(claims), tuple(flags), tuple(notes))


def all_refs() -> list[Ref]:
    return [
        ER_NO_PRIOR_AUTH,
        ER_ANY_NETWORK,
        ER_COST_SHARING,
        ER_FACILITY_NO_BALANCE_BILL,
        ER_PROVIDER_NO_BALANCE_BILL,
        ER_POST_STABILIZATION,
        FACILITY_COVERED,
        FACILITY_COST_SHARING,
        FACILITY_NO_BALANCE_BILL,
        NO_CONSENT_EXCEPTION,
        *ANCILLARY.values(),
        UNFORESEEN,
        AIR_COST_SHARING,
    ]
