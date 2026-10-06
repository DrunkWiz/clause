"""Appeal deadlines for individual-market (marketplace) plans.

Federal minimums only; state law can be stricter. Every figure is quoted from
the regulation text in data/regs (fetched 2026-10-01), and every output claim
cites it, so the grounding verifier checks the rule's own sources.

Dates are calendar dates. The regulations count from *receipt* of a notice;
we count from the date the person gives us (normally the letter date), which
can only be the same as or earlier than receipt, so our dates are never later
than the real ones.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, timedelta

from clause.rules.base import Ref, rule_claim

URGENT = "urgent"
PRE_SERVICE = "pre_service"
POST_SERVICE = "post_service"
CARE_TYPES = (URGENT, PRE_SERVICE, POST_SERVICE)

# ---------------------------------------------------------------- rule table

INTERNAL_APPEAL_DAYS = 180
INTERNAL_APPEAL = (
    Ref(
        "29 CFR 2560.503-1(h)(3)(i)",
        "Provide claimants at least 180 days following receipt of a notification of an adverse benefit "
        "determination within which to appeal the determination",
    ),
    # Applies 2560.503-1 to individual-market issuers.
    Ref("45 CFR 147.136(b)(3)(i)", "the issuer is subject to the requirements in 29 CFR 2560.503-1 as if the issuer were a group health plan"),
)

ONE_LEVEL = Ref(
    "45 CFR 147.136(b)(3)(ii)(G)",
    "must provide for only one level of internal appeal before issuing a final determination",
)

# Insurer's decision on the internal appeal (one level of appeal).
DECISION_DAYS = {URGENT: 3, PRE_SERVICE: 30, POST_SERVICE: 60}  # urgent: 72 hours, shown as 3 days on a calendar
DECISION_WORDS = {URGENT: "72 hours", PRE_SERVICE: "30 days", POST_SERVICE: "60 days"}
DECISION = {
    URGENT: Ref(
        "29 CFR 2560.503-1(i)(2)(i)",
        "but not later than 72 hours after receipt of the claimant's request for review of an adverse benefit "
        "determination by the plan",
    ),
    PRE_SERVICE: Ref(
        "29 CFR 2560.503-1(i)(2)(ii)",
        "In the case of a group health plan that provides for one appeal of an adverse benefit determination, such "
        "notification shall be provided not later than 30 days after receipt by the plan of the claimant's request "
        "for review of an adverse benefit determination",
    ),
    POST_SERVICE: Ref(
        "29 CFR 2560.503-1(i)(2)(iii)(A)",
        "In the case of a group health plan that provides for one appeal of an adverse benefit determination, such "
        "notification shall be provided not later than 60 days after receipt by the plan of the claimant's request "
        "for review of an adverse benefit determination",
    ),
}

EXTERNAL_MONTHS = 4
EXTERNAL_FILING = (
    Ref(
        "45 CFR 147.136(d)(2)(i)",
        "the request is filed within four months after the date of receipt of a notice of an adverse benefit "
        "determination or final internal adverse benefit determination",
    ),
    Ref(
        "45 CFR 147.136(d)(2)(i)",
        "If there is no corresponding date four months after the date of receipt of such a notice, then the request "
        "must be filed by the first day of the fifth month following the receipt of the notice",
    ),
)
WEEKEND_HOLIDAY = Ref(
    "45 CFR 147.136(d)(2)(i)",
    "If the last filing date would fall on a Saturday, Sunday, or Federal holiday, the last filing date is extended "
    "to the next day that is not a Saturday, Sunday, or Federal holiday",
)
STATE_EXTERNAL_MINIMUM = Ref(
    "45 CFR 147.136(c)(2)(vi)",
    "The State process must allow at least four months after the receipt of a notice of an adverse benefit "
    "determination or final internal adverse benefit determination for a request for an external review to be filed",
)

EXTERNAL_DECISION = {
    "standard": Ref(
        "45 CFR 147.136(d)(2)(iii)(B)(6)",
        "The assigned IRO must provide written notice of the final external review decision within 45 days after "
        "the IRO receives the request for the external review",
    ),
    "expedited": Ref(
        "45 CFR 147.136(d)(3)(iv)",
        "but in no event more than 72 hours after the IRO receives the request for an expedited external review",
    ),
}

# Legal public holidays, 5 U.S.C. 6103(a). The Friday/Monday "observed" rules
# in 6103(b) apply "for the purpose of statutes relating to pay and leave of
# employees", so they are not used here: a holiday is the date in (a).
HOLIDAYS = {
    "new_year": Ref("5 U.S.C. 6103(a)", "New Year's Day, January 1."),
    "mlk": Ref("5 U.S.C. 6103(a)", "Birthday of Martin Luther King, Jr., the third Monday in January."),
    "washington": Ref("5 U.S.C. 6103(a)", "Washington's Birthday, the third Monday in February."),
    "memorial": Ref("5 U.S.C. 6103(a)", "Memorial Day, the last Monday in May."),
    "juneteenth": Ref("5 U.S.C. 6103(a)", "Juneteenth National Independence Day, June 19."),
    "independence": Ref("5 U.S.C. 6103(a)", "Independence Day, July 4."),
    "labor": Ref("5 U.S.C. 6103(a)", "Labor Day, the first Monday in September."),
    "columbus": Ref("5 U.S.C. 6103(a)", "Columbus Day, the second Monday in October."),
    "veterans": Ref("5 U.S.C. 6103(a)", "Veterans Day, November 11."),
    "thanksgiving": Ref("5 U.S.C. 6103(a)", "Thanksgiving Day, the fourth Thursday in November."),
    "christmas": Ref("5 U.S.C. 6103(a)", "Christmas Day, December 25."),
}
OBSERVED_RULES_SCOPE = Ref("5 U.S.C. 6103(b)", "For the purpose of statutes relating to pay and leave of employees")

# ------------------------------------------------------------- date helpers


def add_months_rule(d: date, months: int) -> date:
    """Same day `months` later; if that day does not exist, the first day of
    the following month (147.136(d)(2)(i): Oct 30 -> Mar 1)."""
    y, m = divmod(d.month - 1 + months, 12)
    year, month = d.year + y, m + 1
    if d.day <= calendar.monthrange(year, month)[1]:
        return date(year, month, d.day)
    y2, m2 = divmod(month, 12)
    return date(year + y2, m2 + 1, 1)


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    first = date(year, month, 1)
    return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    last = date(year, month, calendar.monthrange(year, month)[1])
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def federal_holidays(year: int) -> dict[date, str]:
    """5 U.S.C. 6103(a) for one year, as {date: key in HOLIDAYS}."""
    mon, thu = 0, 3
    days = {
        date(year, 1, 1): "new_year",
        _nth_weekday(year, 1, mon, 3): "mlk",
        _nth_weekday(year, 2, mon, 3): "washington",
        _last_weekday(year, 5, mon): "memorial",
        date(year, 6, 19): "juneteenth",
        date(year, 7, 4): "independence",
        _nth_weekday(year, 9, mon, 1): "labor",
        _nth_weekday(year, 10, mon, 2): "columbus",
        date(year, 11, 11): "veterans",
        _nth_weekday(year, 11, thu, 4): "thanksgiving",
        date(year, 12, 25): "christmas",
    }
    return days


def next_filing_day(d: date) -> tuple[date, list[str]]:
    """Roll forward past Saturdays, Sundays and federal holidays. Returns the
    day and the reasons for each day skipped ("saturday", "sunday" or a
    holiday key)."""
    skipped: list[str] = []
    while True:
        holiday = federal_holidays(d.year).get(d)
        if d.weekday() == 5:
            skipped.append("saturday")
        elif d.weekday() == 6:
            skipped.append("sunday")
        elif holiday:
            skipped.append(holiday)
        else:
            return d, skipped
        d += timedelta(days=1)


def fmt(d: date) -> str:
    return f"{d:%A}, {d:%B} {d.day}, {d.year}"


# ------------------------------------------------------------------ output


@dataclass(frozen=True)
class Deadline:
    id: str
    title: str
    due: date | None  # None when it depends on a date we do not have yet
    claims: tuple[dict, ...]  # rule claims, each citing regulation text
    unextended: date | None = None  # set when a weekend or holiday moved `due`
    notes: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "due": self.due.isoformat() if self.due else None,
            "unextended": self.unextended.isoformat() if self.unextended else None,
            "claims": list(self.claims),
            "notes": list(self.notes),
        }


COUNT_FROM_LETTER = (
    "Counted from the date you gave us. The rules count from when you received the notice, which can only be "
    "later, so the real deadline is never earlier than this one. Confirm dates with your insurer."
)


def appeal_deadlines(
    notice_received: date,
    care: str,
    appeal_received: date | None = None,
    final_denial_received: date | None = None,
) -> list[Deadline]:
    """Deadlines for an individual-market denial.

    notice_received: date of the denial notice (normally the letter date)
    care: URGENT, PRE_SERVICE or POST_SERVICE
    appeal_received: when the insurer received the internal appeal, if filed
    final_denial_received: date of the final internal denial, if there is one
    """
    if care not in CARE_TYPES:
        raise ValueError(f"care must be one of {CARE_TYPES}, not {care!r}")

    out: list[Deadline] = []

    # 1. Filing the internal appeal.
    due = notice_received + timedelta(days=INTERNAL_APPEAL_DAYS)
    out.append(
        Deadline(
            id="internal_appeal_filing",
            title="File your internal appeal",
            due=due,
            claims=(
                rule_claim(
                    "internal_appeal_filing",
                    # The number comes from the constant, so changing it without
                    # the regulation quote makes the verifier reject the claim.
                    f"You have at least {INTERNAL_APPEAL_DAYS} days after receiving the denial to file an internal appeal. "
                    f"Counting from {fmt(notice_received)}, file by {fmt(due)}.",
                    *INTERNAL_APPEAL,
                ),
            ),
            notes=(COUNT_FROM_LETTER,)
            + ((f"{fmt(due)} is a weekend or federal holiday. This rule has no extension for that, so file before it.",)
               if next_filing_day(due)[1] else ()),
        )
    )

    # 2. The insurer's decision on that appeal.
    words = DECISION_WORDS[care]
    decision_due = appeal_received + timedelta(days=DECISION_DAYS[care]) if appeal_received else None
    when = (
        f"Your appeal reached the insurer on {fmt(appeal_received)}, so the decision is due by {fmt(decision_due)}."
        if appeal_received
        else "The clock starts when the insurer receives your appeal."
    )
    kind = {URGENT: "an urgent care", PRE_SERVICE: "a pre-service", POST_SERVICE: "a post-service"}[care]
    out.append(
        Deadline(
            id="internal_appeal_decision",
            title="Insurer decides your appeal",
            due=decision_due,
            claims=(
                rule_claim(
                    "internal_appeal_decision",
                    f"For {kind} claim, the insurer must decide your appeal within {words} of receiving it. {when}",
                    DECISION[care],
                ),
                rule_claim(
                    "one_level",
                    "Marketplace and other individual plans have only one level of internal appeal, so this decision "
                    "is final and the next step is external review.",
                    ONE_LEVEL,
                ),
            ),
        )
    )

    # 3. Requesting external review.
    if final_denial_received:
        raw_due = add_months_rule(final_denial_received, EXTERNAL_MONTHS)
        ext_due, skipped = next_filing_day(raw_due)
        refs = [*EXTERNAL_FILING]
        text = (
            f"You can request an external review within four months after receiving the final denial. "
            f"Counting from {fmt(final_denial_received)}, the last day is {fmt(ext_due)}."
        )
        if skipped:
            refs.append(WEEKEND_HOLIDAY)
            refs.extend(HOLIDAYS[s] for s in skipped if s in HOLIDAYS)
            text += f" Four months lands on {fmt(raw_due)}, which is a weekend or federal holiday, so it moves to the next working day."
        claims = [rule_claim("external_review_filing", text, *refs)]
        unextended = raw_due if skipped else None
    else:
        ext_due, unextended = None, None
        claims = [
            rule_claim(
                "external_review_filing",
                "If your internal appeal is denied, you can request an external review within four months after "
                "receiving that final denial.",
                EXTERNAL_FILING[0],
            )
        ]
    claims.append(
        rule_claim(
            "external_review_state_minimum",
            "If your state runs the external review, it must still allow at least four months to ask for it.",
            STATE_EXTERNAL_MINIMUM,
        )
    )
    notes = [COUNT_FROM_LETTER] if final_denial_received else []
    if unextended:
        notes.append(f"To be safe, file by {fmt(unextended)}, before the weekend or holiday.")
    out.append(
        Deadline(
            id="external_review_filing",
            title="Request an external review",
            due=ext_due,
            claims=tuple(claims),
            unextended=unextended,
            notes=tuple(notes),
        )
    )

    # 4. The external reviewer's decision.
    expedited = care == URGENT
    out.append(
        Deadline(
            id="external_review_decision",
            title="Independent reviewer decides",
            due=None,
            claims=(
                rule_claim(
                    "external_review_decision",
                    "For urgent care, an expedited external review must be decided within 72 hours after the "
                    "reviewer receives the request."
                    if expedited
                    else "The independent reviewer must decide within 45 days after receiving the request.",
                    EXTERNAL_DECISION["expedited" if expedited else "standard"],
                ),
            ),
        )
    )
    return out


def all_refs() -> list[Ref]:
    """Every regulation reference this rule can cite, for the table tests."""
    return [
        *INTERNAL_APPEAL,
        ONE_LEVEL,
        *DECISION.values(),
        *EXTERNAL_FILING,
        WEEKEND_HOLIDAY,
        STATE_EXTERNAL_MINIMUM,
        *EXTERNAL_DECISION.values(),
        *HOLIDAYS.values(),
        OBSERVED_RULES_SCOPE,
    ]
