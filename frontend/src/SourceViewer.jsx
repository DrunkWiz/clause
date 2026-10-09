import { useEffect, useLayoutEffect, useRef, useState } from "react";
import * as pdfjs from "pdfjs-dist";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import { getJSON } from "./api.js";

pdfjs.GlobalWorkerOptions.workerSrc = workerUrl;

const KIND = {
  rule: "Federal rule or guidance",
  synthetic: "Synthetic test document",
  plan: "Your plan document",
  upload: "Your uploaded document",
};

const pdfCache = new Map();
function loadPdf(url) {
  if (!pdfCache.has(url)) pdfCache.set(url, pdfjs.getDocument({ url }).promise);
  return pdfCache.get(url);
}

const regCache = new Map();
function loadRegulation(docId) {
  if (!regCache.has(docId)) regCache.set(docId, getJSON(`/api/regulations/${docId}`));
  return regCache.get(docId);
}

export function pdfUrlFor(docId, documents, uploads) {
  // Uploaded files never leave the browser: they are shown from a local blob URL.
  return uploads?.[docId] || documents?.[docId]?.file_url || null;
}

/** The right-hand pane: the cited page with its highlight, or regulation text. */
export default function SourceViewer({ source, documents, clauses, uploads }) {
  if (!source) {
    return (
      <div className="viewer-empty">
        <p className="eyebrow">Source</p>
        <p>Click any sentence or citation to see the exact passage it rests on.</p>
      </div>
    );
  }
  const doc = documents?.[source.doc];
  const clause = clauses?.[source.clause_id];
  return (
    <div className="viewer">
      <header className="viewer-head">
        <p className="eyebrow">{KIND[doc?.kind] || "Document"}</p>
        <h2>{source.label || clause?.label || doc?.title || source.doc}</h2>
        {!doc?.regulation && source.page && (
          <p className="muted small">
            {doc?.title || doc?.filename} · page {source.page}
          </p>
        )}
        {source.quote && <blockquote className="quote">{source.quote}</blockquote>}
        {source.ok === false && <p className="warn small">This citation did not check out, so nothing is highlighted.</p>}
      </header>
      {doc?.regulation ? (
        <RegulationText source={source} doc={doc} />
      ) : (
        <PdfPage key={`${source.doc}`} source={source} url={pdfUrlFor(source.doc, documents, uploads)} pageCount={doc?.pages} />
      )}
    </div>
  );
}

function PdfPage({ source, url, pageCount }) {
  const wrap = useRef(null);
  const canvas = useRef(null);
  const [page, setPage] = useState(source.page || 1);
  const [base, setBase] = useState(null); // page size in PDF points
  const [error, setError] = useState("");
  const [width, setWidth] = useState(0);

  useEffect(() => setPage(source.page || 1), [source]);

  // Render at the panel's real width, and again when it changes.
  useLayoutEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setWidth(Math.floor(e.contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    if (!url || !width) return;
    let cancelled = false;
    let task;
    (async () => {
      try {
        const pdf = await loadPdf(url);
        const p = await pdf.getPage(page);
        if (cancelled) return;
        const base = p.getViewport({ scale: 1 });
        const s = width / base.width;
        const ratio = window.devicePixelRatio || 1;
        const vp = p.getViewport({ scale: s * ratio });
        const c = canvas.current;
        c.width = vp.width;
        c.height = vp.height;
        task = p.render({ canvasContext: c.getContext("2d"), viewport: vp });
        await task.promise;
        if (!cancelled) {
          setBase({ w: base.width, h: base.height });
          setError("");
        }
      } catch (e) {
        if (!cancelled && e?.name !== "RenderingCancelledException") {
          console.error("pdf render failed", e);
          setError("This page could not be shown.");
        }
      }
    })();
    return () => {
      cancelled = true;
      task?.cancel();
    };
  }, [url, page, width]);

  const boxes = base ? (source.highlights || []).filter((h) => h.page === page) : [];
  const first = useRef(null);
  useLayoutEffect(() => {
    first.current?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [base, page, source]);
  // Boxes are placed in % of the page, so they stay on the text at any size.
  const pct = (v, total, pad = 0) => `calc(${(v / total) * 100}% + ${pad}px)`;

  if (!url) return <p className="muted pad">The original file is not available in this browser session.</p>;
  return (
    <div className="pdf">
      {pageCount > 1 && (
        <div className="pager">
          <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page <= 1} aria-label="Previous page">
            ‹
          </button>
          <span>
            Page {page} of {pageCount}
          </span>
          <button onClick={() => setPage((p) => Math.min(pageCount, p + 1))} disabled={page >= pageCount} aria-label="Next page">
            ›
          </button>
          {source.page && page !== source.page && (
            <button className="link" onClick={() => setPage(source.page)}>
              Back to cited page
            </button>
          )}
        </div>
      )}
      <div className="page" ref={wrap}>
        <canvas ref={canvas} />
        {boxes.map((h, i) => (
          <div
            key={i}
            ref={i === 0 ? first : null}
            className="hl"
            style={{
              left: pct(h.bbox[0], base.w, -3),
              top: pct(h.bbox[1], base.h, -2),
              width: pct(h.bbox[2] - h.bbox[0], base.w, 6),
              height: pct(h.bbox[3] - h.bbox[1], base.h, 4),
            }}
          />
        ))}
        {error && <p className="warn pad">{error}</p>}
      </div>
    </div>
  );
}

function RegulationText({ source, doc }) {
  const [data, setData] = useState(null);
  const target = useRef(null);
  useEffect(() => {
    let live = true;
    loadRegulation(source.doc).then((d) => live && setData(d), () => live && setData({ clauses: [] }));
    return () => {
      live = false;
    };
  }, [source.doc]);
  useLayoutEffect(() => {
    target.current?.scrollIntoView({ block: "center" });
  }, [data, source]);

  if (!data) return <p className="muted pad">Loading the regulation…</p>;
  return (
    <div className="reg">
      {doc.source_url && (
        <p className="small pad-x">
          <a href={doc.source_url.includes("ecfr.gov/api") ? `https://www.ecfr.gov/current/title-${doc.title.split(" ")[0]}/section-${doc.title.split(" ").pop()}` : doc.source_url} target="_blank" rel="noreferrer">
            Read {doc.title} at the source ↗
          </a>
        </p>
      )}
      {data.clauses.map((c) => {
        const hit = c.clause_id === source.clause_id;
        return (
          <p key={c.clause_id} ref={hit ? target : null} className={hit ? "reg-p hit" : "reg-p"}>
            {hit ? <Marked text={c.text} spans={source.spans || []} /> : c.text}
          </p>
        );
      })}
    </div>
  );
}

function Marked({ text, spans }) {
  if (!spans.length) return text;
  const out = [];
  let at = 0;
  [...spans].sort((a, b) => a[0] - b[0]).forEach(([s, e], i) => {
    if (s > at) out.push(text.slice(at, s));
    out.push(<mark key={i}>{text.slice(s, e)}</mark>);
    at = e;
  });
  out.push(text.slice(at));
  return out;
}
