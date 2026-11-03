import { useMemo, useState } from "react";
import { CalendarBlank, CaretDown, CheckCircle, Copy, DownloadSimple, FileText, Info, Paperclip, Quotes, SealCheck, XCircle } from "@phosphor-icons/react";
import Claim from "./Claim.jsx";
import { BASIS, CARE, NOTICE_STATUS, daysUntil, fmtDate } from "./text.js";

export default function DenialView({ result, sourceKey, onSource, onEditClaim, onOverride }) {
  return (
    <div className="stack">
      <Summary result={result} />
      <Facts facts={result.facts} onSource={onSource} onOverride={onOverride} />
      <Deadlines deadlines={result.deadlines} onSource={onSource} sourceKey={sourceKey} />
      <NoticeCheck notice={result.notice} onSource={onSource} sourceKey={sourceKey} />
      <Letter result={result} onSource={onSource} onEditClaim={onEditClaim} sourceKey={sourceKey} />
    </div>
  );
}

const jump = (id) => document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });

/** The case at a glance: three numbers, each a link to its section. */
function Summary({ result }) {
  const first = result.deadlines[0];
  const left = first ? daysUntil(first.due) : null;
  const missing = result.notice.not_found.length;
  const drafted = result.letter.sections.flatMap((s) => s.claims).filter((c) => c.source === "model" || c.source === "edited");
  const supported = drafted.filter((c) => c.supported).length;
  return (
    <nav className="summary" aria-label="Case summary">
      <button className="tile" onClick={() => jump("deadline")}>
        <CalendarBlank size={20} aria-hidden />
        <span className="tile-label">Appeal deadline</span>
        <span className={`tile-value ${left === null ? "" : left < 0 ? "bad" : left <= 30 ? "warn" : "ok"}`}>
          {left === null ? "Add the date" : left < 0 ? "Passed" : `${left} days`}
        </span>
      </button>
      <button className="tile" onClick={() => jump("notice")}>
        {missing ? <XCircle size={20} aria-hidden /> : <CheckCircle size={20} aria-hidden />}
        <span className="tile-label">Notice check</span>
        <span className={`tile-value ${missing ? "bad" : "ok"}`}>{missing ? `${missing} missing` : "Complete"}</span>
      </button>
      <button className="tile" onClick={() => jump("letter")}>
        <SealCheck size={20} aria-hidden />
        <span className="tile-label">Appeal letter</span>
        <span className={`tile-value ${supported === drafted.length ? "ok" : "warn"}`}>
          {supported} of {drafted.length} verified
        </span>
      </button>
    </nav>
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
        <span className="fact-value">{shown || <span className="muted">Not found</span>}</span>
        {f.confirmed && cit ? (
          <button className="chip ok" onClick={() => onSource({ ...cit, ok: true })}>
            <Quotes size={14} weight="fill" aria-hidden />
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
      <div className="card-head">
        <h2>What the letter says</h2>
        <button className="btn small ghost" onClick={() => setEditing((e) => !e)} aria-expanded={editing}>
          {editing ? "Close" : "Correct something"}
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

function Note({ children }) {
  return (
    <p className="note">
      <Info size={16} aria-hidden />
      <span>{children}</span>
    </p>
  );
}

function Deadlines({ deadlines, onSource, sourceKey }) {
  if (!deadlines.length) {
    return (
      <section className="card" id="deadline">
        <h2>Deadlines</h2>
        <p className="muted">We could not find the date of the denial notice. Add it above to see your deadlines.</p>
      </section>
    );
  }
  const [first, ...rest] = deadlines;
  const left = daysUntil(first.due);
  const tone = left < 0 ? "bad" : left <= 30 ? "warn" : "ok";
  return (
    <section className="card deadline" id="deadline">
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
      <div className="notes">
        {first.notes.map((n, i) => (
          <Note key={i}>{n}</Note>
        ))}
      </div>
      <h3 className="subhead">What happens next</h3>
      <ol className="timeline">
        {rest.map((d) => (
          <li key={d.id}>
            <p className="tl-title">
              {d.title}
              {d.due && <span className="tl-date">by {fmtDate(d.due)}</span>}
            </p>
            {d.claims.map((c, i) => (
              <Claim key={i} claim={c} onSource={onSource} active={sourceKey === key(c)} />
            ))}
            {d.notes.map((n, i) => (
              <Note key={i}>{n}</Note>
            ))}
          </li>
        ))}
      </ol>
    </section>
  );
}

function CheckItem({ e, onSource }) {
  const s = NOTICE_STATUS[e.status];
  const ev = e.evidence[0]?.citations.find((c) => c.ok);
  return (
    <li className={e.status}>
      <span className={`dot ${s.tone}`} aria-hidden />
      <span className="ck-title">{e.title}</span>
      <span className="ck-actions">
        <span className={`chip ${s.tone}`}>{s.label}</span>
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
}

function NoticeCheck({ notice, onSource, sourceKey }) {
  const missing = notice.elements.filter((e) => e.status === "not_found");
  const found = notice.elements.filter((e) => e.status === "present");
  const other = notice.elements.filter((e) => e.status !== "not_found" && e.status !== "present");
  return (
    <section className="card" id="notice">
      <div className="card-head">
        <h2>Is the denial notice complete?</h2>
        <span className={`chip ${missing.length ? "bad" : "ok"}`}>{missing.length ? `${missing.length} missing` : "Nothing missing"}</span>
      </div>
      <p className="muted small">
        Federal rules say what a denial notice must include. Something counts as found only when we can quote it from your
        letter.
      </p>
      {missing.length > 0 && (
        <ul className="checklist">
          {missing.map((e) => (
            <CheckItem key={e.id} e={e} onSource={onSource} />
          ))}
        </ul>
      )}
      {notice.exhaustion && (
        <div className="callout">
          <Claim claim={notice.exhaustion} onSource={onSource} active={sourceKey === key(notice.exhaustion)} />
        </div>
      )}
      <details className="disclosure">
        <summary>
          <CaretDown size={16} weight="bold" aria-hidden className="caret" />
          {found.length} found in your letter
        </summary>
        <ul className="checklist">
          {found.map((e) => (
            <CheckItem key={e.id} e={e} onSource={onSource} />
          ))}
        </ul>
      </details>
      {other.length > 0 && (
        <details className="disclosure">
          <summary>
            <CaretDown size={16} weight="bold" aria-hidden className="caret" />
            {other.length} not required here, or to ask the insurer about
          </summary>
          <ul className="checklist">
            {other.map((e) => (
              <CheckItem key={e.id} e={e} onSource={onSource} />
            ))}
          </ul>
        </details>
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
    <section className="card letter-card" id="letter">
      <div className="card-head">
        <h2>Your appeal, drafted</h2>
        <div className="row gap">
          <button
            className="btn small"
            onClick={() =>
              navigator.clipboard?.writeText(text).then(() => {
                setCopied(true);
                setTimeout(() => setCopied(false), 1800);
              })
            }
          >
            <Copy size={16} weight="bold" aria-hidden />
            {copied ? "Copied" : "Copy letter"}
          </button>
          <a className="btn small ghost" href={`data:text/plain;charset=utf-8,${encodeURIComponent(text)}`} download="appeal-draft.txt">
            <DownloadSimple size={16} weight="bold" aria-hidden />
            Download
          </a>
        </div>
      </div>
      <p className="muted small">
        Every sentence cites your letter, your plan or a federal rule, and was checked word for word. Click one to see its
        source, or use the pencil to edit it. Sentences that fail the check are struck through and left out of the copy.
      </p>
      <p className="stats">
        <span className="chip ok">
          <SealCheck size={14} weight="fill" aria-hidden />
          {stats.supported} of {stats.model_claims} sentences verified
        </span>
        {stats.rejected > 0 && <span className="chip bad">{stats.rejected} rejected by the verifier</span>}
      </p>
      <article className="paper">
        <p className="paper-mark">
          <FileText size={16} aria-hidden /> Draft
        </p>
        <p>To the Appeals Unit:</p>
        <p>I am requesting an internal appeal of the denial described below.</p>
        {result.letter.sections.map((s) =>
          s.claims.length ? (
            <div key={s.id} className="letter-section">
              <h3>{s.title}</h3>
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
        <h3 className="subhead">
          <Paperclip size={16} weight="bold" aria-hidden /> Send with your appeal
        </h3>
        <ul>
          {result.enclosures.map((e) => (
            <li key={e}>{e}</li>
          ))}
        </ul>
      </div>
      <p className="muted small">You send the letter. Clause never contacts your insurer.</p>
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
