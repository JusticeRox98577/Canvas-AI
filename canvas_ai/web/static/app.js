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
  // License gate (only active when the build requires a license).
  try {
    const lic = await api("/api/license/status");
    if (lic.required && !lic.activated) { showLicenseGate(); return; }
  } catch { /* ignore */ }

  // Update banner (only if UPDATE_URL is configured and a newer version exists).
  try {
    const u = await api("/api/update");
    if (u.update_available) showUpdateBanner(u);
  } catch { /* ignore */ }

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
  // First run: if anything's unconfigured, launch the guided setup wizard.
  try {
    const st = await api("/api/setup/status");
    if (!st.brain_ready || !st.canvas_base_url || !st.canvas_authenticated) {
      wizStep = 0; showOnboarding();
    }
  } catch { /* ignore */ }

  $("#chat-send").onclick = sendChat;
  $("#chat-text").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) sendChat();
  });
  $("#modal-cancel").onclick = closeModal;
}

function switchTab(name, btn) {
  btn = btn || document.querySelector(`.tabs button[data-tab="${name}"]`);
  document.querySelectorAll(".tabs button").forEach((b) => b.classList.remove("active"));
  if (btn) btn.classList.add("active");
  document.querySelectorAll(".tab").forEach((t) => t.classList.add("hidden"));
  $("#tab-" + name).classList.remove("hidden");
  if (name === "dashboard") loadDashboard();
  if (name === "discussions") loadDiscussions();
  if (name === "settings") loadSettings();
  if (name === "setup") loadSetup();
  if (name === "study") loadStudy();
}

// ---- study mode ----
async function loadStudy() {
  const box = $("#tab-study");
  if (!activeCourse) { box.innerHTML = `<p class="muted">Pick a course on the left, then study it here.</p>`; return; }
  box.innerHTML = "";
  box.appendChild(el("p", "muted", `Study help for ${escapeHtml(activeCourse.name || "this course")} — grounded in your real course material.`));
  const topic = el("input"); topic.placeholder = "Optional: focus on a topic, module, or page";
  box.appendChild(topic);
  const out = el("div"); out.style.marginTop = "12px";
  const mk = (label, goalFn) => {
    const b = el("button", "ghost", label);
    b.onclick = () => runStudy(goalFn(topic.value.trim()), b, out);
    return b;
  };
  const row = el("div", "row");
  row.appendChild(mk("Quiz me", (t) => `Write 5 practice quiz questions to test my understanding${t ? " of " + t : ""} in this course, then an answer key at the end. Base them on the course material.`));
  row.appendChild(mk("Flashcards", (t) => `Make 8 flashcards as "Term — Definition" for the key concepts${t ? " in " + t : ""} in this course.`));
  row.appendChild(mk("Explain concepts", (t) => `Explain the most important concepts I should understand${t ? " about " + t : ""} in this course, in simple plain terms.`));
  row.appendChild(mk("Summarize", (t) => `Give me a concise review summary of the key points${t ? " of " + t : ""} in this course.`));
  box.appendChild(row);
  box.appendChild(out);
}

async function runStudy(goal, btn, out) {
  const label = btn.textContent; btn.disabled = true; btn.textContent = "Thinking…";
  out.innerHTML = `<p class="muted">Working from your course material…</p>`;
  try {
    const r = await api("/api/agent", { method: "POST", headers: { "Content-Type": "application/json" }, body: agentBody(goal) });
    out.innerHTML = ""; out.appendChild(el("div", "msg ai", escapeHtml(r.answer)));
  } catch (e) { out.innerHTML = `<p class="muted">${escapeHtml(e.message)}</p>`; }
  btn.disabled = false; btn.textContent = label;
}

