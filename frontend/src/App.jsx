import { useEffect, useState } from "react";
import { getJSON, indexPdf, loadSaved, postJSON, save } from "./api.js";
import DenialView from "./DenialView.jsx";
import EobView from "./EobView.jsx";
import SourceViewer from "./SourceViewer.jsx";

const PLANS = [
  { id: "ambetter-tx", label: "Ambetter Health Solutions Silver 5000 (Texas)", docs: ["ambetter-tx-silver-sbc-2026", "ambetter-tx-eoc-2026"] },
  { id: "kaiser-ga", label: "Kaiser Permanente Signature Gold HMO (Georgia)", docs: ["kaiser-ga-gold-hmo-sbc-2026", "kaiser-ga-hmo-eoc-2026"] },
  { id: "fidelis-ny", label: "Ambetter from Fidelis Care Silver (New York)", docs: ["fidelis-ny-silver-sbc-2026", "fidelis-ny-silver-contract-2026"] },
];

export default function App() {
  const saved = loadSaved();
  const [cases, setCases] = useState([]);
  const [current, setCurrent] = useState(saved); // {meta, result}
  const [source, setSourceState] = useState(null);
  // On narrow screens the source sits below the case, so bring it into view.
  const setSource = (s) => {
    setSourceState(s);
    if (s && window.matchMedia?.("(max-width: 900px)").matches) {
      requestAnimationFrame(() => document.querySelector(".right")?.scrollIntoView({ behavior: "smooth", block: "start" }));
    }
  };
  const [busy, setBusy] = useState(null); // {title, live, started}
  const [error, setError] = useState("");
  const [uploads, setUploads] = useState({}); // doc_id -> blob URL, this session only
  const [uploadIndex, setUploadIndex] = useState(null);

  useEffect(() => {
    getJSON("/api/demo").then((d) => setCases(d.cases), () => setError("The server is not reachable."));
  }, []);
  useEffect(() => save(current?.meta?.upload ? null : current), [current]);

  async function run(meta, call, live = false) {
    setError("");
    setBusy({ title: meta.title, live, started: Date.now() });
    setSource(null);
    try {
      const result = await call();
      setCurrent({ meta, result });
      window.scrollTo({ top: 0 });
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(null);
    }
  }

  const openDemo = (c, overrides, live = false) =>
    run({ id: c.id, kind: c.kind, title: c.title, docs: [c.id, ...c.plan_docs] }, () => postJSON(`/api/demo/${c.id}`, { overrides, live }), live);
  const demoOf = (meta) => ({ id: meta.id, kind: meta.kind, title: meta.title, plan_docs: meta.docs.slice(1) });

  async function openUpload({ file, planId, kind }) {
    const plan = PLANS.find((p) => p.id === planId);
    await run({ upload: true, kind, title: file.name, docs: plan.docs }, async () => {
      const index = await indexPdf(file);
      const docId = index.documents[0].doc_id;
      setUploads({ [docId]: URL.createObjectURL(file) });
      setUploadIndex({ index, planDocs: plan.docs, kind });
      return postJSON("/api/case", { kind, document: index, plan_docs: plan.docs });
    }, true);
  }

  function override(vals) {
    const meta = current.meta;
    const overrides = Object.fromEntries(Object.entries(vals).filter(([, v]) => v));
    if (meta.upload && uploadIndex) {
      run(meta, () => postJSON("/api/case", { kind: uploadIndex.kind, document: uploadIndex.index, plan_docs: uploadIndex.planDocs, overrides }), true);
    } else {
      openDemo(demoOf(meta), overrides);
    }
  }

  async function editClaim(sectionId, i, text) {
    const { meta, result } = current;
    const old = result.letter.sections.find((s) => s.id === sectionId).claims[i];
    const claim = { text, source: "edited", citations: old.citations.map(({ doc, clause_id, quote }) => ({ doc, clause_id, quote })) };
    const body = { claim, docs: meta.upload ? meta.docs : meta.docs };
    if (meta.upload && uploadIndex) body.documents = [uploadIndex.index];
    const checked = await postJSON("/api/verify", body);
    const sections = result.letter.sections.map((s) =>
      s.id !== sectionId ? s : { ...s, claims: s.claims.map((c, j) => (j === i ? checked : c)) },
    );
    setCurrent({ meta, result: { ...result, letter: { sections } } });
    const ok = checked.citations.find((c) => c.ok);
    if (ok) setSource(ok);
  }

  const sourceKey = source ? `${source.clause_id}|${source.quote}` : "";
  const result = current?.result;

  return (
    <div className="app">
      <header className="top">
        <button className="brand" onClick={() => { setCurrent(null); setSource(null); }}>
          <span className="mark" aria-hidden>
            ¶
          </span>
          Clause
        </button>
        <p className="tagline">Only says what your plan says.</p>
      </header>
      <p className="disclaimer">
        Information about your own plan documents, not legal or medical advice. Federal minimums only; your state may give you
        more. Confirm dates with your insurer.
      </p>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {busy && <Busy busy={busy} />}

      {!result ? (
        <Home cases={cases} onOpen={openDemo} onUpload={openUpload} disabled={!!busy} />
      ) : (
        <main className="split">
          <div className="left">
            <div className="case-head">
              <button className="link small" onClick={() => { setCurrent(null); setSource(null); }}>
                ← All cases
              </button>
              <h1>{current.meta.title}</h1>
              <div className="row gap wrap">
                {!current.meta.upload && <span className="chip warn">Synthetic test case</span>}
                <ModelBadge answeredBy={result.answered_by} />
                {!current.meta.upload && (
                  <button className="link small" onClick={() => openDemo(demoOf(current.meta), undefined, true)} disabled={!!busy}>
                    Run again with the live model
                  </button>
                )}
              </div>
            </div>
            {result.kind === "denial" ? (
              <DenialView result={result} sourceKey={sourceKey} onSource={setSource} onEditClaim={editClaim} onOverride={override} />
            ) : (
              <EobView result={result} onSource={setSource} />
            )}
          </div>
          <aside className="right">
            <SourceViewer source={source} documents={result.documents} clauses={result.clauses} uploads={uploads} />
          </aside>
        </main>
      )}
      <footer className="foot">
        Plan documents are real public 2026 documents. Denial letters and EOBs in the demo are synthetic. Uploaded files are
        read in memory and not stored. Clause drafts; you decide what to send.
      </footer>
    </div>
  );
}

