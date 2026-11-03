// Plain-language explanations of verifier results and rule statuses.

const CITATION_REASONS = {
  unknown_clause: "it points to a passage that isn't in your documents",
  doc_mismatch: "it names the wrong document for that passage",
  quote_not_in_clause: "the quoted words aren't in the passage it cites",
  quote_too_short: "the quote is too short to check",
  empty_quote: "the quote is empty",
  malformed: "the citation is incomplete",
};

export function whyRejected(claim) {
  if (claim.reason === "no_citations") return "It cites nothing in your documents.";
  if (claim.reason === "number_not_in_quote")
    return `It mentions ${claim.missing_numbers.join(", ")}, but the quoted text doesn't.`;
  if (claim.reason === "citation_failed") {
    const bad = claim.citations.find((c) => !c.ok);
    return `One of its citations failed: ${CITATION_REASONS[bad?.reason] || "it could not be checked"}.`;
  }
  return "It could not be checked against your documents.";
}

export const NOTICE_STATUS = {
  present: { label: "Found", tone: "ok" },
  not_found: { label: "Not found", tone: "bad" },
  not_applicable: { label: "Not required here", tone: "muted" },
  check: { label: "Ask the insurer", tone: "muted" },
};

export const CARE = { urgent: "Urgent care", pre_service: "Before care (pre-service)", post_service: "After care (post-service)" };
export const BASIS = {
  medical_necessity: "Medical necessity",
  experimental: "Experimental or investigational",
  missing_information: "Missing information",
  other: "Other reason",
};
export const NSA_STATUS = {
  protected: { label: "Protected by the No Surprises Act", tone: "ok" },
  protected_unless_valid_consent: { label: "Protected unless you signed a valid consent form", tone: "ok" },
  may_have_waived_by_consent: { label: "Protection may not apply: you signed a consent form", tone: "warn" },
  not_covered_by_these_rules: { label: "Not covered by the federal No Surprises rules", tone: "muted" },
};

export function fmtDate(iso) {
  if (!iso) return "";
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric", year: "numeric" });
}

export function daysUntil(iso, today = new Date()) {
  const [y, m, d] = iso.split("-").map(Number);
  const due = new Date(y, m - 1, d);
  const start = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  return Math.round((due - start) / 86400000);
}

export function docLabel(doc, documents) {
  const d = documents?.[doc];
  return d?.title || d?.filename || doc;
}

// "Denial: lumbar MRI, medical necessity (plan provision not named)" ->
// {kind: "Denial", title: "Lumbar MRI, medical necessity", hint: "plan provision not named"}
export function caseParts(full = "") {
  const m = full.match(/^([^:]+):\s*(.*?)(?:\s*\(([^)]*)\))?$/);
  if (!m) return { kind: "", title: full, hint: "" };
  const title = m[2].charAt(0).toUpperCase() + m[2].slice(1);
  return { kind: m[1], title, hint: m[3] || "" };
}

export const PLAN_NAMES = {
  "ambetter-tx": "Ambetter Silver 5000, Texas",
  "kaiser-ga": "Kaiser Permanente Gold HMO, Georgia",
  "fidelis-ny": "Ambetter from Fidelis Care Silver, New York",
};

export function planName(planDocs = []) {
  const id = (planDocs[0] || "").split("-").slice(0, 2).join("-");
  return PLAN_NAMES[id] || id;
}

// Rules sometimes cite the same paragraph twice for one sentence; show it once.
export function uniqueCitations(citations = []) {
  const seen = new Set();
  return citations.filter((c) => {
    const k = c.label || c.clause_id;
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  });
}
