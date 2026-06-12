const API = "http://127.0.0.1:8000";
const $ = (id) => document.getElementById(id);

let masterResume = null;   // structured master resume (JSON)
let tailored = null;       // last tailored resume (JSON)
let boldTerms = [];        // matched JD keywords to bold in the rendered files

// ---------- backend health ----------
async function checkBackend() {
  try {
    const r = await fetch(`${API}/health`, { cache: "no-store" });
    const j = await r.json();
    $("backend-dot").className = "dot dot-ok";
    $("backend-warn").classList.add("hidden");
    if (!j.has_key) {
      $("backend-warn").classList.remove("hidden");
      $("backend-warn").innerHTML =
        "Backend is running but no API key found. Add <code>GEMINI_API_KEY</code> to " +
        "<code>backend/.env</code> and restart it.";
    }
    return true;
  } catch (e) {
    $("backend-dot").className = "dot dot-bad";
    $("backend-warn").classList.remove("hidden");
    return false;
  }
}

// ---------- resume storage ----------
async function loadStoredResume() {
  const { resume } = await chrome.storage.local.get("resume");
  if (resume) {
    masterResume = resume;
    $("resume-status").textContent = "stored ✓";
    showResumeSummary();
    refreshActionState();
  }
}
function showResumeSummary() {
  if (!masterResume) return;
  const exp = (masterResume.experience || []).length;
  const sk = (masterResume.skills || []).length;
  const el = $("resume-summary");
  el.classList.remove("hidden");
  el.textContent = `${masterResume.name || "Resume"} · ${exp} role(s) · ${sk} skill group(s)`;
}

$("upload-btn").onclick = () => $("resume-file").click();
$("resume-file").onchange = async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  setLoading(true, "Reading and structuring your resume…");
  try {
    const fd = new FormData();
    fd.append("file", file);
    const r = await fetch(`${API}/import`, { method: "POST", body: fd });
    if (!r.ok) throw new Error((await r.json()).detail || r.statusText);
    masterResume = await r.json();
    await chrome.storage.local.set({ resume: masterResume });
    $("resume-status").textContent = "stored ✓";
    showResumeSummary();
    refreshActionState();
  } catch (err) {
    alert("Could not import resume: " + err.message);
  } finally {
    setLoading(false);
  }
};

// ---------- JD detection ----------
$("detect-btn").onclick = async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab) return;
  try {
    const res = await chrome.tabs.sendMessage(tab.id, { type: "GET_JD" });
    if (res && res.jd) {
      $("jd-text").value = res.jd;
      $("jd-source").textContent = "from " + (res.source || "page");
    } else {
      $("jd-source").textContent = "nothing detected — paste or select text";
    }
  } catch (e) {
    // content script not present (e.g. chrome:// page) — ask user to paste
    $("jd-source").textContent = "can't read this page — paste the JD";
  }
  refreshActionState();
};
$("jd-text").addEventListener("input", refreshActionState);

function refreshActionState() {
  const ready = !!masterResume && $("jd-text").value.trim().length > 40;
  $("score-btn").disabled = !ready;
  $("tailor-btn").disabled = !ready;
}

// ---------- score ----------
$("score-btn").onclick = async () => {
  setLoading(true, "Scoring against the job description…");
  try {
    const r = await fetch(`${API}/score`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ resume: masterResume, jd: $("jd-text").value }),
    });
    if (!r.ok) throw new Error((await r.json()).detail || r.statusText);
    const data = await r.json();
    tailored = null;
    renderScore(data.score, null);
    $("download-row").classList.add("hidden");
    $("changelog").classList.add("hidden");
  } catch (err) {
    alert("Scoring failed: " + err.message);
  } finally {
    setLoading(false);
  }
};

// ---------- tailor ----------
$("tailor-btn").onclick = async () => {
  setLoading(true, "Tailoring (extract → rewrite → verify → re-score)…");
  try {
    const r = await fetch(`${API}/tailor`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ resume: masterResume, jd: $("jd-text").value }),
    });
    if (!r.ok) throw new Error((await r.json()).detail || r.statusText);
    const { result } = await r.json();
    tailored = result.resume;
    renderScore(result.score_after, result.score_before);
    renderChangeLog(result.change_log, result.flagged);
    $("download-row").classList.remove("hidden");
  } catch (err) {
    alert("Tailoring failed: " + err.message);
  } finally {
    setLoading(false);
  }
};

// ---------- downloads ----------
async function download(kind) {
  const resume = tailored || masterResume;
  const name = (resume.name || "resume").replace(/\s+/g, "_");
  const r = await fetch(`${API}/render/${kind}`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ resume, filename: name, bold_terms: boldTerms }),
  });
  if (!r.ok) { alert("Render failed."); return; }
  const blob = await r.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = `${name}.${kind}`; a.click();
  URL.revokeObjectURL(url);
}
$("dl-pdf").onclick = () => download("pdf");
$("dl-docx").onclick = () => download("docx");

// ---------- render helpers ----------
function renderScore(score, before) {
  boldTerms = score.matched || [];
  $("score-card").classList.remove("hidden");
  $("score-total").textContent = score.total;
  const delta = $("score-delta");
  if (before) {
    const d = score.total - before.total;
    delta.textContent = `${before.total} → ${score.total} (${d >= 0 ? "+" : ""}${d})`;
    delta.className = "delta " + (d > 0 ? "up" : d < 0 ? "down" : "");
  } else { delta.textContent = ""; delta.className = "delta"; }

  $("subscores").innerHTML = "";
  for (const s of score.subscores) {
    const div = document.createElement("div");
    div.className = "sub";
    div.innerHTML = `
      <div class="sub-row"><span class="sub-name">${s.name}</span>
        <span class="sub-val">${Math.round(s.value)} · ${Math.round(s.weight * 100)}%</span></div>
      <div class="track"><div class="fill" style="width:${Math.round(s.value)}%"></div></div>
      <div class="sub-detail">${escapeHtml(s.detail || "")}</div>`;
    $("subscores").appendChild(div);
  }
  chips("kw-matched", score.matched, "chip");
  chips("kw-missing-req", score.missing_required, "chip miss");
  chips("kw-adjacent", (score.adjacent || []).map(a => a.split(" -> ")[0].split(":")[0]), "chip");
  chips("kw-missing-pref", score.missing_preferred, "chip pref");

  $("notes").innerHTML = "";
  for (const n of score.notes || []) {
    const d = document.createElement("div"); d.className = "note"; d.textContent = n;
    $("notes").appendChild(d);
  }
}
function chips(id, items, cls) {
  const c = $(id); c.innerHTML = "";
  for (const it of items || []) {
    const s = document.createElement("span"); s.className = cls; s.textContent = it;
    c.appendChild(s);
  }
}
function renderChangeLog(log, flagged) {
  const c = $("changelog"); c.innerHTML = ""; c.classList.remove("hidden");
  for (const line of log || []) { const d = document.createElement("div"); d.textContent = "• " + line; c.appendChild(d); }
  if (flagged && flagged.length) {
    const d = document.createElement("div");
    d.textContent = "⚠ Add these only if true: " + flagged.join(", ");
    c.appendChild(d);
  }
}
function escapeHtml(s) { const d = document.createElement("div"); d.textContent = s; return d.innerHTML; }
function setLoading(on, msg) {
  $("loading").classList.toggle("hidden", !on);
  if (msg) $("loading-msg").textContent = msg;
}

$("retry").onclick = checkBackend;

// init
checkBackend();
loadStoredResume();