// ---- setup (first run) ----
async function loadSetup() {
  const box = $("#tab-setup");
  box.innerHTML = `<p class="muted">Checking setup…</p>`;
  let s;
  try { s = await api("/api/setup/status"); } catch (e) { box.innerHTML = `<p class="muted">${escapeHtml(e.message)}</p>`; return; }
  box.innerHTML = "";
  const wrap = el("div", "settings-form");
  wrap.appendChild(el("h2", null, "Setup"));

  const step = (ok, title, body) => {
    const d = el("div", "field");
    d.appendChild(el("div", null, `<strong>${ok ? "✓" : "•"} ${escapeHtml(title)}</strong>`));
    if (body) d.appendChild(body);
    wrap.appendChild(d);
    return d;
  };

  // 1. Pick the AI brain
  const pickBody = el("div");
  pickBody.appendChild(el("p", "muted",
    "Claude = your Claude Pro/Max subscription · Ollama = free local model · Anthropic = API key (paid)."));
  const pick = selectEl(["claude_code", "ollama", "anthropic"], s.llm_provider);
  pick.onchange = async () => {
    try { await api("/api/setup/provider", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ provider: pick.value }) }); loadSetup(); appConfig = await api("/api/config"); }
    catch (e) { alert(e.message); }
  };
  pickBody.appendChild(pick);
  step(s.brain_ready, "AI brain", pickBody);

  // 1a. Provider-specific setup
  if (s.llm_provider === "claude_code") {
    const body = el("div");
    if (s.claude_installed) {
      body.appendChild(el("p", "muted", "Claude Code is installed. If answers fail, log in once below."));
    } else {
      body.appendChild(el("p", "muted", "Uses your Claude subscription via Claude Code, which isn't installed yet."));
      if (s.platform === "win32") {
        const ib = el("button", "primary", "Install Claude Code");
        ib.onclick = async () => {
          ib.disabled = true; ib.textContent = "Installing… (a minute or two)";
          try { const r = await api("/api/setup/install_claude", { method: "POST" }); ib.textContent = r.ok ? "Installed ✓" : "Install ran — re-check"; }
          catch (e) { alert(e.message); ib.textContent = "Install Claude Code"; }
          ib.disabled = false; loadSetupSoon();
        };
        body.appendChild(ib);
      } else {
        body.appendChild(el("p", "muted", "Install from https://claude.ai/install then re-check."));
      }
    }
    const lb = el("button", "ghost", "Log in to Claude");
    lb.onclick = async () => { try { await api("/api/setup/claude_login", { method: "POST" }); alert("A window opened — finish the Claude login there, choosing Subscription."); } catch (e) { alert(e.message); } };
    body.appendChild(lb);
    step(s.claude_installed, "Claude Code", body);

  } else if (s.llm_provider === "ollama") {
    const body = el("div");
    if (s.ollama_running) {
      body.appendChild(el("p", "muted", `Ollama is running (model: ${escapeHtml(s.ollama_model)}).`));
    } else {
      body.appendChild(el("p", "muted", "Free local model. Needs Ollama installed and a model pulled (a few GB)."));
      if (s.platform === "win32") {
        const ib = el("button", "primary", `Install Ollama + ${escapeHtml(s.ollama_model)}`);
        ib.onclick = async () => {
          ib.disabled = true; ib.textContent = "Installing + downloading model… (can take a while)";
          try { const r = await api("/api/setup/install_ollama", { method: "POST" }); ib.textContent = r.ok ? "Ready ✓" : "Ran — re-check"; }
          catch (e) { alert(e.message); ib.textContent = "Install Ollama"; }
          ib.disabled = false; loadSetupSoon();
        };
        body.appendChild(ib);
      } else {
        body.appendChild(el("p", "muted", "Install from https://ollama.com/download, then run: ollama pull " + escapeHtml(s.ollama_model)));
      }
    }
    step(s.ollama_running, "Local model (Ollama)", body);

  } else if (s.llm_provider === "anthropic") {
    const body = el("div");
    body.appendChild(el("p", "muted", "Paid Anthropic API. Get a key at https://console.anthropic.com."));
    const key = el("input"); key.type = "password"; key.placeholder = s.anthropic_key_set ? "key saved — paste to replace" : "sk-ant-…";
    const model = el("input"); model.value = s.anthropic_model || "";
    body.appendChild(el("label", null, "API key")); body.appendChild(key);
    body.appendChild(el("label", null, "Model")); body.appendChild(model);
    const sb = el("button", "primary", "Save API key");
    sb.onclick = async () => {
      sb.disabled = true;
      try {
        const payload = { anthropic_model: model.value.trim() };
        if (key.value.trim()) payload.anthropic_api_key = key.value.trim();
        await api("/api/settings", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
        loadSetup();
      } catch (e) { alert(e.message); }
      sb.disabled = false;
    };
    body.appendChild(sb);
    step(s.anthropic_key_set, "Anthropic API key", body);
  }

  // 2. Canvas URL — set it right here (sign-in needs it first)
  const urlBody = el("div");
  urlBody.appendChild(el("p", "muted", "Current: " + escapeHtml(s.canvas_base_url || "(not set)")));
  const urlInput = el("input"); urlInput.placeholder = "https://yourschool.instructure.com"; urlInput.value = s.canvas_base_url || "";
  urlBody.appendChild(urlInput);
  const urlRow = el("div", "row");
  const urlSave = el("button", "primary", "Save URL");
  const urlMsg = el("span", "muted", "");
  urlSave.onclick = async () => {
    const v = urlInput.value.trim();
    if (!/^https?:\/\//.test(v)) { urlMsg.textContent = "Enter a full URL starting with https://"; return; }
    urlSave.disabled = true; urlMsg.textContent = "Saving…";
    try { await api("/api/settings", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ canvas_base_url: v }) }); loadSetup(); }
    catch (e) { urlMsg.textContent = e.message; }
    urlSave.disabled = false;
  };
  urlRow.appendChild(urlSave); urlRow.appendChild(urlMsg); urlBody.appendChild(urlRow);
  step(!!s.canvas_base_url, "Your Canvas URL", urlBody);

  // 3. Canvas sign-in (needs a URL first)
  const cbody = el("div");
  if (s.canvas_authenticated) {
    cbody.appendChild(el("p", "muted", "Signed in to Canvas."));
  } else if (!s.canvas_base_url) {
    cbody.appendChild(el("p", "muted", "Set your Canvas URL above first, then sign in."));
  } else {
    const cb = el("button", "primary", "Sign in to Canvas");
    cb.onclick = async () => {
      cb.disabled = true; cb.textContent = "Opening sign-in…";
      try { await api("/api/setup/canvas_login", { method: "POST" }); alert("A browser window is opening — sign in to your school, then click Re-check."); }
      catch (e) { alert(e.message); }
      cb.disabled = false; cb.textContent = "Sign in to Canvas";
    };
    cbody.appendChild(cb);
  }
  step(s.canvas_authenticated, "Canvas sign-in", cbody);

  const recheck = el("button", "ghost", "Re-check");
  recheck.onclick = () => loadSetup();
  wrap.appendChild(recheck);
  box.appendChild(wrap);
}
function loadSetupSoon() { setTimeout(loadSetup, 1500); }

