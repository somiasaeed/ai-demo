const examples = {
  echo: { agent: "echo", text: "hello from dashboard" },
  summarizer: { agent: "summarizer", file_path: "samples/job_description.txt" },
  cv_tailorer: {
    agent: "cv_tailorer",
    cv_path: "samples/cv.pdf",
    cover_letter_path: "samples/cover_letter.pdf",
    job_desc_path: "samples/job_description.txt",
    output_dir: "output",
    photo_path: null,
  },
  job_search: {
    agent: "job_search",
    query: "Senior Python backend engineer, remote EU",
    location: "Germany",
  },
};

function apiBase() {
  const el = document.getElementById("apiBase");
  if (el.value.trim()) return el.value.replace(/\/$/, "");
  return `${window.location.protocol}//${window.location.host}`;
}

function headers() {
  const h = { "Content-Type": "application/json" };
  const key = document.getElementById("apiKey").value.trim();
  if (key) h["X-API-Key"] = key;
  return h;
}

function setStatus(msg) {
  document.getElementById("status").textContent = msg || "";
}

async function loadAgents() {
  setStatus("Loading…");
  const res = await fetch(`${apiBase()}/api/v1/agents`, { headers: headers() });
  if (!res.ok) {
    setStatus(`Error ${res.status}`);
    document.getElementById("agentList").innerHTML = `<li class="muted">Failed to load (${res.status})</li>`;
    return;
  }
  const agents = await res.json();
  const ul = document.getElementById("agentList");
  ul.innerHTML = agents
    .map(
      (a) =>
        `<li><strong>${a.id}</strong> — ${a.title}<br/><span class="muted">${a.description}</span></li>`
    )
    .join("");

  const sel = document.getElementById("agentSelect");
  const prev = sel.value;
  sel.innerHTML = agents.map((a) => `<option value="${a.id}">${a.id}</option>`).join("");
  if (agents.some((a) => a.id === prev)) sel.value = prev;
  sel.dispatchEvent(new Event("change"));
  setStatus("");
}

function syncJsonFromSelect() {
  const id = document.getElementById("agentSelect").value;
  const ex = examples[id];
  if (ex) {
    document.getElementById("jsonBody").value = JSON.stringify(ex, null, 2);
  }
}

async function invoke() {
  const ta = document.getElementById("jsonBody");
  let body;
  try {
    body = JSON.parse(ta.value);
  } catch (e) {
    document.getElementById("result").textContent = "Invalid JSON: " + e.message;
    return;
  }
  setStatus("Running…");
  document.getElementById("result").textContent = "";
  const res = await fetch(`${apiBase()}/api/v1/invoke`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify(body),
  });
  const text = await res.text();
  let out;
  try {
    out = JSON.parse(text);
  } catch {
    out = text;
  }
  if (!res.ok) {
    document.getElementById("result").textContent =
      typeof out === "object" ? JSON.stringify(out, null, 2) : text;
    setStatus(`Error ${res.status}`);
    return;
  }
  document.getElementById("result").textContent = out.result ?? JSON.stringify(out, null, 2);
  setStatus("Done");
}

document.getElementById("btnLoadAgents").addEventListener("click", loadAgents);
document.getElementById("btnInvoke").addEventListener("click", invoke);
document.getElementById("agentSelect").addEventListener("change", syncJsonFromSelect);

document.getElementById("apiBase").value =
  window.location.origin.includes("127.0.0.1") || window.location.origin.includes("localhost")
    ? window.location.origin
    : "http://127.0.0.1:8000";

loadAgents();
