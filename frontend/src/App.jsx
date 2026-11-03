import { useEffect, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  CursorClick,
  FileArrowUp,
  GithubLogo,
  Lightning,
  ListChecks,
  Receipt,
  Scales,
  SealCheck,
  ShieldWarning,
  WarningCircle,
} from "@phosphor-icons/react";
import { getJSON, indexPdf, loadSaved, postJSON, save } from "./api.js";
import DenialView from "./DenialView.jsx";
import EobView from "./EobView.jsx";
import SourceViewer from "./SourceViewer.jsx";
import { caseParts, planName } from "./text.js";

const PLANS = [
  { id: "ambetter-tx", label: "Ambetter Health Solutions Silver 5000 (Texas)", docs: ["ambetter-tx-silver-sbc-2026", "ambetter-tx-eoc-2026"] },
  { id: "kaiser-ga", label: "Kaiser Permanente Signature Gold HMO (Georgia)", docs: ["kaiser-ga-gold-hmo-sbc-2026", "kaiser-ga-hmo-eoc-2026"] },
  { id: "fidelis-ny", label: "Ambetter from Fidelis Care Silver (New York)", docs: ["fidelis-ny-silver-sbc-2026", "fidelis-ny-silver-contract-2026"] },
];
const REPO = "https://github.com/DrunkWiz/clause";

export default function App() {
  const saved = loadSaved();
  const [cases, setCases] = useState([]);
  const [current, setCurrent] = useState(saved); // {meta, result}
  const [source, setSource] = useState(null);
  const [busy, setBusy] = useState(null); // {title, live, started}
  const [error, setError] = useState("");
  const [uploads, setUploads] = useState({}); // doc_id -> blob URL, this session only
  const [uploadIndex, setUploadIndex] = useState(null);

  useEffect(() => {
    getJSON("/api/demo").then((d) => setCases(d.cases), () => setError("The server is not reachable. Reload the page to try again."));
  }, []);
  useEffect(() => save(current?.meta?.upload ? null : current), [current]);
  // On phones the source is a sheet over the page; Escape closes it everywhere.
  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && setSource(null);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

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
    const body = { claim, docs: meta.docs };
    if (meta.upload && uploadIndex) body.documents = [uploadIndex.index];
    const checked = await postJSON("/api/verify", body);
    const sections = result.letter.sections.map((s) =>
      s.id !== sectionId ? s : { ...s, claims: s.claims.map((c, j) => (j === i ? checked : c)) },
    );
    setCurrent({ meta, result: { ...result, letter: { sections } } });
    const ok = checked.citations.find((c) => c.ok);
    if (ok) setSource(ok);
  }

  const goHome = () => {
    setCurrent(null);
    setSource(null);
  };
  const sourceKey = source ? `${source.clause_id}|${source.quote}` : "";
  const result = current?.result;

  return (
    <div className="app">
      <a className="skip" href="#main">
        Skip to content
      </a>
      <header className="top">
        <button className="brand" onClick={goHome} aria-label="Clause, back to all cases">
          <span className="mark" aria-hidden>
            ¶
          </span>
          Clause
        </button>
        <p className="tagline">Only says what your plan says.</p>
        <a className="top-link" href={REPO} target="_blank" rel="noreferrer">
          <GithubLogo size={20} aria-hidden />
          <span>Source code</span>
        </a>
      </header>
      <p className="disclaimer">
        <WarningCircle size={16} aria-hidden />
        <span>
          Information about your own plan documents, not legal or medical advice. Federal minimums only; your state may give
          you more. Confirm dates with your insurer.
        </span>
      </p>
      {error && (
        <p className="error" role="alert">
          <WarningCircle size={20} weight="fill" aria-hidden />
          <span>{error}</span>
        </p>
      )}

      <div id="main">
        {busy ? (
          <Busy busy={busy} />
        ) : !result ? (
          <Home cases={cases} onOpen={openDemo} onUpload={openUpload} />
        ) : (
          <main className="split">
            <div className="left">
              <CaseHead meta={current.meta} result={result} onBack={goHome} onLive={() => openDemo(demoOf(current.meta), undefined, true)} />
              {result.kind === "denial" ? (
                <DenialView result={result} sourceKey={sourceKey} onSource={setSource} onEditClaim={editClaim} onOverride={override} />
              ) : (
                <EobView result={result} onSource={setSource} />
              )}
            </div>
            {source && <div className="scrim" onClick={() => setSource(null)} aria-hidden />}
            <aside className={`right ${source ? "open" : ""}`} aria-label="Source document">
              <SourceViewer source={source} documents={result.documents} clauses={result.clauses} uploads={uploads} onClose={() => setSource(null)} />
            </aside>
          </main>
        )}
      </div>

      <footer className="foot">
        <p>
          Plan documents are real public 2026 documents. Denial letters and EOBs in the demo are synthetic. Uploaded files are
          read in memory and never stored. Clause drafts; you decide what to send.
        </p>
        <p>
          <a href={REPO} target="_blank" rel="noreferrer">
            Source code and data sources
          </a>
        </p>
      </footer>
    </div>
  );
}