// ---- settings ----
function selectEl(opts, val) {
  const s = el("select");
  opts.forEach((o) => { const op = el("option", null, o); op.value = o; if (o === val) op.selected = true; s.appendChild(op); });
  return s;
}

async function loadSettings() {
  const box = $("#tab-settings");
  box.innerHTML = `<p class="muted">Loading settings…</p>`;
  let s;
  try { s = await api("/api/settings"); } catch (e) { box.innerHTML = `<p class="muted">${escapeHtml(e.message)}</p>`; return; }
  box.innerHTML = "";
  const form = el("div", "settings-form");
  const field = (label, node, hint) => {
    const w = el("div", "field");
    w.appendChild(el("label", null, label));
    w.appendChild(node);
    if (hint) w.appendChild(el("div", "muted", hint));
    form.appendChild(w);
    return node;
  };

  const url = field("Canvas URL", el("input"), "e.g. https://yourschool.instructure.com");
  url.value = s.canvas_base_url || "";
  const llm = field("Brain (chat & quizzes)", selectEl(["claude_code", "ollama", "anthropic"], s.llm_provider));
  const draft = field("Drafting brain", selectEl(["claude_code", "ollama", "anthropic"], s.draft_provider));
  const model = field("Claude model (optional)", el("input"), "blank = your subscription default");
  model.value = s.claude_code_model || "";
  const wm = field("Write mode", selectEl(["dry_run", "confirm", "auto"], s.write_mode));
  const allow = el("input"); allow.type = "checkbox"; allow.checked = !!s.allow_submit;
  const allowWrap = el("label", "checkrow"); allowWrap.appendChild(allow);
  allowWrap.appendChild(document.createTextNode(" Allow submitting graded work (off = study only)"));
  const allowField = el("div", "field"); allowField.appendChild(allowWrap);
  allowField.appendChild(el("div", "muted", "When off, Canvas-AI only helps you read, study, and draft — no submit/auto-do buttons appear."));
  form.appendChild(allowField);
  const auto = el("input"); auto.type = "checkbox"; auto.checked = !!s.auto_submit;
  const autoWrap = el("label", "checkrow"); autoWrap.appendChild(auto); autoWrap.appendChild(document.createTextNode(" Auto-submit graded work (skip the confirm dialog)"));
  const af = el("div", "field"); af.appendChild(autoWrap); form.appendChild(af);
  const voiceTa = field("Your writing voice (sample)", el("textarea"), "Paste a few paragraphs you wrote; drafts will match your style.");
  voiceTa.rows = 8; voiceTa.value = s.writing_sample || "";

  const save = el("button", "primary", "Save settings");
  const status = el("span", "muted", "");
  save.onclick = async () => {
    save.disabled = true; status.textContent = "Saving…";
    try {
      await api("/api/settings", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          canvas_base_url: url.value.trim(), llm_provider: llm.value, draft_provider: draft.value,
          claude_code_model: model.value.trim(), write_mode: wm.value, auto_submit: auto.checked,
          allow_submit: allow.checked, writing_sample: voiceTa.value,
        }) });
      status.textContent = "Saved ✓";
      appConfig = await api("/api/config");
    } catch (e) { status.textContent = "Error: " + e.message; }
    save.disabled = false;
  };
  const row = el("div", "row"); row.appendChild(save); row.appendChild(status);
  form.appendChild(row);
  if (s.settings_path) form.appendChild(el("p", "muted", "Saved to: " + s.settings_path));
  box.appendChild(form);
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
      appConfig.allow_submit
        ? "“Study this with AI” explains what to learn. (Submitting is enabled in Settings.)"
        : "Use “Study this with AI” to learn the material. Open the quiz in Canvas to take it."));
    const row = el("div", "row");
    const doBtn = el("button", "primary", appConfig.auto_submit ? "Do quiz for me ✨" : "Do quiz with AI…");
    const study = el("button", "ghost", "Study this with AI");
    const open = el("button", "ghost", "Open quiz in Canvas ↗");
    doBtn.onclick = () => doQuiz(quizId, q.title, node, doBtn);
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
    if (appConfig.allow_submit) row.appendChild(doBtn);
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
        const r = await api("/api/draft", { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ goal: `Write my response to this assignment, in first person. Assignment: "${a.name}". Instructions: ${strip(a.description)}` }) });
        ta.value = r.answer;
      } catch (e) { alert(e.message); }
      draftBtn.disabled = false; draftBtn.textContent = "Draft with AI";
    };
    subBtn.onclick = () => confirmSubmit(aid, a.name, ta);
    doBtn.onclick = () => doAssignment(aid, a.name, ta, doBtn);
    row.appendChild(draftBtn);
    if (appConfig.allow_submit) { row.appendChild(doBtn); row.appendChild(subBtn); }
    body.appendChild(row);
    showReaderNode(a.name || title || "Assignment", body);
  } catch (e) { showReader("Error", `<p class="muted">${e.message}</p>`); }
}

