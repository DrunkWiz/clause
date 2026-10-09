"""One case, end to end: extract -> rules -> retrieve -> draft -> verify.

The model locates facts and drafts claims. Code reads dates out of verified
quotes, runs the rules, and verifies every claim before anything is shown.
Unsupported claims are kept, marked, and never presented as fact.
"""

from __future__ import annotations

import re
from datetime import date

from clause.index.model import Clause, ClauseIndex
from clause.model.providers import Chain, ChainResult
from clause.pipeline import prompts
from clause.pipeline.retrieve import select
from clause.rules import deadlines as dl
from clause.rules import no_surprises as nsa
from clause.rules import notice as nt
from clause.rules import reason_codes as rc
from clause.rules.base import regs
from clause.verify.verifier import ClaimResult, verify_claim

MONTHS = "January February March April May June July August September October November December".split()
_DATE_LONG = re.compile(r"\b(" + "|".join(MONTHS) + r")\s+(\d{1,2}),\s*(\d{4})\b")
_DATE_NUM = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")

BASIS_QUERIES = {
    nt.MEDICAL_NECESSITY: "medically necessary means definition accepted standards of medicine",
    nt.EXPERIMENTAL: "experimental investigational treatment exclusion clinical trial",
    nt.MISSING_INFORMATION: "claim information proof of loss submit records",
    nt.OTHER: "prior authorization required services covered",
}
APPEAL_QUERY = "internal appeal adverse determination external review independent review organization complaint"

# What to send with the appeal. Fixed text chosen by code from the denial
# basis: the drafted letter makes arguments, and these are the evidence the
# person has to supply for them. Not legal advice; a checklist.
ENCLOSURES = {
    nt.MEDICAL_NECESSITY: (
        "A letter from your doctor explaining why this care was medically necessary for you",
        "Medical records that support it, such as visit notes and test results",
    ),
    nt.EXPERIMENTAL: (
        "A letter from your doctor explaining why this treatment is right for you, citing any studies they rely on",
        "Medical records showing other treatments you have tried, if any",
    ),
    nt.MISSING_INFORMATION: ("The information the denial notice says is missing",),
    nt.OTHER: ("Any records that support your request, such as proof that prior authorization was requested",),
}
ALWAYS_ENCLOSE = ("A copy of the denial notice", "Your member ID card (front and back)")


_BARE_ID = re.compile(r"^p\d+\.\d+$")


def canonical_citations(obj):
    """Models sometimes split "doc#p26.6" into doc "doc" and clause_id
    "p26.6". Join them back, in place, before verifying. Only this exact,
    unambiguous shape is rewritten; the quote is still checked against the
    clause as usual."""
    if isinstance(obj, dict):
        cits = obj.get("citations")
        if isinstance(cits, list):
            for c in cits:
                if isinstance(c, dict) and isinstance(c.get("doc"), str) and isinstance(c.get("clause_id"), str):
                    if _BARE_ID.match(c["clause_id"]):
                        c["clause_id"] = f"{c['doc']}#{c['clause_id']}"
        for v in obj.values():
            canonical_citations(v)
    elif isinstance(obj, list):
        for v in obj:
            canonical_citations(v)
    return obj


def parse_date(text: str) -> date | None:
    m = _DATE_LONG.search(text)
    try:
        if m:
            return date(int(m.group(3)), MONTHS.index(m.group(1)) + 1, int(m.group(2)))
        m = _DATE_NUM.search(text)
        if m:
            return date(int(m.group(3)), int(m.group(1)), int(m.group(2)))
    except ValueError:
        return None
    return None


# ------------------------------------------------------------------ views


def claim_view(claim: dict, result: ClaimResult, index: ClauseIndex, source: str) -> dict:
    cits = []
    for c in result.citations:
        clause = index.get(c.clause_id) if isinstance(c.clause_id, str) else None
        cits.append(
            {
                "doc": c.doc,
                "clause_id": c.clause_id,
                "quote": c.quote,
                "ok": c.ok,
                "reason": c.reason,
                "page": clause.page if clause else None,
                "label": clause.label if clause else "",
                "spans": [list(s) for s in c.spans],
                "highlights": [{"page": h.page, "bbox": list(h.bbox)} for h in c.highlights],
            }
        )
    return {
        "text": claim.get("text") if isinstance(claim, dict) else None,
        "supported": result.supported,
        "reason": result.reason,
        "missing_numbers": list(result.missing_numbers),
        "source": source,
        "rule_id": claim.get("rule_id") if isinstance(claim, dict) else None,
        "citations": cits,
    }


