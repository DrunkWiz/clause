import { useState } from "react";
import { whyRejected } from "./text.js";

const TAG = { rule: "Federal rule", finding: "Checked by rule", edited: "Your edit" };

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
  const okCitations = claim.citations.filter((c) => c.ok);
  const open = (c) => onSource?.(c || okCitations[0] || claim.citations[0]);

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
        <div className="row gap">
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
    <div className={`claim ${rejected ? "rejected" : ""} ${claim.source} ${active ? "active" : ""}`}>
      <span
        className="claim-text"
        role={claim.citations.length ? "button" : undefined}
        tabIndex={claim.citations.length ? 0 : undefined}
        onClick={() => claim.citations.length && open()}
        onKeyDown={(e) => e.key === "Enter" && claim.citations.length && open()}
      >
        {claim.text}
      </span>
      {claim.citations.map((c, i) => (
        <button key={i} className={`cite ${c.ok ? "" : "bad"}`} onClick={() => open(c)} title={c.label || c.quote}>
          {c.label ? c.label.replace(/^(\d+) CFR /, "§ ").replace(/ \(Remittance.*\)/, "") : i + 1}
        </button>
      ))}
      {TAG[claim.source] && <span className={`tag ${claim.source}`}>{TAG[claim.source]}</span>}
      {editable && (
        <button className="icon" onClick={() => setEditing(true)} aria-label="Edit this sentence" title="Edit and re-check">
          ✎
        </button>
      )}
      {rejected && <p className="why">Not supported by your documents. {whyRejected(claim)}</p>}
    </div>
  );
}