// Quiz: start an attempt, let the AI answer, show answers for review, then
// submit only on confirm (or immediately when AUTO_SUBMIT is on).
async function doQuiz(quizId, title, node, btn) {
  const label = btn.textContent;
  btn.disabled = true; btn.textContent = "Answering…";
  try {
    const r = await api("/api/quiz/answer", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ course_id: activeCourse.id, quiz_id: quizId }) });

    const panel = el("div", "entry");
    if (r.note) panel.appendChild(el("p", "muted", escapeHtml(r.note)));
    panel.appendChild(el("p", null, `<strong>AI answers (${r.answered.length}/${r.total})</strong>`));
    r.answered.forEach((a, i) => {
      const item = el("div", "item");
      item.appendChild(el("span", "kind", a.type ? a.type.replace(/_question$/, "") : ""));
      item.appendChild(el("span", null, `<strong>Q${i + 1}.</strong> ${escapeHtml(a.question)} <br/>→ ${escapeHtml(a.answer)}`));
      panel.appendChild(item);
    });
    if (r.skipped && r.skipped.length) {
      panel.appendChild(el("p", "muted", `Couldn't auto-answer ${r.skipped.length} question(s) — answer those in Canvas before submitting.`));
    }
    if (r.debug && r.debug.length) {
      panel.appendChild(el("pre", "body", "diagnostics:\n" + r.debug.map(escapeHtml).join("\n")));
    }
    const subBtn = el("button", "primary", appConfig.auto_submit ? "Submitting…" : "Submit quiz…");
    subBtn.onclick = () => submitQuiz(quizId, title, r.submission_id);
    panel.appendChild(subBtn);
    node.appendChild(panel);

    if (appConfig.auto_submit) {
      await submitQuiz(quizId, title, r.submission_id, true);
    }
  } catch (e) { alert(e.message); }
  btn.disabled = false; btn.textContent = label;
}