def check(claim: dict, index: ClauseIndex, source: str) -> dict:
    return claim_view(claim, verify_claim(claim, index), index, source)


def finding(text: str, rule_id: str) -> dict:
    """A statement made by a rule about something it did NOT find. There is
    nothing to quote for an absence, so it has no citations and is labelled
    as a rule finding rather than a supported claim."""
    return {"text": text, "supported": None, "reason": None, "missing_numbers": [], "source": "finding", "rule_id": rule_id, "citations": []}


def cited_clauses(views: list[dict], index: ClauseIndex) -> dict:
    out = {}
    for v in views:
        for c in v.get("citations", []):
            clause = index.get(c["clause_id"]) if isinstance(c.get("clause_id"), str) else None
            if clause and clause.clause_id not in out:
                out[clause.clause_id] = {"doc": clause.doc_id, "page": clause.page, "label": clause.label, "text": clause.text}
    return out


def file_url(doc_id: str, filename: str, has_pages: bool, is_reg_source: bool) -> str | None:
    """Where the browser can fetch the original PDF. Uploads stay in the
    browser, so they have none; regulation text has no PDF."""
    if not has_pages or doc_id.startswith("upload-"):
        return None
    if is_reg_source:
        return f"/files/regs/{filename}"
    return f"/files/{'synthetic' if doc_id.startswith('synthetic-') else 'plans'}/{filename}"


def documents_view(index: ClauseIndex) -> dict:
    reg_docs = set(regs().documents)
    return {
        d.doc_id: {
            "title": d.title or d.filename,
            "filename": d.filename,
            "pages": len(d.page_sizes),
            "page_sizes": [list(s) for s in d.page_sizes],
            "source_url": d.source_url,
            "regulation": not d.page_sizes,
            "kind": "rule" if d.doc_id in reg_docs else "synthetic" if d.doc_id.startswith("synthetic-") else "upload" if d.doc_id.startswith("upload-") else "plan",
            "file_url": file_url(d.doc_id, d.filename, bool(d.page_sizes), d.doc_id in reg_docs),
        }
        for d in index.documents.values()
    }


def _attempts(r: ChainResult | None) -> list[dict]:
    return [{"provider": a.provider, "ok": a.ok, "error": a.error, "seconds": round(a.seconds, 2)} for a in (r.attempts if r else [])]


# -------------------------------------------------------------- extraction


def _verified_fact(fact: dict, index: ClauseIndex) -> tuple[bool, ClaimResult | None]:
    cits = fact.get("citations")
    if not isinstance(cits, list) or not cits:
        return False, None
    r = verify_claim({"text": str(fact.get("field", "fact")), "citations": cits}, index)
    return r.supported, r


def read_denial_facts(data: dict, letter: ClauseIndex, overrides: dict) -> dict:
    """Facts the rules need, each with whether it was confirmed by a verified
    quote. Overrides (entered by the person) win."""
    facts = {f.get("field"): f for f in data.get("facts", []) if isinstance(f, dict)}
    out: dict[str, dict] = {}

    nd, nd_cits = None, []
    f = facts.get("notice_date")
    if f:
        ok, r = _verified_fact(f, letter)
        if ok:
            for c in f["citations"]:
                nd = nd or parse_date(str(c.get("quote", "")))
            nd_cits = f["citations"]
    if overrides.get("notice_date"):
        out["notice_date"] = {"value": overrides["notice_date"], "confirmed": False, "entered": True, "citations": []}
    else:
        out["notice_date"] = {"value": nd.isoformat() if nd else None, "confirmed": nd is not None, "entered": False, "citations": nd_cits}

    for field_name, allowed, default in (("care", dl.CARE_TYPES, dl.POST_SERVICE), ("basis", nt.BASES, nt.OTHER)):
        f = facts.get(field_name)
        value, confirmed, cits = default, False, []
        if f and f.get("value") in allowed:
            ok, _ = _verified_fact(f, letter)
            if ok:
                value, confirmed, cits = f["value"], True, f["citations"]
        if overrides.get(field_name) in allowed:
            value, confirmed, cits = overrides[field_name], False, []
            out[field_name] = {"value": value, "confirmed": False, "entered": True, "citations": []}
        else:
            out[field_name] = {"value": value, "confirmed": confirmed, "entered": False, "citations": cits}

    for field_name in ("service", "reason"):
        f = facts.get(field_name)
        ok = bool(f) and _verified_fact(f, letter)[0]
        out[field_name] = {"value": f.get("value") if ok else None, "confirmed": ok, "citations": f["citations"] if ok else []}
    return out


