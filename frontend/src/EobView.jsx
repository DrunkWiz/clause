import Claim from "./Claim.jsx";
import { NSA_STATUS } from "./text.js";

export default function EobView({ result, onSource }) {
  const nsa = result.no_surprises;
  const s = nsa && NSA_STATUS[nsa.status];
  const flags = [...(nsa?.flags || []), ...result.patient_share];
  return (
    <div className="stack">
      <section className={`card ${flags.length ? "alert" : ""}`}>
        <p className="eyebrow">What we found</p>
        <h3>{flags.length ? `${flags.length} thing${flags.length > 1 ? "s" : ""} to question on this EOB` : "Nothing on this EOB looks wrong"}</h3>
        {flags.map((c, i) => (
          <div key={i} className="flag">
            <Claim claim={c} onSource={onSource} />
          </div>
        ))}
      </section>

      {nsa && (
        <section className="card">
          <div className="row between wrap">
            <h3>Surprise billing</h3>
            <span className={`chip ${s.tone}`}>{s.label}</span>
          </div>
          {nsa.claims.map((c, i) => (
            <Claim key={i} claim={c} onSource={onSource} />
          ))}
          {nsa.notes.map((n, i) => (
            <p key={i} className="note">
              {n}
            </p>
          ))}
        </section>
      )}

      <section className="card">
        <h3>The codes on your EOB</h3>
        <p className="muted small">
          Code numbers are from the X12 claim adjustment code lists; the plain-language meanings are ours.
        </p>
        <ul className="codes">
          {result.lines.map((l, i) => (
            <li key={i}>
              <div className="row between wrap">
                <button className="code" onClick={() => onSource(l.line.citations[0])}>
                  {l.group}-{l.code}
                </button>
                <span className="amount">{l.amount}</span>
              </div>
              <p>{l.meaning}</p>
              <p className="muted small">Next step: {l.next_step}</p>
              {l.claims.map((c, j) => (
                <Claim key={j} claim={c} onSource={onSource} />
              ))}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