function Home({ cases, onOpen, onUpload, disabled }) {
  const [file, setFile] = useState(null);
  const [planId, setPlanId] = useState(PLANS[0].id);
  const [kind, setKind] = useState("denial");
  const denials = cases.filter((c) => c.kind === "denial");
  const eobs = cases.filter((c) => c.kind === "eob");
  return (
    <main className="home">
      <section className="hero">
        <h1>Got a denial letter? You can fight it.</h1>
        <p className="lede">
          Clause reads your own plan and your letter, works out your appeal deadline, checks what the insurer left out, and
          drafts an appeal in which every sentence points to the words it rests on. If it can’t point to it, it doesn’t say it.
        </p>
      </section>

      <section>
        <h2 className="section-title">Try a denial</h2>
        <div className="cards">
          {denials.map((c) => (
            <CaseCard key={c.id} c={c} onOpen={onOpen} disabled={disabled} />
          ))}
        </div>
      </section>
      <section>
        <h2 className="section-title">Check an Explanation of Benefits</h2>
        <div className="cards">
          {eobs.map((c) => (
            <CaseCard key={c.id} c={c} onOpen={onOpen} disabled={disabled} />
          ))}
        </div>
      </section>

      <section className="card upload">
        <h2 className="section-title">Use your own letter</h2>
        <p className="muted small">
          Your PDF is read in memory to find its paragraphs, then discarded. Nothing is stored on our server.
        </p>
        <form
          className="upload-form"
          onSubmit={(e) => {
            e.preventDefault();
            if (file) onUpload({ file, planId, kind });
          }}
        >
          <label>
            Document
            <input type="file" accept="application/pdf" onChange={(e) => setFile(e.target.files[0] || null)} />
          </label>
          <label>
            It is a
            <select value={kind} onChange={(e) => setKind(e.target.value)}>
              <option value="denial">Denial letter</option>
              <option value="eob">Explanation of Benefits</option>
            </select>
          </label>
          <label>
            Your plan
            <select value={planId} onChange={(e) => setPlanId(e.target.value)}>
              {PLANS.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.label}
                </option>
              ))}
            </select>
          </label>
          <button className="btn" disabled={!file || disabled}>
            Check it
          </button>
        </form>
      </section>

      <section className="how">
        <h2 className="section-title">How it stays honest</h2>
        <ol>
          <li>
            <strong>Every paragraph gets an address.</strong> Your letter, your plan and the federal rules are split into
            passages, each with its page and position.
          </li>
          <li>
            <strong>The model may only point.</strong> It reads and drafts, but every sentence must quote the passage it
            rests on.
          </li>
          <li>
            <strong>Code checks the pointing.</strong> Each quote must appear word for word in the passage it cites, and
            every amount or number of days must appear in the quote. Sentences that fail are greyed out, never shown as fact.
          </li>
          <li>
            <strong>Deadlines are code, not guesses.</strong> They are computed from the federal regulations, and each one
            links to the paragraph of law it comes from.
          </li>
        </ol>
      </section>
    </main>
  );
}

// A live model run takes about a minute, so say so and show that it is still going.
function Busy({ busy }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);
  const secs = Math.max(0, Math.round((now - busy.started) / 1000));
  return (
    <div className="busy" role="status">
      <span className="spinner" aria-hidden />
      <span>
        {busy.live
          ? "Asking the live model to read your documents, then checking every citation. This usually takes about a minute."
          : "Reading the documents and checking every citation…"}
        {secs >= 3 && <span className="elapsed"> {secs}s</span>}
      </span>
    </div>
  );
}

const MODEL_NAMES = { gemini: "Gemini Flash", featherless: "Featherless", recorded: "a saved Gemini response" };

function ModelBadge({ answeredBy }) {
  const used = [...new Set(Object.values(answeredBy || {}))];
  const live = !used.includes("recorded");
  return (
    <span className={`chip ${live ? "ok" : "muted"}`} title="Which model answered. Saved responses are replayed for the demo cases when speed matters or the live model is unavailable.">
      {live ? "Live: " : "From "}
      {used.map((u) => MODEL_NAMES[u] || u).join(" + ")}
    </span>
  );
}

function CaseCard({ c, onOpen, disabled }) {
  return (
    <button className="case-card" onClick={() => onOpen(c)} disabled={disabled}>
      <span className="chip warn">Synthetic</span>
      <span className="case-title">{c.title}</span>
      <span className="muted small">Plan: {c.plan_docs[0].split("-").slice(0, 2).join(" ").toUpperCase()}</span>
    </button>
  );
}