def notice_findings(data: dict) -> list[dict]:
    titles = {e.id: e.title for e in nt.ELEMENTS}
    out = []
    for e in data.get("elements", []):
        if isinstance(e, dict) and e.get("element") in titles:
            out.append({"element": e["element"], "text": f"The letter includes: {titles[e['element']].lower()}.", "citations": e.get("citations")})
    return out


# ------------------------------------------------------------------ denial


def run_denial(
    letter: ClauseIndex,
    plan: ClauseIndex,
    chain: Chain,
    overrides: dict | None = None,
    plan_limit: int = 40,
) -> dict:
    overrides = overrides or {}
    letter_clauses = list(letter.clauses.values())
    index = letter.merge(plan).merge(regs())

    # 1. Locate facts and notice elements in the letter.
    ext = chain.run("denial_extract", prompts.DENIAL_SYSTEM, prompts.denial_user(letter_clauses), prompts.validate_denial)
    canonical_citations(ext.data)
    facts = read_denial_facts(ext.data, letter, overrides)
    for f in facts.values():  # verified citation views, with page and highlight boxes
        if f["citations"]:
            f["citations"] = check({"text": "fact", "citations": f["citations"]}, index, "model")["citations"]

    # 2. Rules.
    deadlines = []
    nd = facts["notice_date"]["value"]
    care, basis = facts["care"]["value"], facts["basis"]["value"]
    if nd:
        for d in dl.appeal_deadlines(date.fromisoformat(nd), care):
            dd = d.to_dict()
            dd["claims"] = [check(c, index, "rule") for c in d.claims]
            deadlines.append(dd)
    report = nt.check_notice(notice_findings(ext.data), letter, care=care, basis=basis)
    notice_view = {
        "elements": [
            {
                "id": e.element.id,
                "title": e.element.title,
                "status": e.status,
                "requirement": check(e.requirement, index, "rule"),
                "evidence": [claim_view({"text": ev.text}, ev, index, "model") for ev in e.evidence],
            }
            for e in report.elements
        ],
        "not_found": [e.element.id for e in report.not_found],
        "exhaustion": check(report.exhaustion, index, "rule") if report.exhaustion else None,
    }

    # 3. Pick plan clauses and draft.
    plan_clauses = list(plan.clauses.values())
    q_case = " ".join(str(facts[k]["value"] or "") for k in ("service", "reason"))
    q_provision = " ".join(c.text for c in letter_clauses if "plan" in c.text.lower() and "based on" in c.text.lower())
    queries = [q for q in (q_case, BASIS_QUERIES[basis], APPEAL_QUERY, q_provision) if q.strip()]
    selected = select(plan_clauses, queries, k_each=14, limit=plan_limit)
    shown = {
        "service": facts["service"]["value"],
        "reason": facts["reason"]["value"],
        "care": care,
        "basis": basis,
    }
    draft = chain.run("draft_appeal", prompts.DRAFT_SYSTEM, prompts.draft_user(letter_clauses, selected, shown), prompts.validate_draft)
    canonical_citations(draft.data)

    by_id = {s.get("id"): s for s in draft.data["sections"] if isinstance(s, dict)}
    sections = []
    for sid, title in prompts.SECTIONS:
        claims = [check(c, index, "model") for c in by_id.get(sid, {}).get("claims", []) if isinstance(c, dict)]
        sections.append({"id": sid, "title": title, "claims": claims})

    # 4. Procedural points from the notice rule, before the request.
    procedure = []
    for e in report.not_found:
        procedure.append(check(e.requirement, index, "rule"))
        procedure.append(finding(f"The denial notice I received does not include {e.element.title.lower()}.", f"notice.{e.element.id}"))
    if report.exhaustion:
        procedure.append(check(report.exhaustion, index, "rule"))
    if procedure:
        sections.insert(len(sections) - 1, {"id": "procedure", "title": "Problems with the denial notice", "claims": procedure})

    model_claims = [c for s in sections for c in s["claims"] if c["source"] == "model"]
    rejected = [c for c in model_claims if not c["supported"]]
    all_views = (
        [c for s in sections for c in s["claims"]]
        + [c for d in deadlines for c in d["claims"]]
        + [e["requirement"] for e in notice_view["elements"]]
        + [v for e in notice_view["elements"] for v in e["evidence"]]
        + ([notice_view["exhaustion"]] if notice_view["exhaustion"] else [])
    )
    return {
        "kind": "denial",
        "facts": facts,
        "deadlines": deadlines,
        "notice": notice_view,
        "letter": {"sections": sections},
        "enclosures": [*ENCLOSURES[basis], *ALWAYS_ENCLOSE],
        "plan_clauses_shown": [c.clause_id for c in selected],
        "stats": {
            "model_claims": len(model_claims),
            "supported": len(model_claims) - len(rejected),
            "rejected": len(rejected),
            "rejection_rate": round(len(rejected) / len(model_claims), 3) if model_claims else 0.0,
        },
        "providers": {"extract": _attempts(ext), "draft": _attempts(draft)},
        "answered_by": {"extract": ext.provider, "draft": draft.provider},
        "documents": documents_view(index),
        "clauses": cited_clauses(all_views, index),
    }


