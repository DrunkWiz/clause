async function handle(res) {
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
  return data;
}

export const getJSON = (url) => fetch(url).then(handle);

export const postJSON = (url, body) =>
  fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
  }).then(handle);

// The PDF is sent once to be indexed in memory and is not stored on the server.
export const indexPdf = (file) =>
  fetch("/api/index", {
    method: "POST",
    headers: { "Content-Type": "application/pdf", "X-Filename": file.name },
    body: file,
  }).then(handle);

// Per-viewer convenience only: the current case survives a reload on this device.
const KEY = "clause.case.v1";
export function loadSaved() {
  try {
    return JSON.parse(localStorage.getItem(KEY) || "null");
  } catch {
    return null;
  }
}
export function save(value) {
  try {
    if (value) localStorage.setItem(KEY, JSON.stringify(value));
    else localStorage.removeItem(KEY);
  } catch {
    /* storage unavailable or full: the app works without it */
  }
}