function CaseHead({ meta, result, onBack, onLive }) {
  const p = meta.upload ? { kind: meta.kind === "eob" ? "EOB" : "Denial", title: meta.title, hint: "" } : caseParts(meta.title);
  return (
    <div className="case-head">
      <button className="back" onClick={onBack}>
        <ArrowLeft size={16} weight="bold" aria-hidden />
        All cases
      </button>
      <p className="eyebrow">
        {p.kind}
        {!meta.upload && <> · {planName(meta.docs.slice(1))}</>}
      </p>
      <h1>{p.title}</h1>
      <div className="row gap wrap">
        {!meta.upload && <span className="chip warn">Synthetic test case</span>}
        <ModelBadge answeredBy={result.answered_by} />
        {!meta.upload && (
          <button className="btn small ghost" onClick={onLive} title="Calls Gemini live. Takes about a minute.">
            <Lightning size={16} weight="bold" aria-hidden />
            Run with the live model
          </button>
        )}
      </div>
    </div>
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
    <div className="busy-wrap" role="status" aria-live="polite">
      <div className="busy">
        <span className="pulse" aria-hidden />
        <span>
          {busy.live
            ? "Asking the live model to read your documents, then checking every citation. This usually takes about a minute."
            : "Reading the documents and checking every citation…"}
          {secs >= 3 && <span className="elapsed"> {secs}s</span>}
        </span>
      </div>
      <div className="split" aria-hidden>
        <div className="stack">
          <div className="skel skel-title" />
          <div className="summary">
            <div className="skel skel-tile" />
            <div className="skel skel-tile" />
            <div className="skel skel-tile" />
          </div>
          <div className="skel skel-card" />
          <div className="skel skel-card tall" />
        </div>
        <div className="skel skel-pane" />
      </div>
    </div>
  );
}

function HeroPreview() {
  return (
    <div className="preview" aria-hidden>
      <div className="preview-card">
        <p className="eyebrow">Your appeal, drafted</p>
        <p className="preview-line">
          <span className="hl-text">My plan covers medically necessary radiology services, including MRI.</span>
          <span className="cite">1</span>
        </p>
        <p className="preview-line rejected">
          <span>The denied claim is for $2,400.00.</span>
          <span className="cite bad">1</span>
        </p>
        <p className="why">
          <WarningCircle size={16} weight="fill" />
          <span>It mentions $2,400, but the quoted text doesn’t.</span>
        </p>
      </div>
      <div className="preview-link">
        <CursorClick size={20} />
      </div>
      <div className="preview-card source">
        <p className="eyebrow">Your plan · page 99</p>
        <p className="preview-doc">
          <span className="doc-line">Radiology, Imaging and Other Diagnostic Testing</span>
          <span className="doc-line hl-box">Medically necessary radiology services, imaging and tests performed are a covered service (e.g., X‑ray, MRI)</span>
          <span className="doc-line faint" />
          <span className="doc-line faint short" />
        </p>
      </div>
    </div>
  );
}