# --------------------------------------------------------------------- EOB


def _first_verified(obj, index: ClauseIndex) -> dict | None:
    """The object's first citation, if its citations verify."""
    if not isinstance(obj, dict) or not isinstance(obj.get("citations"), list) or not obj["citations"]:
        return None
    r = verify_claim({"text": "fact", "citations": obj["citations"]}, index)
    return dict(obj["citations"][0]) if r.supported else None


def run_eob(eob: ClauseIndex, plan: ClauseIndex, chain: Chain) -> dict:
    index = eob.merge(plan).merge(regs())
    ext = chain.run("eob_extract", prompts.EOB_SYSTEM, prompts.eob_user(list(eob.clauses.values())), prompts.validate_eob)
    d = canonical_citations(ext.data)

    lines = []
    for l in d.get("lines", []):
        cit = _first_verified(l, eob)
        if cit and isinstance(l, dict):
            lines.append({"group": l.get("group"), "code": l.get("code"), "amount": l.get("amount"), "citation": cit})
    owes = d.get("patient_owes")
    owes_cit = _first_verified(owes, eob)
    patient_owes = {"amount": owes.get("amount"), "citation": owes_cit} if owes_cit else None

    def value(key, allowed=None):
        obj = d.get(key)
        cit = _first_verified(obj, eob)
        v = obj.get("value") if cit else None
        return v if (allowed is None or v in allowed) else None

    setting = value("setting", nsa.SETTINGS) or nsa.OTHER
    provider_in = value("provider_in_network", (True, False))
    facility_in = value("facility_in_network", (True, False))
    specialty = value("specialty")
    nsa_result = nsa.check_bill(
        setting,
        bool(provider_in),
        facility_in_network=facility_in,
        specialty=specialty if isinstance(specialty, str) else None,
        out_of_network_cost_sharing=_first_verified(d.get("out_of_network_cost_sharing"), eob),
        balance_bill=_first_verified(d.get("balance_bill"), eob),
    ) if provider_in is not None else None

    explained = []
    for l in lines:
        e = rc.explain(l)
        ev = e.to_dict()
        ev["claims"] = [check(c, index, "rule") for c in e.claims]
        ev["amount"] = l["amount"]
        ev["line"] = check({"text": f"{e.group}-{e.code}", "citations": [l["citation"]]}, index, "model")
        explained.append(ev)
    share = [check(c, index, "rule") for c in rc.check_patient_share(lines, patient_owes)]
    nsa_view = None
    if nsa_result:
        nsa_view = {
            "status": nsa_result.status,
            "claims": [check(c, index, "rule") for c in nsa_result.claims],
            "flags": [check(c, index, "rule") for c in nsa_result.flags],
            "notes": list(nsa_result.notes),
        }
    views = [c for e in explained for c in e["claims"] + [e["line"]]] + share
    if nsa_view:
        views += nsa_view["claims"] + nsa_view["flags"]
    return {
        "kind": "eob",
        "facts": {"setting": setting, "provider_in_network": provider_in, "facility_in_network": facility_in, "specialty": specialty},
        "lines": explained,
        "patient_share": share,
        "no_surprises": nsa_view,
        "basis": rc.denial_basis(lines),
        "providers": {"extract": _attempts(ext)},
        "answered_by": {"extract": ext.provider},
        "documents": documents_view(index),
        "clauses": cited_clauses(views, index),
    }
