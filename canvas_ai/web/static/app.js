const $ = (s) => document.querySelector(s);
const el = (t, c, h) => { const e = document.createElement(t); if (c) e.className = c; if (h != null) e.innerHTML = h; return e; };
let activeCourse = null;

async function api(path, opts) {
  const r = await fetch(path, opts);
  if (!r.ok) {
    const detail = await r.json().catch(() => ({}));
    throw new Error(detail.detail || `${r.status} ${r.statusText}`);
  }
  return r.json();
}

// ---- init ----
async function init() {
  try {
    const s = await api("/api/status");
    if (s.authenticated) {
      $("#status").textContent = `${s.name} · ${s.base_url.replace(/^https?:\/\//, "")}`;
      $("#status").classList.add("ok");
    } else {
      $("#auth-banner").classList.remove("hidden");
      $("#status").textContent = "not signed in";
    }
  } catch { $("#status").textContent = "offline"; }

  try {
    const courses = await api("/api/courses");
    const ul = $("#course-list");
    courses.forEach((c) => {
      const li = el("li", null, c.name || `Course ${c.id}`);
      li.onclick = () => selectCourse(c, li);
      ul.appendChild(li);
    });
  } catch (e) { /* banner already shown */ }

  document.querySelectorAll(".tabs button").forEach((b) => {
    b.onclick = () => switchTab(b.dataset.tab, b);
  });
  $("#chat-send").onclick = sendChat;
  $("#chat-text").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) sendChat();
  });
  $("#modal-cancel").onclick = closeModal;
}

function switchTab(name, btn) {
  document.querySelectorAll(".tabs button").forEach((b) => b.classList.remove("active"));
  btn.classList.add("active");
  document.querySelectorAll(".tab").forEach((t) => t.classList.add("hidden"));
  $("#tab-" + name).classList.remove("hidden");
  if (name === "dashboard") loadDashboard();
  if (name === "discussions") loadDiscussions();
}

function selectCourse(c, li) {
  activeCourse = c;
  document.querySelectorAll("#course-list li").forEach((x) => x.classList.remove("active"));
  li.classList.add("active");
  loadModules();
  const active = document.querySelector(".tabs button.active").dataset.tab;
  if (active === "discussions") loadDiscussions();
}

// ---- modules ----
async function loadModules() {
  const box = $("#tab-modules");
  box.innerHTML = `<p class="muted">Loading modules…</p>`;
  try {
    const mods = await api(`/api/modules?course_id=${activeCourse.id}`);
    box.innerHTML = "";
    if (!mods.length) box.innerHTML = `<p class="muted">No modules in this course.</p>`;
    mods.forEach((m) => {
      const div = el("div", "module");
      div.appendChild(el("h3", null, m.name || "Module"));
      (m.items || []).forEach((it) => {
        const row = el("div", "item");
        row.appendChild(el("span", "kind", it.type || ""));
        row.appendChild(el("span", null, it.title || ""));
        row.onclick = () => openItem(it);
        div.appendChild(row);
      });
      box.appendChild(div);
    });
  } catch (e) { box.innerHTML = `<p class="muted">${e.message}</p>`; }
}

async function openItem(it) {
  if (it.type === "Page" && it.page_url) return openPage(it.page_url);
  if (it.type === "Assignment" && it.content_id) return openAssignment(it.content_id, it.title);
  // Fallback: link out for files / quizzes / external tools.
  showReader(it.title || "Item",
    `<p class="muted">This item type (${it.type}) opens in Canvas.</p>` +
    (it.html_url ? `<p><a href="${it.html_url}" target="_blank">Open in Canvas ↗</a></p>` : ""));
}

async function openPage(pageUrl) {
  showReader("Loading…", "");
  try {
    const p = await api(`/api/page?course_id=${activeCourse.id}&page_url=${encodeURIComponent(pageUrl)}`);
    showReader(p.title || "Page", `<div class="body">${p.html || "<em>empty</em>"}</div>`);
  } catch (e) { showReader("Error", `<p class="muted">${e.message}</p>`); }
}