async function submitQuiz(quizId, title, submissionId, skipModal) {
  const send = async () => {
    const res = await api("/api/quiz/submit", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ course_id: activeCourse.id, quiz_id: quizId, submission_id: submissionId, confirm: true }) });
    const score = res.score != null ? `Score: ${res.score}` : "Submitted.";
    showReader("Quiz submitted", `<p class="muted">Turned in "${escapeHtml(title)}". ${escapeHtml(score)}</p>`);
  };
  if (skipModal) { await send(); return; }
  openModal("Submit this quiz?",
    `You are about to TURN IN "${title}" as your graded attempt. Review the answers above first.`,
    async () => { await send(); closeModal(); });
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
    const who = d.participants || {};
    const node = el("div");
    node.appendChild(el("div", "body", d.message || ""));
    const entries = (d.entries || []).filter((e) => !e.deleted);
    node.appendChild(el("p", null, `<strong>Replies (${entries.length})</strong>`));
    if (!entries.length) node.appendChild(el("p", "muted", "No one has posted yet — nobody to reply to."));
    entries.forEach((e) => {
      const name = who[String(e.user_id)] || ("User " + (e.user_id || ""));
      const ent = el("div", "entry");
      ent.appendChild(el("div", "who", escapeHtml(name)));
      ent.appendChild(el("div", "body", e.message || ""));

      // Per-person reply box
      const ta = el("textarea"); ta.rows = 3; ta.placeholder = `Reply to ${name}…`;
      const row = el("div", "row");
      const draftBtn = el("button", "ghost", "Reply with AI");
      const postBtn = el("button", "primary", "Post reply…");
      draftBtn.onclick = async () => {
        draftBtn.disabled = true; draftBtn.textContent = "Drafting…";
        try {
          const r = await api("/api/draft", { method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ goal: `Write my reply (2-4 sentences) to my classmate ${name}'s discussion post, in first person. Respond to a specific point they made and add my own thought; keep it friendly and genuine. Their post: ${strip(e.message)}` }) });
          ta.value = r.answer;
        } catch (err) { alert(err.message); }
        draftBtn.disabled = false; draftBtn.textContent = "Reply with AI";
      };
      postBtn.onclick = () => {
        const msg = ta.value.trim();
        if (!msg) { alert("Write or draft a reply first."); return; }
        openModal(`Reply to ${name}?`, msg, async () => {
          await api("/api/discussion/reply", { method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ course_id: activeCourse.id, topic_id: tid, entry_id: e.id, message: msg }) });
          closeModal(); openDiscussion(tid);
        });
      };
      row.appendChild(draftBtn);
      if (appConfig.allow_submit) row.appendChild(postBtn);
      ent.appendChild(ta); ent.appendChild(row);
      node.appendChild(ent);
    });
    node.appendChild(el("p", null, "<strong>Your initial post</strong>"));
    const ta = el("textarea"); ta.rows = 4; node.appendChild(ta);
    const row = el("div", "row");
    const draftBtn = el("button", "ghost", "Draft with AI");
    const postBtn = el("button", "primary", "Post reply…");
    draftBtn.onclick = async () => {
      draftBtn.disabled = true; draftBtn.textContent = "Drafting…";
      try {
        const r = await api("/api/draft", { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ goal: `Write my initial discussion post (about 150-220 words) answering this prompt in first person. Prompt: ${strip(d.message)}` }) });
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
    row.appendChild(draftBtn);
    if (appConfig.allow_submit) row.appendChild(postBtn);
    node.appendChild(row);
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

