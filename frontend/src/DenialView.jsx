import { useMemo, useState } from "react";
import Claim from "./Claim.jsx";
import { BASIS, CARE, NOTICE_STATUS, daysUntil, fmtDate } from "./text.js";

export default function DenialView({ result, sourceKey, onSource, onEditClaim, onOverride }) {
  return (
    <div className="stack">
      <Facts facts={result.facts} onSource={onSource} onOverride={onOverride} />
      <Deadlines deadlines={result.deadlines} onSource={onSource} sourceKey={sourceKey} />
      <NoticeCheck notice={result.notice} onSource={onSource} sourceKey={sourceKey} />
      <Letter result={result} onSource={onSource} onEditClaim={onEditClaim} sourceKey={sourceKey} />
    </div>
  );
}

function Facts({ facts, onSource, onOverride }) {
  const [editing, setEditing] = useState(false);
  const [vals, setVals] = useState({ notice_date: facts.notice_date.value || "", care: facts.care.value, basis: facts.basis.value });
  const item = (key, label, shown) => {
    const f = facts[key];
    const cit = f.citations?.[0];
    return (
      <div className="fact">
        <span className="fact-label">{label}</span>
        <span className="fact-value">{shown || <em>Not found</em>}</span>
        {f.confirmed && cit ? (
          <button className="chip ok" onClick={() => onSource({ ...cit, ok: true })}>
            From the letter
          </button>
        ) : (
          <span className={`chip ${f.entered ? "" : "warn"}`}>{f.entered ? "Entered by you" : "Please confirm"}</span>
        )}
      </div>
    );
  };
  return (
    <section className="card facts">
      <div className="row between">
        <h3>What the letter says</h3>
        <button className="link small" onClick={() => setEditing((e) => !e)}>
          {editing ? "Close" : "Something wrong? Correct it"}
        </button>
      </div>
      {item("notice_date", "Date of the denial notice", facts.notice_date.value && fmtDate(facts.notice_date.value))}
      {item("care", "Type of claim", CARE[facts.care.value])}
      {item("basis", "Reason for denial", BASIS[facts.basis.value])}
      {editing && (
        <form
          className="override"
          onSubmit={(e) => {
            e.preventDefault();
            onOverride(vals);
            setEditing(false);
          }}
        >
          <label>
            Notice date
            <input type="date" value={vals.notice_date} onChange={(e) => setVals({ ...vals, notice_date: e.target.value })} />
          </label>
          <label>
            Type of claim
            <select value={vals.care} onChange={(e) => setVals({ ...vals, care: e.target.value })}>
              {Object.entries(CARE).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          </label>
          <label>
            Reason
            <select value={vals.basis} onChange={(e) => setVals({ ...vals, basis: e.target.value })}>
              {Object.entries(BASIS).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          </label>
          <button className="btn small">Recalculate</button>
        </form>
      )}
    </section>
  );
}

function Deadlines({ deadlines, onSource, sourceKey }) {
  if (!deadlines.length) {
    return (
      <section className="card">
        <h3>Deadlines</h3>
        <p className="muted">We could not find the date of the denial notice. Add it above to see your deadlines.</p>
      </section>
    );
  }
  const [first, ...rest] = deadlines;
  const left = daysUntil(first.due);
  const tone = left < 0 ? "bad" : left <= 30 ? "warn" : "ok";
  return (
    <section className="card deadline">
      <p className="eyebrow">Your appeal deadline</p>
      <div className="countdown">
        <span className={`days ${tone}`}>{left < 0 ? "Passed" : left}</span>
        {left >= 0 && <span className="days-label">{left === 1 ? "day left" : "days left"}</span>}
      </div>
      <p className="due">
        File your internal appeal by <strong>{fmtDate(first.due)}</strong>.
      </p>
      {first.claims.map((c, i) => (
        <Claim key={i} claim={c} onSource={onSource} active={sourceKey === key(c)} />
      ))}
      {first.notes.map((n, i) => (
        <p key={i} className="note">
          {n}
        </p>
      ))}
      <ol className="timeline">
        {rest.map((d) => (
          <li key={d.id}>
            <p className="tl-title">
              {d.title}
              {d.due && <span className="tl-date"> · by {fmtDate(d.due)}</span>}
            </p>
            {d.claims.map((c, i) => (
              <Claim key={i} claim={c} onSource={onSource} active={sourceKey === key(c)} />
            ))}
            {d.notes.map((n, i) => (
              <p key={i} className="note">
                {n}
              </p>
            ))}
          </li>
        ))}
      </ol>
    </section>
  );
}

function NoticeCheck({ notice, onSource, sourceKey }) {
  const order = { not_found: 0, present: 1, check: 2, not_applicable: 3 };
  const items = [...notice.elements].sort((a, b) => order[a.status] - order[b.status]);
  const missing = notice.not_found.length;
  return (
    <section className="card">
      <div className="row between">
        <h3>Is the denial notice complete?</h3>
        <span className={`chip ${missing ? "bad" : "ok"}`}>{missing ? `${missing} missing` : "Nothing missing"}</span>
      </div>
      <p className="muted small">Federal rules say what a denial notice must include. Something counts as found only when we can quote it from your letter.</p>
      <ul className="checklist">
        {items.map((e) => {
          const s = NOTICE_STATUS[e.status];
          const ev = e.evidence[0]?.citations.find((c) => c.ok);
          return (
            <li key={e.id} className={e.status}>
              <span className={`dot ${s.tone}`} aria-hidden />
              <span className="ck-title">{e.title}</span>
              <span className={`chip ${s.tone}`}>{s.label}</span>
              <span className="ck-actions">
                {ev && (
                  <button className="link small" onClick={() => onSource(ev)}>
                    See it
                  </button>
                )}
                <button className="link small" onClick={() => onSource(e.requirement.citations[0])}>
                  The rule
                </button>
              </span>
            </li>
          );
        })}
      </ul>
      {notice.exhaustion && (
        <div className="callout">
          <Claim claim={notice.exhaustion} onSource={onSource} active={sourceKey === key(notice.exhaustion)} />
        </div>
      )}
    </section>
  );
}

const key = (c) => {
  const x = c.citations?.[0];
  return x ? `${x.clause_id}|${x.quote}` : "";
};

function Letter({ result, onSource, onEditClaim, sourceKey }) {
  const [copied, setCopied] = useState(false);
  const text = useMemo(() => letterText(result), [result]);
  // Counted from the sentences as they are now, including your edits.
  const drafted = result.letter.sections.flatMap((s) => s.claims).filter((c) => c.source === "model" || c.source === "edited");
  const stats = {
    model_claims: drafted.length,
    supported: drafted.filter((c) => c.supported).length,
    rejected: drafted.filter((c) => c.supported === false).length,
  };
  return (
    <section className="card letter-card">
      <div className="row between wrap">
        <h3>Your appeal, drafted</h3>
        <div className="row gap">
          <button
            className="btn small"
            onClick={() => navigator.clipboard?.writeText(text).then(() => {
              setCopied(true);
              setTimeout(() => setCopied(false), 1800);
            })}
          >
            {copied ? "Copied" : "Copy letter"}
          </button>
          <a className="btn small ghost" href={`data:text/plain;charset=utf-8,${encodeURIComponent(text)}`} download="appeal-draft.txt">
            Download
          </a>
        </div>
      </div>
      <p className="muted small">
        Every sentence cites your letter, your plan or a federal rule, and was checked word for word. Click one to see its
        source. Sentences that failed the check are greyed out and left out of the copy. You send the letter; Clause never
        contacts your insurer.
      </p>
      <article className="paper">
        <p className="salutation">To the Appeals Unit:</p>
        <p>I am requesting an internal appeal of the denial described below.</p>
        {result.letter.sections.map((s) =>
          s.claims.length ? (
            <div key={s.id} className="letter-section">
              <h4>{s.title}</h4>
              {s.claims.map((c, i) => (
                <Claim
                  key={i}
                  claim={c}
                  onSource={onSource}
                  active={sourceKey === key(c)}
                  editable={c.source === "model" || c.source === "edited"}
                  onEdit={(t) => onEditClaim(s.id, i, t)}
                />
              ))}
            </div>
          ) : null,
        )}
        <p>Please send me your decision in writing.</p>
        <p className="signoff">Sincerely,</p>
      </article>
      <div className="enclose">
        <h4>Send with your appeal</h4>
        <ul>
          {result.enclosures.map((e) => (
            <li key={e}>{e}</li>
          ))}
        </ul>
      </div>
      <p className="stats small muted">
        {stats.model_claims} sentences drafted · {stats.supported} supported · {stats.rejected} rejected by the verifier
      </p>
    </section>
  );
}

export function letterText(result) {
  const lines = ["To the Appeals Unit:", "", "I am requesting an internal appeal of the denial described below.", ""];
  for (const s of result.letter.sections) {
    const ok = s.claims.filter((c) => c.supported !== false);
    if (!ok.length) continue;
    lines.push(s.title.toUpperCase());
    ok.forEach((c) => lines.push(c.text));
    lines.push("");
  }
  lines.push("Please send me your decision in writing.", "", "Sincerely,", "", "", "Enclosures:");
  result.enclosures.forEach((e) => lines.push(`- ${e}`));
  return lines.join("\n");
}