async function openAssignment(aid, title) {
  showReader("Loading…", "");
  try {
    const a = await api(`/api/assignment?course_id=${activeCourse.id}&assignment_id=${aid}`);
    const body = el("div");
    body.appendChild(el("div", "body", a.description || "<em>No description</em>"));
    body.appendChild(el("p", "muted", a.due_at ? "Due: " + fmt(a.due_at) : "No due date"));
    body.appendChild(el("p", null, "<strong>Your submission (text)</strong>"));
    const ta = el("textarea"); ta.rows = 8; ta.id = "subtext";
    body.appendChild(ta);
    const row = el("div", "row");
    const draftBtn = el("button", "ghost", "Draft with AI");
    const subBtn = el("button", "primary", "Submit…");
    draftBtn.onclick = async () => {
      draftBtn.disabled = true; draftBtn.textContent = "Drafting…";
      try {
        const r = await api("/api/agent", { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ goal: `Draft a response for the assignment "${a.name}" in course ${activeCourse.id}. Assignment description: ${strip(a.description)}` }) });
        ta.value = r.answer;
      } catch (e) { alert(e.message); }
      draftBtn.disabled = false; draftBtn.textContent = "Draft with AI";
    };
    subBtn.onclick = () => confirmSubmit(aid, a.name, ta);
    row.appendChild(draftBtn); row.appendChild(subBtn);
    body.appendChild(row);
    showReaderNode(a.name || title || "Assignment", body);
  } catch (e) { showReader("Error", `<p class="muted">${e.message}</p>`); }
}

function confirmSubmit(aid, name, ta) {
  const text = ta.value.trim();
  if (!text) { alert("Nothing to submit yet."); return; }
  openModal("Submit graded work?",
    `You are about to SUBMIT to "${name}" as yourself. This counts as your graded work.\n\n` +
    `Preview:\n${text.slice(0, 600)}`,
    async () => {
      await api("/api/assignment/submit", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ course_id: activeCourse.id, assignment_id: aid, body: text, confirm: true }) });
      closeModal();
      showReader("Submitted", `<p class="muted">Submitted to "${name}".</p>`);
    });
}

// ---- dashboard ----
async function loadDashboard() {
  const box = $("#tab-dashboard");
  box.innerHTML = `<p class="muted">Loading due dates across your courses…</p>`;
  try {
    const rows = await api("/api/dashboard");
    if (!rows.length) { box.innerHTML = `<p class="muted">Nothing with a due date.</p>`; return; }
    let html = "<table><thead><tr><th>Due</th><th>Assignment</th><th>Course</th><th>Status</th></tr></thead><tbody>";
    rows.forEach((r) => {
      html += `<tr><td>${fmt(r.due_at)}</td><td>${r.name}</td><td class="muted">${r.course || ""}</td>` +
        `<td><span class="pill ${r.submitted ? "done" : "todo"}">${r.submitted ? "submitted" : "to do"}</span></td></tr>`;
    });
    box.innerHTML = html + "</tbody></table>";
  } catch (e) { box.innerHTML = `<p class="muted">${e.message}</p>`; }
}

// ---- discussions ----
async function loadDiscussions() {
  const box = $("#tab-discussions");
  if (!activeCourse) { box.innerHTML = `<p class="muted">Pick a course first.</p>`; return; }
  box.innerHTML = `<p class="muted">Loading discussions…</p>`;
  try {
    const list = await api(`/api/discussions?course_id=${activeCourse.id}`);
    box.innerHTML = "";
    if (!list.length) box.innerHTML = `<p class="muted">No discussions.</p>`;
    list.forEach((d) => {
      const row = el("div", "item", `<span>${d.title || "Discussion"}</span>`);
      row.onclick = () => openDiscussion(d.id);
      box.appendChild(row);
    });
  } catch (e) { box.innerHTML = `<p class="muted">${e.message}</p>`; }
}