function Home({ cases, onOpen, onUpload }) {
  const [file, setFile] = useState(null);
  const [planId, setPlanId] = useState(PLANS[0].id);
  const [kind, setKind] = useState("denial");
  const [touched, setTouched] = useState(false);
  const denials = cases.filter((c) => c.kind === "denial");
  const eobs = cases.filter((c) => c.kind === "eob");
  const fileError = touched && !file ? "Choose a PDF of your letter or EOB." : "";
  return (
    <main className="home">
      <section className="hero">
        <div className="hero-copy">
          <p className="eyebrow">For anyone holding a health insurance denial</p>
          <h1>
            Got a denial letter?
            <br />
            You can fight it.
          </h1>
          <p className="lede">
            Clause reads your plan and your letter, works out your appeal deadline, finds what the insurer left out, and drafts
            an appeal in which every sentence points to the words it rests on.
          </p>
          <div className="row gap wrap">
            <button className="btn" onClick={() => denials[0] && onOpen(denials[0])} disabled={!denials.length}>
              Open a sample denial
              <ArrowRight size={18} weight="bold" aria-hidden />
            </button>
            <a className="btn ghost" href="#upload">
              <FileArrowUp size={18} weight="bold" aria-hidden />
              Use your own letter
            </a>
          </div>
          <p className="proof">
            <strong>1 in 5</strong> in‑network claims on HealthCare.gov plans were denied in 2023, and fewer than{" "}
            <strong>1 in 100</strong> denials were appealed. <span className="muted">Source: KFF.</span>
          </p>
        </div>
        <HeroPreview />
      </section>

      <section aria-labelledby="try-denial">
        <h2 id="try-denial" className="section-title">
          Try a denial
        </h2>
        <div className="cards">
          {denials.map((c) => (
            <CaseCard key={c.id} c={c} onOpen={onOpen} Icon={ShieldWarning} />
          ))}
        </div>
      </section>
      <section aria-labelledby="try-eob">
        <h2 id="try-eob" className="section-title">
          Check an Explanation of Benefits
        </h2>
        <div className="cards">
          {eobs.map((c) => (
            <CaseCard key={c.id} c={c} onOpen={onOpen} Icon={Receipt} />
          ))}
        </div>
      </section>

      <section className="card upload" id="upload" aria-labelledby="upload-title">
        <div className="card-head">
          <h2 id="upload-title">Use your own letter</h2>
        </div>
        <p className="muted small">Your PDF is read in memory to find its paragraphs, then discarded. Nothing is stored on our server.</p>
        <form
          className="upload-form"
          noValidate
          onSubmit={(e) => {
            e.preventDefault();
            setTouched(true);
            if (file) onUpload({ file, planId, kind });
          }}
        >
          <label>
            Document (PDF)
            <input
              type="file"
              accept="application/pdf"
              aria-invalid={!!fileError}
              aria-describedby={fileError ? "file-error" : undefined}
              onChange={(e) => setFile(e.target.files[0] || null)}
            />
            {fileError && (
              <span className="field-error" id="file-error">
                {fileError}
              </span>
            )}
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
          <button className="btn">Check it</button>
        </form>
      </section>

      <section className="how" aria-labelledby="how-title">
        <h2 id="how-title" className="section-title">
          How it stays honest
        </h2>
        <ol className="steps">
          <li>
            <ListChecks size={24} aria-hidden />
            <h3>Every paragraph gets an address</h3>
            <p>Your letter, your plan and the federal rules are split into passages, each with its page and position.</p>
          </li>
          <li>
            <CursorClick size={24} aria-hidden />
            <h3>The model may only point</h3>
            <p>It reads and drafts, but every sentence must quote the passage it rests on.</p>
          </li>
          <li>
            <SealCheck size={24} aria-hidden />
            <h3>Code checks the pointing</h3>
            <p>Each quote must appear word for word, and every amount or day count must be in it. Failures are struck through, never shown as fact.</p>
          </li>
          <li>
            <Scales size={24} aria-hidden />
            <h3>Deadlines are code, not guesses</h3>
            <p>They are computed from the federal regulations, and each one links to the paragraph of law it comes from.</p>
          </li>
        </ol>
      </section>
    </main>
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

function CaseCard({ c, onOpen, Icon }) {
  const p = caseParts(c.title);
  return (
    <button className="case-card" onClick={() => onOpen(c)}>
      <span className="row between">
        <span className="case-icon" aria-hidden>
          <Icon size={20} />
        </span>
        <span className="chip warn">Synthetic</span>
      </span>
      <span className="case-title">{p.title}</span>
      {p.hint && <span className="case-hint">Look for: {p.hint}</span>}
      <span className="case-plan">{planName(c.plan_docs)}</span>
      <span className="case-go">
        Open case <ArrowRight size={16} weight="bold" aria-hidden />
      </span>
    </button>
  );
}
