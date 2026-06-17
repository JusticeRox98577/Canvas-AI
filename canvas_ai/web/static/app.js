const $ = (s) => document.querySelector(s);
const el = (t, c, h) => { const e = document.createElement(t); if (c) e.className = c; if (h != null) e.innerHTML = h; return e; };
let activeCourse = null;
let appConfig = { auto_submit: false, write_mode: "dry_run" };

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

  try { appConfig = await api("/api/config"); } catch { /* keep defaults */ }

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
  if (active === "dashboard") loadDashboard();
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
  switch (it.type) {
    case "Page": return openPage(it.page_url);
    case "Assignment": return openAssignment(it.content_id, it.title);
    case "Discussion": return openDiscussion(it.content_id);
    case "File": return openFile(it.content_id, it.title);
    case "Quiz": return openQuiz(it.content_id, it.title);
    case "ExternalUrl":
    case "ExternalTool":
      return openExternal(it.external_url || it.html_url, it.title);
    case "SubHeader":
      return; // headers aren't openable
    default:
      return openExternal(it.html_url, it.title);
  }
}

async function openFile(fileId, title) {
  showReader("Loading…", "");
  try {
    const m = await api(`/api/file?file_id=${fileId}`);
    const ct = (m.content_type || "").toLowerCase();
    if (ct.includes("pdf")) {
      showReader(m.display_name || title, `<iframe src="/api/file/raw?file_id=${fileId}" style="width:100%;height:75vh;border:0;border-radius:8px"></iframe>`);
    } else if (ct.startsWith("image/")) {
      showReader(m.display_name || title, `<img src="/api/file/raw?file_id=${fileId}" />`);
    } else {
      const t = await api(`/api/file/text?file_id=${fileId}`);
      const node = el("div");
      node.appendChild(el("pre", "body", escapeHtml(t.text || "(no extractable text)")));
      const btn = el("button", "ghost", "Explain with AI");
      btn.onclick = async () => {
        btn.disabled = true; btn.textContent = "Thinking…";
        try {
          const r = await api("/api/agent", { method: "POST", headers: { "Content-Type": "application/json" },
            body: agentBody(`Explain this document in simple terms:\n\n${(t.text || "").slice(0, 4000)}`) });
          node.appendChild(el("div", "msg ai", escapeHtml(r.answer)));
        } catch (e) { alert(e.message); }
        btn.disabled = false; btn.textContent = "Explain with AI";
      };
      node.appendChild(btn);
      showReaderNode(t.display_name || title, node);
    }
  } catch (e) { showReader("Error", `<p class="muted">${escapeHtml(e.message)}</p>`); }
}

async function openExternal(url, title) {
  if (!url) return showReader(title || "Item", `<p class="muted">No link available.</p>`);
  showReader(title || "External", `
    <iframe src="${url}" style="width:100%;height:75vh;border:0;border-radius:8px"></iframe>
    <p class="muted">If this stays blank, the site blocks embedding —
      <a href="${url}" target="_blank">open it in a new tab ↗</a>.</p>`);
}

async function openQuiz(quizId, title) {
  showReader("Loading…", "");
  try {
    const q = await api(`/api/quiz?course_id=${activeCourse.id}&quiz_id=${quizId}`);
    const node = el("div");
    node.appendChild(el("div", "body", q.description || "<em>No description</em>"));
    const meta = [
      q.points_possible != null ? `Points: ${q.points_possible}` : null,
      q.question_count != null ? `Questions: ${q.question_count}` : null,
      q.time_limit ? `Time limit: ${q.time_limit} min` : null,
      q.due_at ? `Due: ${fmt(q.due_at)}` : null,
      q.allowed_attempts != null ? `Attempts: ${q.allowed_attempts < 0 ? "unlimited" : q.allowed_attempts}` : null,
    ].filter(Boolean).join(" · ");
    node.appendChild(el("p", "muted", meta));
    node.appendChild(el("p", "muted",
      "Quizzes are taken in Canvas — the AI won't auto-answer graded work. " +
      "Use Study mode below to actually learn the material."));
    const row = el("div", "row");
    const study = el("button", "ghost", "Study this with AI");
    const open = el("button", "primary", "Open quiz in Canvas ↗");
    study.onclick = async () => {
      study.disabled = true; study.textContent = "Thinking…";
      try {
        const r = await api("/api/agent", { method: "POST", headers: { "Content-Type": "application/json" },
          body: agentBody(`I have a quiz titled "${q.title}". Based on this course's material, explain the key concepts I should understand to do well. Quiz description: ${strip(q.description)}`) });
        node.appendChild(el("div", "msg ai", escapeHtml(r.answer)));
      } catch (e) { alert(e.message); }
      study.disabled = false; study.textContent = "Study this with AI";
    };
    open.onclick = () => { if (q.html_url) window.open(q.html_url, "_blank"); };
    row.appendChild(study); row.appendChild(open);
    node.appendChild(row);
    showReaderNode(q.title || title || "Quiz", node);
  } catch (e) { showReader("Error", `<p class="muted">${escapeHtml(e.message)}</p>`); }
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
    const doBtn = el("button", "primary", appConfig.auto_submit ? "Do it for me ✨" : "Do it for me…");
    draftBtn.onclick = async () => {
      draftBtn.disabled = true; draftBtn.textContent = "Drafting…";
      try {
        const r = await api("/api/agent", { method: "POST", headers: { "Content-Type": "application/json" },
          body: agentBody(`Draft a response for the assignment "${a.name}". Assignment description: ${strip(a.description)}`) });
        ta.value = r.answer;
      } catch (e) { alert(e.message); }
      draftBtn.disabled = false; draftBtn.textContent = "Draft with AI";
    };
    subBtn.onclick = () => confirmSubmit(aid, a.name, ta);
    doBtn.onclick = () => doAssignment(aid, a.name, ta, doBtn);
    row.appendChild(draftBtn); row.appendChild(doBtn); row.appendChild(subBtn);
    body.appendChild(row);
    showReaderNode(a.name || title || "Assignment", body);
  } catch (e) { showReader("Error", `<p class="muted">${e.message}</p>`); }
}