// ---- license + update ----
function showLicenseGate() {
  const o = el("div", "modal");
  o.innerHTML = `<div class="modal-box">
    <div class="modal-title">Activate Canvas-AI</div>
    <div class="modal-body">Enter your license key to unlock the app.</div>
    <input id="lickey" type="text" placeholder="Your license key" style="margin-top:12px"/>
    <div class="modal-actions"><span id="licmsg" class="muted"></span><button class="primary" id="licgo">Activate</button></div>
  </div>`;
  document.body.appendChild(o);
  const go = async () => {
    const key = o.querySelector("#lickey").value.trim();
    o.querySelector("#licmsg").textContent = "Activating…";
    try {
      await api("/api/license/activate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ key }) });
      location.reload();
    } catch (e) { o.querySelector("#licmsg").textContent = e.message; }
  };
  o.querySelector("#licgo").onclick = go;
  o.querySelector("#lickey").addEventListener("keydown", (e) => { if (e.key === "Enter") go(); });
}

function showUpdateBanner(u) {
  const b = el("div", "banner");
  b.innerHTML = `Update available: v${escapeHtml(u.latest)} (you have v${escapeHtml(u.current)}). ` +
    (u.url ? `<a href="${escapeHtml(u.url)}" target="_blank">Download ↗</a>` : "");
  document.querySelector("header").insertAdjacentElement("afterend", b);
}

// ---- first-run setup wizard ----
let wizStep = 0;
function closeOnboarding() { const o = document.getElementById("wizard"); if (o) o.remove(); }

async function showOnboarding() {
  let s; try { s = await api("/api/setup/status"); } catch { s = {}; }
  let o = document.getElementById("wizard");
  if (!o) { o = el("div", "wizard"); o.id = "wizard"; document.body.appendChild(o); }
  o.innerHTML = "";
  const card = el("div", "wizard-card");
  card.appendChild(el("div", "wizard-logo"));
  const steps = [stepWelcome, stepBrain, stepUrl, stepSignin, stepDone];
  wizStep = Math.max(0, Math.min(wizStep, steps.length - 1));
  steps[wizStep](card, s);
  const dots = el("div", "dots");
  steps.forEach((_, i) => dots.appendChild(el("span", "d" + (i === wizStep ? " on" : ""))));
  card.appendChild(dots);
  if (wizStep < steps.length - 1) {
    const skip = el("div", "skip", "Skip for now — finish later in Settings");
    skip.onclick = closeOnboarding;
    card.appendChild(skip);
  }
  o.appendChild(card);
}

function wizNav(card, opts) {
  opts = opts || {};
  const nav = el("div", "nav");
  const back = el("button", "ghost", "Back");
  if (wizStep === 0) back.style.visibility = "hidden";
  back.onclick = () => { wizStep--; showOnboarding(); };
  const next = el("button", "primary", opts.nextLabel || "Next");
  next.onclick = opts.onNext || (() => { wizStep++; showOnboarding(); });
  nav.appendChild(back); nav.appendChild(next);
  card.appendChild(nav);
}

function stepWelcome(card) {
  card.appendChild(el("h2", null, "Welcome to Canvas-AI"));
  card.appendChild(el("p", "sub", "Let's get you set up — about a minute. You can change anything later in Settings."));
  wizNav(card, { nextLabel: "Get started" });
}

function stepBrain(card, s) {
  card.appendChild(el("h2", null, "Choose your AI"));
  card.appendChild(el("p", "sub", "Powers studying and chat. Claude uses your subscription · Ollama is free + local · Anthropic uses a paid API key."));
  const f = el("div", "field");
  const sel = selectEl(["claude_code", "ollama", "anthropic"], s.llm_provider);
  sel.onchange = async () => {
    try { await api("/api/setup/provider", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ provider: sel.value }) }); appConfig = await api("/api/config"); showOnboarding(); }
    catch (e) { alert(e.message); }
  };
  f.appendChild(sel); card.appendChild(f);

  if (s.llm_provider === "claude_code") {
    if (!s.claude_installed && s.platform === "win32") {
      const b = el("button", "ghost", "Install Claude Code");
      b.onclick = async () => { b.disabled = true; b.textContent = "Installing… (a minute or two)"; try { await api("/api/setup/install_claude", { method: "POST" }); } catch (e) { alert(e.message); } setTimeout(showOnboarding, 1500); };
      card.appendChild(b);
    }
    const lb = el("button", "ghost", "Log in to Claude");
    lb.onclick = async () => { try { await api("/api/setup/claude_login", { method: "POST" }); alert("Finish the Claude login in the window that opened (choose Subscription)."); } catch (e) { alert(e.message); } };
    card.appendChild(lb);
    card.appendChild(el("p", "hint", s.claude_installed ? "Claude Code is installed ✓" : "Claude Code isn't installed yet."));
  } else if (s.llm_provider === "ollama") {
    if (!s.ollama_running && s.platform === "win32") {
      const b = el("button", "ghost", "Install Ollama + model");
      b.onclick = async () => { b.disabled = true; b.textContent = "Installing… (can take a while)"; try { await api("/api/setup/install_ollama", { method: "POST" }); } catch (e) { alert(e.message); } setTimeout(showOnboarding, 1500); };
      card.appendChild(b);
    }
    card.appendChild(el("p", "hint", s.ollama_running ? "Ollama is running ✓" : "Ollama isn't running yet."));
  } else if (s.llm_provider === "anthropic") {
    const f2 = el("div", "field");
    const key = el("input"); key.type = "password"; key.placeholder = s.anthropic_key_set ? "key saved — paste to replace" : "sk-ant-…";
    f2.appendChild(el("label", null, "Anthropic API key")); f2.appendChild(key);
    const sb = el("button", "ghost", "Save key");
    sb.onclick = async () => { if (!key.value.trim()) return; sb.disabled = true; try { await api("/api/settings", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ anthropic_api_key: key.value.trim() }) }); showOnboarding(); } catch (e) { alert(e.message); } };
    f2.appendChild(sb); card.appendChild(f2);
  }
  wizNav(card, {});
}