async function openDiscussion(tid) {
  showReader("Loading…", "");
  try {
    const d = await api(`/api/discussion?course_id=${activeCourse.id}&topic_id=${tid}`);
    const node = el("div");
    node.appendChild(el("div", "body", d.message || ""));
    node.appendChild(el("p", null, "<strong>Replies</strong>"));
    (d.entries || []).forEach((e) => {
      const ent = el("div", "entry");
      ent.appendChild(el("div", "who", "User " + (e.user_id || "")));
      ent.appendChild(el("div", null, e.message || ""));
      node.appendChild(ent);
    });
    node.appendChild(el("p", null, "<strong>Your reply</strong>"));
    const ta = el("textarea"); ta.rows = 4; node.appendChild(ta);
    const row = el("div", "row");
    const draftBtn = el("button", "ghost", "Draft with AI");
    const postBtn = el("button", "primary", "Post reply…");
    draftBtn.onclick = async () => {
      draftBtn.disabled = true; draftBtn.textContent = "Drafting…";
      try {
        const r = await api("/api/agent", { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ goal: `Draft a thoughtful discussion reply for topic ${tid} in course ${activeCourse.id}. Prompt: ${strip(d.message)}` }) });
        ta.value = r.answer;
      } catch (e) { alert(e.message); }
      draftBtn.disabled = false; draftBtn.textContent = "Draft with AI";
    };
    postBtn.onclick = () => {
      const msg = ta.value.trim();
      if (!msg) { alert("Write or draft a reply first."); return; }
      openModal("Post this reply?", msg, async () => {
        await api("/api/discussion/reply", { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ course_id: activeCourse.id, topic_id: tid, message: msg }) });
        closeModal(); ta.value = ""; openDiscussion(tid);
      });
    };
    row.appendChild(draftBtn); row.appendChild(postBtn); node.appendChild(row);
    showReaderNode(d.title || "Discussion", node);
  } catch (e) { showReader("Error", `<p class="muted">${e.message}</p>`); }
}

// ---- chat ----
async function sendChat() {
  const ta = $("#chat-text");
  const goal = ta.value.trim();
  if (!goal) return;
  addMsg("user", goal);
  ta.value = "";
  const thinking = addMsg("sys", "thinking…");
  try {
    const r = await api("/api/agent", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ goal }) });
    thinking.remove();
    addMsg("ai", r.answer);
  } catch (e) { thinking.remove(); addMsg("sys", "Error: " + e.message); }
}

function addMsg(kind, text) {
  const m = el("div", "msg " + kind, escapeHtml(text));
  $("#chat-log").appendChild(m);
  $("#chat-log").scrollTop = $("#chat-log").scrollHeight;
  return m;
}

// ---- reader + modal ----
function showReader(title, html) {
  const r = $("#reader");
  r.classList.remove("hidden");
  r.innerHTML = `<span class="close" onclick="document.getElementById('reader').classList.add('hidden')">✕ close</span><h2>${escapeHtml(title)}</h2>${html}`;
}
function showReaderNode(title, node) {
  showReader(title, "");
  $("#reader").appendChild(node);
}
let modalAction = null;
function openModal(title, body, onok) {
  $("#modal-title").textContent = title;
  $("#modal-body").textContent = body;
  modalAction = onok;
  $("#modal").classList.remove("hidden");
  $("#modal-ok").onclick = async () => { try { await modalAction(); } catch (e) { alert(e.message); } };
}
function closeModal() { $("#modal").classList.add("hidden"); }

// ---- utils ----
function fmt(iso) { try { return new Date(iso).toLocaleString(); } catch { return iso; } }
function strip(html) { const d = el("div", null, html || ""); return (d.textContent || "").slice(0, 1500); }
function escapeHtml(s) { const d = document.createElement("div"); d.textContent = s == null ? "" : s; return d.innerHTML; }

init();
