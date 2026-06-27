// AlphaDynamics live predictor — calls the public Hugging Face Space directly
// over the raw Gradio HTTP API (no @gradio/client dependency, no token).
const BASE = "https://krissss0-alphadynamics.hf.space";
const AA = /^[ACDEFGHIKLMNPQRSTVWY]+$/;

const $ = (id) => document.getElementById(id);
const seqEl = $("seq"), trajEl = $("traj"), stepsEl = $("steps");
const trajVal = $("trajVal"), stepVal = $("stepVal");
const runBtn = $("run"), errEl = $("err");
const placeholder = $("placeholder"), plotEl = $("rama-plot");
const basinsEl = $("basins"), dlEl = $("downloads");

// --- controls ---
trajEl.addEventListener("input", () => (trajVal.textContent = trajEl.value));
stepsEl.addEventListener("input", () => (stepVal.textContent = stepsEl.value));
document.querySelectorAll(".examples button").forEach((b) =>
  b.addEventListener("click", () => { seqEl.value = b.dataset.seq; errEl.textContent = ""; })
);

function cleanSeq() { return seqEl.value.trim().toUpperCase().replace(/\s+/g, ""); }
function validate(seq) {
  if (!seq) return "Enter a peptide sequence.";
  if (seq.length < 4 || seq.length > 20) return "Sequence must be 4–20 residues.";
  if (!AA.test(seq)) return "Use one-letter amino-acid codes only (ACDEFGHIKLMNPQRSTVWY).";
  return null;
}

// turn a Gradio file output into a usable URL
function fileUrl(f) {
  if (!f) return null;
  if (typeof f === "string") return f.startsWith("http") ? f : `${BASE}/gradio_api/file=${f}`;
  if (f.url) return f.url;
  if (f.path) return `${BASE}/gradio_api/file=${f.path}`;
  return null;
}

function downloadLink(href, label, name) {
  const a = document.createElement("a");
  a.href = href; a.download = name || ""; a.target = "_blank"; a.rel = "noopener";
  a.innerHTML =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>' +
    label;
  return a;
}

// raw Gradio API: POST -> event_id, then GET SSE stream until "complete"
async function callPredict(payload) {
  const post = await fetch(`${BASE}/gradio_api/call/predict`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ data: payload }),
  });
  if (!post.ok) throw new Error("POST " + post.status);
  const { event_id } = await post.json();
  if (!event_id) throw new Error("no event_id from Space");

  const res = await fetch(`${BASE}/gradio_api/call/predict/${event_id}`);
  if (!res.ok || !res.body) throw new Error("stream " + res.status);

  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = "", ev = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let nl;
    while ((nl = buf.indexOf("\n")) >= 0) {
      const line = buf.slice(0, nl); buf = buf.slice(nl + 1);
      if (line.startsWith("event:")) ev = line.slice(6).trim();
      else if (line.startsWith("data:")) {
        const d = line.slice(5).trim();
        if (ev === "complete") return JSON.parse(d);
        if (ev === "error") throw new Error("Space error" + (d ? ": " + d : ""));
      }
    }
  }
  throw new Error("stream ended before completion");
}

async function run() {
  const seq = cleanSeq();
  seqEl.value = seq;
  const v = validate(seq);
  errEl.textContent = "";
  if (v) { errEl.textContent = v; return; }

  runBtn.disabled = true;
  runBtn.innerHTML = '<span class="spin"></span>Propagating dynamics… (first run wakes the model, ~30–60 s)';
  basinsEl.innerHTML = ""; dlEl.innerHTML = "";

  try {
    const data = await callPredict([seq, Number(trajEl.value), Number(stepsEl.value)]);

    // 0: Ramachandran density (plotly)
    const plot = data[0];
    if (plot && plot.type === "plotly" && plot.plot) {
      const fig = typeof plot.plot === "string" ? JSON.parse(plot.plot) : plot.plot;
      placeholder.style.display = "none";
      plotEl.style.display = "block";
      const layout = Object.assign({}, fig.layout, {
        paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)",
        font: { color: "#9aa0b4" }, margin: { t: 20, r: 10, b: 40, l: 50 },
      });
      Plotly.newPlot(plotEl, fig.data, layout, { responsive: true, displaylogo: false });
    }

    // 1: basin populations (markdown)
    if (data[1]) basinsEl.innerHTML = window.marked ? marked.parse(data[1]) : "<pre>" + data[1] + "</pre>";

    // 2,3: downloads (.npz, .pdb)
    const npz = fileUrl(data[2]), pdb = fileUrl(data[3]);
    if (npz) dlEl.appendChild(downloadLink(npz, "trajectory .npz", `alphadynamics_${seq}.npz`));
    if (pdb) dlEl.appendChild(downloadLink(pdb, "backbone .pdb", `alphadynamics_${seq}.pdb`));
  } catch (e) {
    console.error(e);
    errEl.textContent = "Prediction failed: " + (e && e.message ? e.message : e) +
      ". The free Space may be cold or busy — try again in a moment.";
  } finally {
    runBtn.disabled = false;
    runBtn.textContent = "Generate torsion ensemble";
  }
}

runBtn.addEventListener("click", run);
seqEl.addEventListener("keydown", (e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) run(); });

// --- visitor counter (counterapi.dev) ---
(async () => {
  const box = $("counter"), n = $("counter-n");
  try {
    const r = await fetch("https://api.counterapi.dev/v1/myreson/alphadynamics/up");
    const j = await r.json();
    const c = j.count ?? j.value;
    if (typeof c === "number") { n.textContent = c.toLocaleString("en-US"); box.classList.remove("hidden"); }
  } catch (_) { /* if the counter service is down, just hide it — no fake number */ }
})();