function stepUrl(card, s) {
  card.appendChild(el("h2", null, "Your Canvas URL"));
  card.appendChild(el("p", "sub", "The address you use for Canvas, like https://yourschool.instructure.com"));
  const f = el("div", "field");
  const inp = el("input"); inp.placeholder = "https://yourschool.instructure.com"; inp.value = s.canvas_base_url || "";
  f.appendChild(inp); card.appendChild(f);
  const msg = el("p", "hint", "");
  card.appendChild(msg);
  wizNav(card, { nextLabel: "Save & continue", onNext: async () => {
    const v = inp.value.trim();
    if (!/^https?:\/\//.test(v)) { msg.textContent = "Enter a full URL starting with https://"; return; }
    try { await api("/api/settings", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ canvas_base_url: v }) }); appConfig = await api("/api/config"); wizStep++; showOnboarding(); }
    catch (e) { msg.textContent = e.message; }
  } });
}

function stepSignin(card, s) {
  card.appendChild(el("h2", null, "Sign in to Canvas"));
  if (s.canvas_authenticated) {
    card.appendChild(el("p", "sub", "You're signed in to Canvas ✓"));
    wizNav(card, { nextLabel: "Continue" });
    return;
  }
  if (!s.canvas_base_url) {
    card.appendChild(el("p", "sub", "Set your Canvas URL first — go Back."));
    wizNav(card, {});
    return;
  }
  card.appendChild(el("p", "sub", "A browser window opens — sign in to your school (including any Microsoft/Google login). Then click ‘I've signed in’."));
  const open = el("button", "primary", "Open Canvas sign-in");
  open.onclick = async () => { try { await api("/api/setup/canvas_login", { method: "POST" }); } catch (e) { alert(e.message); } };
  card.appendChild(open);
  const nav = el("div", "nav");
  const back = el("button", "ghost", "Back"); back.onclick = () => { wizStep--; showOnboarding(); };
  const chk = el("button", "ghost", "I've signed in — check"); chk.onclick = () => showOnboarding();
  nav.appendChild(back); nav.appendChild(chk);
  card.appendChild(nav);
}

function stepDone(card, s) {
  card.appendChild(el("h2", null, "You're all set 🎉"));
  const issues = [];
  if (!s.brain_ready) issues.push("finish your AI brain");
  if (!s.canvas_base_url) issues.push("set your Canvas URL");
  if (!s.canvas_authenticated) issues.push("sign in to Canvas");
  card.appendChild(el("p", "sub", issues.length
    ? "Still to do (you can finish these in Settings): " + issues.join(", ") + "."
    : "Everything's connected. Open the Study tab to begin."));
  const nav = el("div", "nav");
  const back = el("button", "ghost", "Back"); back.onclick = () => { wizStep--; showOnboarding(); };
  const done = el("button", "primary", "Open Canvas-AI"); done.onclick = () => { closeOnboarding(); location.reload(); };
  nav.appendChild(back); nav.appendChild(done);
  card.appendChild(nav);
}

// ---- utils ----
function fmt(iso) { try { return new Date(iso).toLocaleString(); } catch { return iso; } }
function strip(html) { const d = el("div", null, html || ""); return (d.textContent || "").slice(0, 1500); }
function escapeHtml(s) { const d = document.createElement("div"); d.textContent = s == null ? "" : s; return d.innerHTML; }

init();
