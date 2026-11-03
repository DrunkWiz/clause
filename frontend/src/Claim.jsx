import { useState } from "react";
import { ListChecks, PencilSimple, Scales, UserCircle, WarningCircle } from "@phosphor-icons/react";
import { uniqueCitations, whyRejected } from "./text.js";

const TAG = {
  rule: { label: "Federal rule", Icon: Scales },
  finding: { label: "Checked by rule", Icon: ListChecks },
  edited: { label: "Your edit", Icon: UserCircle },
};

const shortLabel = (label) => label.replace(/^(\d+) CFR /, "§ ").replace(/ \(Remittance.*\)/, "");

/**
 * One sentence and its citations. Supported sentences read normally and link
 * to their source; unsupported ones are greyed out with the reason, and are
 * never shown as fact. Editable sentences are re-verified on save.
 */
export default function Claim({ claim, active, onSource, onEdit, editable = false }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(claim.text || "");
  const [busy, setBusy] = useState(false);
  const rejected = claim.supported === false;
  const citations = uniqueCitations(claim.citations);
  const okCitations = citations.filter((c) => c.ok);
  const open = (c) => onSource?.(c || okCitations[0] || citations[0]);
  const tag = TAG[claim.source];

  async function save() {
    setBusy(true);
    try {
      await onEdit(draft.trim());
      setEditing(false);
    } finally {
      setBusy(false);
    }
  }

  if (editing) {
    return (
      <div className="claim editing">
        <textarea value={draft} onChange={(e) => setDraft(e.target.value)} rows={3} autoFocus aria-label="Edit sentence" />
        <div className="row gap wrap">
          <button className="btn small" onClick={save} disabled={busy || !draft.trim()}>
            {busy ? "Checking…" : "Save and re-check"}
          </button>
          <button className="btn small ghost" onClick={() => setEditing(false)} disabled={busy}>
            Cancel
          </button>
          <span className="muted small">Your sentence is checked against the same quotes.</span>
        </div>
      </div>
    );
  }

  return (
    <div className={`claim ${rejected ? "rejected" : ""} ${claim.source} ${active && citations.length ? "active" : ""}`}>
      <span
        className="claim-text"
        role={citations.length ? "button" : undefined}
        tabIndex={citations.length ? 0 : undefined}
        onClick={() => citations.length && open()}
        onKeyDown={(e) => e.key === "Enter" && citations.length && open()}
      >
        {claim.text}
      </span>{" "}
      <span className="claim-meta">
        {citations.map((c, i) => (
          <button key={i} className={`cite ${c.ok ? "" : "bad"}`} onClick={() => open(c)} title={c.quote ? `“${c.quote}”` : c.label}>
            {c.label ? shortLabel(c.label) : i + 1}
          </button>
        ))}
        {tag && (
          <span className={`tag ${claim.source}`} title={tag.label}>
            <tag.Icon size={14} weight="bold" aria-hidden />
            {tag.label}
          </span>
        )}
        {editable && (
          <button className="icon" onClick={() => setEditing(true)} aria-label="Edit this sentence" title="Edit and re-check">
            <PencilSimple size={16} weight="bold" aria-hidden />
          </button>
        )}
      </span>
      {rejected && (
        <p className="why">
          <WarningCircle size={16} weight="fill" aria-hidden />
          <span>Not supported by your documents. {whyRejected(claim)}</span>
        </p>
      )}
    </div>
  );
}