// One-click: AI writes the whole submission, then submits it. When AUTO_SUBMIT
// is on it submits directly; otherwise it drafts and shows the confirm dialog.
async function doAssignment(aid, name, ta, btn) {
  const label = btn.textContent;
  btn.disabled = true; btn.textContent = appConfig.auto_submit ? "Doing it…" : "Drafting…";
  try {
    const r = await api("/api/assignment/do", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ course_id: activeCourse.id, assignment_id: aid, submit: appConfig.auto_submit }) });
    ta.value = r.draft || "";
    if (r.submitted) {
      showReader("Submitted", `<p class="muted">Done — submitted your work to "${escapeHtml(name)}".</p>` +
        `<div class="body"><pre class="body">${escapeHtml(r.draft || "")}</pre></div>`);
    } else {
      // Not in auto mode: review is required, so jump straight to the confirm step.
      confirmSubmit(aid, name, ta);
    }
  } catch (e) { alert(e.message); }
  btn.disabled = false; btn.textContent = label;
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
let dashAll = false;

function dashHeader(scoped) {
  const note = scoped ? `Showing: ${activeCourse.name}` : "Showing: all courses";
  return `<div class="row" style="justify-content:space-between;align-items:center;margin-bottom:8px">
      <span class="muted">${escapeHtml(note)}</span>
      <label class="muted" style="cursor:pointer">
        <input type="checkbox" id="dashall" ${dashAll ? "checked" : ""}/> All courses
      </label>
    </div>`;
}
function bindDash() {
  const cb = $("#dashall");
  if (cb) cb.onchange = (e) => { dashAll = e.target.checked; loadDashboard(); };
}

async function loadDashboard() {
  const box = $("#tab-dashboard");
  const scoped = activeCourse && !dashAll;
  box.innerHTML = dashHeader(scoped) + `<p class="muted">Loading due dates…</p>`;
  bindDash();
  try {
    const q = scoped ? `?course_id=${activeCourse.id}` : "";
    const rows = await api("/api/dashboard" + q);
    let body;
    if (!rows.length) {
      body = `<p class="muted">Nothing with a due date.</p>`;
    } else {
      body = "<table><thead><tr><th>Due</th><th>Assignment</th><th>Course</th><th>Status</th></tr></thead><tbody>";
      rows.forEach((r) => {
        body += `<tr><td>${fmt(r.due_at)}</td><td>${escapeHtml(r.name)}</td><td class="muted">${escapeHtml(r.course || "")}</td>` +
          `<td><span class="pill ${r.submitted ? "done" : "todo"}">${r.submitted ? "submitted" : "to do"}</span></td></tr>`;
      });
      body += "</tbody></table>";
    }
    box.innerHTML = dashHeader(scoped) + body;
    bindDash();
  } catch (e) { box.innerHTML = dashHeader(scoped) + `<p class="muted">${escapeHtml(e.message)}</p>`; bindDash(); }
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
          body: agentBody(`Draft a thoughtful discussion reply for topic ${tid}. Prompt: ${strip(d.message)}`) });
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
function agentBody(goal) {
  return JSON.stringify({
    goal,
    course_id: activeCourse ? activeCourse.id : null,
    course_name: activeCourse ? activeCourse.name : null,
  });
}

async function sendChat() {
  const ta = $("#chat-text");
  const goal = ta.value.trim();
  if (!goal) return;
  if (!activeCourse) addMsg("sys", "Tip: pick a course on the left so I use real data.");
  addMsg("user", goal);
  ta.value = "";
  const thinking = addMsg("sys", "thinking…");
  try {
    const r = await api("/api/agent", { method: "POST", headers: { "Content-Type": "application/json" },
      body: agentBody(goal) });
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
