/* CaseForge app — plain JavaScript, no build step. Talks to the FastAPI JSON API. */
"use strict";

const $ = (sel, root = document) => root.querySelector(sel);
const view = $("#view"), side = $("#side"), userbar = $("#userbar");
const S = { me: null, config: null, projects: [], rec: null, pendingImages: [], editing: null };

/* ---------------------------------------------------------------- helpers */
function esc(v) {
  return String(v ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function toast(msg, err = false) {
  document.querySelectorAll(".toast").forEach(t => t.remove());
  const t = document.createElement("div");
  t.className = "toast" + (err ? " err" : "");
  t.setAttribute("role", err ? "alert" : "status");
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), err ? 6000 : 3000);
}
async function api(method, path, body) {
  const opts = { method, headers: {}, credentials: "same-origin" };
  if (body instanceof FormData) opts.body = body;
  else if (body !== undefined) { opts.headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(body); }
  const r = await fetch(path, opts);
  if (r.status === 401 && S.me && !path.startsWith("/api/log") && !path.startsWith("/api/signup")) {
    S.me = null; location.hash = "#login"; throw new Error("Your session ended. Please log in again.");
  }
  const ct = r.headers.get("content-type") || "";
  const data = ct.includes("json") ? await r.json() : await r.text();
  if (!r.ok) throw new Error((data && data.detail) || `Request failed (${r.status})`);
  return data;
}
async function act(fn, okMsg) {
  try { const out = await fn(); if (okMsg) toast(okMsg); return out; }
  catch (e) { toast(e.message, true); return null; }
}
function busy(steps) {
  const el = document.createElement("div");
  el.className = "busy";
  el.innerHTML = `<div class="box" role="status"><b>Working on it…</b><ol>${steps.map(s => `<li>${esc(s)}</li>`).join("")}</ol>
    <p class="hint" style="margin:12px 0 0"><span class="secs">Usually 10–30 seconds.</span></p></div>`;
  document.body.appendChild(el);
  const lis = el.querySelectorAll("li"), secs = el.querySelector(".secs"), t0 = Date.now(); let i = 0;
  lis[0]?.classList.add("on");
  const timer = setInterval(() => { if (i < lis.length - 1) { lis[i].classList.remove("on"); lis[++i].classList.add("on"); } }, 4500);
  const clock = setInterval(() => {
    const s = Math.round((Date.now() - t0) / 1000);
    if (s >= 40) secs.textContent = `${s}s. Gemini is slow right now, still trying (or switching to a backup model). It gives up after 4 minutes.`;
  }, 1000);
  return () => { clearInterval(timer); clearInterval(clock); el.remove(); };
}
/* confirmation dialog — a real <dialog>, keyboard and screen-reader friendly; resolves true/false */
function confirmBox(title, html, okText = "Confirm") {
  return new Promise(resolve => {
    const d = document.createElement("dialog");
    d.className = "confirm";
    d.innerHTML = `<h3>${esc(title)}</h3><p>${html}</p><div class="row">
      <button class="btn" value="no">Cancel</button><button class="btn primary" value="yes">${esc(okText)}</button></div>`;
    document.body.appendChild(d);
    const inp = d.querySelector("input");  /* a dialog with a field resolves to its value */
    const done = v => { const out = v && inp ? inp.value : v; d.close(); d.remove(); resolve(out); };
    d.querySelector('[value="no"]').onclick = () => done(false);
    d.querySelector('[value="yes"]').onclick = () => done(true);
    d.addEventListener("cancel", e => { e.preventDefault(); done(false); });
    d.addEventListener("click", e => { if (e.target === d) done(false); });
    if (inp) inp.addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); done(true); } });
    d.showModal(); (inp || d.querySelector('[value="yes"]')).focus();
  });
}
const LABEL = {
  supported: ["ok", "In your notes"], reworded: ["re", "Reworded from your notes"],
  unsupported: ["bad", "Not in your notes"], contradicted: ["bad", "Contradicts your notes"],
};
const chip = label => { const [cls, txt] = LABEL[label] || ["none", "Not checked"]; return `<span class="chip ${cls}">${txt}</span>`; };
const STATUS = { input: "No draft yet", drafted: "Waiting for review", approved: "Approved", rejected: "Rejected" };

/* ---------------------------------------------------------------- chrome */
function renderChrome() {
  if (!S.me) { userbar.innerHTML = `<a class="btn sm" href="#login">Log in</a>`; side.hidden = true; return; }
  userbar.innerHTML = `<span class="quota" title="AI actions left today">${S.me.quota_left} AI actions left today</span>
    <a class="acct" href="#settings" title="Settings"><span class="avatar sm" aria-hidden="true">${esc(initials(S.me.name))}</span>
      <span class="acct-t"><b>${esc(S.me.name)}</b><small>${esc(S.me.workspace_name)}</small></span></a>
    <button class="btn sm" id="logout">Log out</button>`;
  $("#logout").onclick = async () => { await api("POST", "/api/logout"); S.me = null; location.href = "/"; };
  side.hidden = false;
  const cur = (location.hash.match(/^#p\/([^/]+)/) || [])[1];
  side.innerHTML = `<a class="btn primary" href="#new">New case study</a>
    <a class="btn ghost" href="#library" style="margin-top:8px">Proof library</a>
    <a class="btn ghost" href="#brands" style="margin-top:8px">Brand kits</a>
    <h4>Your workspace</h4>
    ${S.projects.length ? `<ul>${S.projects.map(p => `<li><a href="#p/${esc(p.id)}" class="${p.id === cur ? "on" : ""}" title="${esc(p.title || "Untitled")}">
      <span class="dot ${esc(p.status)}" aria-hidden="true"></span><span class="t">${esc(p.title || "Untitled")}</span>
      <small>${STATUS[p.status]} · ${when(p.updated_at)}</small></a></li>`).join("")}</ul>`
      : `<p class="empty">Nothing here yet. Your case studies will show up in this list.</p>`}`;
}
async function refreshSide() {
  try { S.projects = await api("GET", "/api/projects"); S.me = await api("GET", "/api/me"); } catch (e) { /* handled */ }
  renderChrome();
}

/* ---------------------------------------------------------------- auth */
function viewAuth(mode) {
  const signup = mode === "signup";
  view.innerHTML = `<div class="auth">
    <div class="auth-side">
      <span class="wordmark"><span class="mark" aria-hidden="true"></span>CaseForge</span>
      <h2>Messy project notes in.<br><span>A fact-checked case study out.</span></h2>
      <ul><li>Every sentence and number checked against your notes</li>
        <li>A branded 4–5 page report, laid out from what your project actually achieved</li>
        <li>Nothing goes to a client until a person approves it</li></ul>
      <div class="proof" aria-hidden="true">
        <div><span>Late deliveries fell from 14% to 6.1%.</span><span class="chip ok">In your notes</span></div>
        <div><span class="x">Costs dropped by 70% overnight.</span><span class="chip bad">Not in your notes</span></div>
      </div>
    </div>
    <div class="auth-form">
    <h1 class="page">${signup ? "Create your account" : "Log in"}</h1>
    <p class="sub">${signup ? "Free while we're testing. Your case studies stay private to your workspace." : "Welcome back."}</p>
    <form id="auth" novalidate>
      ${signup ? `<div class="field"><label for="name">Your name</label><input id="name" type="text" autocomplete="name" required></div>` : ""}
      <div class="field"><label for="email">Email</label><input id="email" type="email" autocomplete="email" required></div>
      <div class="field"><label for="pw">Password</label><input id="pw" type="password" autocomplete="${signup ? "new-password" : "current-password"}" required>
        ${signup ? `<div class="hint">At least 8 characters.</div>` : ""}</div>
      ${signup ? `<div class="field"><label for="company">Company or team name</label><input id="company" type="text" placeholder="Leave blank if you're joining a team"></div>
      <div class="field"><label for="invite">Invite code (optional)</label><input id="invite" type="text" placeholder="From a teammate, to join their workspace"></div>` : ""}
      <button class="btn primary" style="width:100%" type="submit">${signup ? "Create account" : "Log in"}</button>
    </form>
    <p class="switch">${signup ? `Have an account? <a href="#login">Log in</a>` : `New here? <a href="#signup">Create an account</a>`}</p>
  </div></div>`;
  $("#auth").onsubmit = async e => {
    e.preventDefault();
    const body = { email: $("#email").value, password: $("#pw").value };
    if (signup) Object.assign(body, { name: $("#name").value, company: $("#company").value, invite_code: $("#invite").value });
    const user = await act(() => api("POST", signup ? "/api/signup" : "/api/login", body));
    if (user) { await refreshSide(); location.hash = "#new"; }
  };
}

/* ---------------------------------------------------------------- new case study */
/* "today, 14:02" / "9 Nov" — so eight projects with the same name can be told apart */
function when(iso) {
  const d = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : iso + "Z"); if (isNaN(d)) return "";
  const t = d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  return d.toDateString() === new Date().toDateString() ? `today, ${t}` : d.toLocaleDateString([], { day: "numeric", month: "short" }) + `, ${t}`;
}
function viewNew() {
  S.pendingImages = [];
  view.innerHTML = `
    <h1 class="page">New case study</h1>
    <p class="sub">Upload files, import a Notion page or paste notes. Messy is fine: CaseForge only uses what's here and tells you what's missing.</p>
    <div class="samples"><span class="hint">No notes handy? Try an example:</span><span id="samples"></span>
      <button class="btn sm ghost" id="clear" type="button">Clear all</button></div>
    <div class="sheet">
    <div class="two">
      <div class="field"><label for="title">Project name (optional)</label><input id="title" type="text" placeholder="e.g. Inventory dashboard"></div>
      <div class="field"><label for="client">Client name (optional)</label><input id="client" type="text" placeholder="Only with the client's permission"></div>
    </div>
    <div class="field">
      <label for="files">Files</label>
      <div class="drop" id="drop" tabindex="0" role="button" aria-describedby="drophint">
        <b>Drop files here</b> or click to choose<div class="hint" id="drophint">PDF, Word, Excel, PowerPoint, text or images · up to ${S.config?.max_file_mb || 10} MB each</div>
      </div>
      <input id="files" type="file" multiple hidden accept="${(S.config?.file_types || []).map(t => "." + t).join(",")}">
      <ul class="files" id="filelist"></ul>
      <details class="fold" id="notionbox"><summary>Import from Notion</summary>
        <div class="notion">
          <ol class="hint">
            <li>Go to <b>notion.so/profile/integrations</b> → <b>New integration</b> (Internal), tick <b>Read content</b>, copy the secret.</li>
            <li>Open your project page in Notion → <b>•••</b> → <b>Connections</b> → add that integration.</li>
            <li>Paste the secret and the page link here. Sub-pages and tables inside it are read too.</li>
          </ol>
          <div class="two">
            <div class="field"><label for="ntoken">Integration secret</label><input id="ntoken" type="password" autocomplete="off" placeholder="ntn_…"></div>
            <div class="field"><label for="nurl">Page link</label><input id="nurl" type="text" inputmode="url" autocomplete="off" placeholder="https://www.notion.so/…"></div>
          </div>
          <button class="btn" id="nimport" type="button">Import page</button>
          <span class="hint">The secret is used once and never saved.</span>
        </div>
      </details>
    </div>
    <div class="field"><label for="logo">Company logo (optional)</label>
      <div class="pick"><label class="btn" for="logo" style="margin:0">Choose logo</label><input id="logo" type="file" class="sr" accept="image/png,image/jpeg">
        <img id="logoprev" alt="" hidden><span class="hint" id="logoname">PNG or JPG</span></div>
      <div class="hint" style="margin-top:.4em">The report uses your logo and takes its colours from it. No logo? The colours are matched to your notes.</div></div>
    <div class="field"><label for="notes">Notes</label>
      <textarea id="notes" rows="12" placeholder="- client tracked stock in 3 excel files&#10;- we built a dashboard, python + react&#10;- manager said the friday count is way faster now"></textarea>
      <div class="hint">Text from your files appears here first, so you can see and delete anything before it goes to the AI.</div></div>
    <div class="go"><button class="btn primary" id="go">Write my case study</button><span class="hint">Takes about a minute. Every sentence is checked against these notes.</span></div>
    </div>`;
  $("#logo").onchange = e => {
    const f = e.target.files[0], img = $("#logoprev");
    $("#logoname").textContent = f ? f.name : "PNG or JPG";
    img.hidden = !f; if (f) img.src = URL.createObjectURL(f);
  };
  api("GET", "/api/samples").then(list => {
    $("#samples").innerHTML = list.map(s => `<button class="btn sm" data-k="${esc(s.key)}" type="button">${esc(s.label)}</button>`).join(" ");
    $("#samples").onclick = async e => {
      const k = e.target.dataset.k; if (!k) return;
      const s = await act(() => api("GET", "/api/samples/" + k));
      if (s) { $("#title").value = s.title; $("#client").value = s.client; $("#notes").value = s.notes; }
    };
  });
  $("#clear").onclick = () => { ["#title", "#client", "#notes"].forEach(i => $(i).value = ""); S.pendingImages = []; $("#filelist").innerHTML = ""; };
  const drop = $("#drop"), input = $("#files");
  drop.onclick = () => input.click();
  drop.onkeydown = e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); input.click(); } };
  drop.ondragover = e => { e.preventDefault(); drop.classList.add("over"); };
  drop.ondragleave = () => drop.classList.remove("over");
  drop.ondrop = e => { e.preventDefault(); drop.classList.remove("over"); addFiles(e.dataTransfer.files); };
  input.onchange = () => { addFiles(input.files); input.value = ""; };
  $("#nimport").onclick = importNotion;
  $("#go").onclick = createProject;
}
async function importNotion() {
  const token = $("#ntoken").value.trim(), url = $("#nurl").value.trim();
  if (!token || !url) { toast("Paste the integration secret and the page link.", true); return; }
  const btn = $("#nimport"); btn.disabled = true; btn.textContent = "Reading Notion…";
  const r = await act(() => api("POST", "/api/notion", { token, url }));
  btn.disabled = false; btn.textContent = "Import page";
  if (!r) return;
  const notes = $("#notes");
  notes.value = (notes.value.trim() + `\n\n--- from Notion: ${r.title} ---\n` + r.text).trim();
  if (!$("#title").value.trim()) $("#title").value = r.title;
  const words = r.text.split(/\s+/).length, pages = r.pages === 1 ? "1 page" : `${r.pages} pages and rows`;
  $("#filelist").insertAdjacentHTML("beforeend", `<li><b>Notion: ${esc(r.title)}</b> — ${words} words from ${pages} added to the notes${r.truncated ? " (cut: too long)" : ""}</li>`);
  $("#ntoken").value = "";
  $("#notionbox").open = false;
  toast("Notion page added to the notes. Check it before writing.");
}
async function addFiles(fileList) {
  const files = [...fileList]; if (!files.length) return;
  const fd = new FormData(); files.forEach(f => fd.append("files", f));
  const res = await act(() => api("POST", "/api/extract", fd)); if (!res) return;
  const list = $("#filelist"), notes = $("#notes");
  res.forEach((r, i) => {
    let msg;
    if (r.error) msg = `<span style="color:var(--bad)">${esc(r.error)}</span>`;
    else if (r.image) { S.pendingImages.push(files[i]); msg = "added as an image"; }
    else { notes.value = (notes.value.trim() + `\n\n--- from ${r.name} ---\n` + r.text).trim(); msg = `${r.text.split(/\s+/).length} words added to the notes`; }
    list.insertAdjacentHTML("beforeend", `<li><b>${esc(r.name)}</b> — ${msg}</li>`);
  });
}
async function createProject() {
  const notes = $("#notes").value.trim();
  if (!notes) { toast("Add some notes or upload a file first.", true); return; }
  const fd = new FormData();
  fd.append("title", $("#title").value); fd.append("client_name", $("#client").value); fd.append("notes", notes);
  S.pendingImages.forEach(f => fd.append("images", f));
  const lg = $("#logo")?.files[0]; if (lg) fd.append("logo", lg);
  const done = busy(["Reading your notes and pulling out the facts", "Writing the case study from those facts only", "Checking every sentence against your notes"]);
  try {
    const rec = await api("POST", "/api/projects", fd);
    try { await api("POST", `/api/projects/${rec.id}/generate`); }
    catch (e) { toast(e.message, true); }
    await refreshSide();
    location.hash = `#p/${rec.id}`;
  } catch (e) { toast(e.message, true); }
  finally { done(); }
}

/* ---------------------------------------------------------------- project */
async function viewProject(id, tab) {
  const rec = await act(() => api("GET", `/api/projects/${id}`));
  if (!rec) { view.innerHTML = `<div class="empty-state">This case study doesn't exist in your workspace.</div>`; return; }
  S.rec = rec; renderProject(tab);
}
/* the project is a guided flow: Review → Report → Download. Each step unlocks the next and moves you on. */
const STEPS = [["review", "Review"], ["report", "Report"], ["outputs", "Download"]];
function stepState(r) {
  const rep = r.report, fresh = rep && rep.based_on_hash === r.approved_hash;
  return { review: r.can_export ? "done" : "now",
           report: !r.can_export ? "locked" : r.report_ready && fresh ? "done" : "now",
           outputs: !r.can_export ? "locked" : r.report_ready && fresh ? "now" : "open" };
}
function renderProject(tab = "review") {
  const r = S.rec, st = stepState(r);
  if (st[tab] === "locked") tab = "review";
  if (S.lastTab !== tab) { window.scrollTo(0, 0); S.lastTab = tab; }
  view.innerHTML = `
    <div class="phead"><div><h1 class="page">${esc(r.input.title || "Untitled case study")}</h1>
      <p class="sub">${STATUS[r.status]}${r.input.client_name ? " · " + esc(r.input.client_name) : ""}</p></div>
      <a class="btn sm ghost" href="#p/${esc(r.id)}/details" title="Notes, facts and history">Details</a></div>
    <nav class="steps" aria-label="Steps">${STEPS.map(([k, t], i) => {
      const cls = st[k] + (tab === k ? " on" : "");
      const inner = `<span class="num">${st[k] === "done" ? "✓" : i + 1}</span><span>${t}</span>`;
      return st[k] === "locked" ? `<span class="step ${cls}" aria-disabled="true" title="Approve the case study first">${inner}</span>`
        : `<a class="step ${cls}" href="#p/${esc(r.id)}${k === "review" ? "" : "/" + k}" ${tab === k ? 'aria-current="step"' : ""}>${inner}</a>`;
    }).join('<span class="sep" aria-hidden="true"></span>')}</nav>
    <div id="tab"></div>`;
  if (!r.claims.length) {
    $("#tab").innerHTML = `<div class="empty-state"><p>No draft yet.</p><button class="btn primary" id="gen">Write the draft</button></div>`;
    $("#gen").onclick = regenerate; return;
  }
  ({ review: tabReview, report: tabReport, outputs: tabOutputs, details: tabDetails }[tab] || tabReview)();
}
async function update(promise, msg) {
  const rec = await act(() => promise, msg);
  if (rec) { S.rec = rec; const tab = (location.hash.split("/")[2]) || "review"; renderProject(tab); refreshSide(); }
  return rec;
}
function go(tab) { const h = `#p/${S.rec.id}${tab === "review" ? "" : "/" + tab}`; if (location.hash === h) renderProject(tab); else location.hash = h; }
function savedBrand() { try { return localStorage.getItem("cf_brand") || ""; } catch (e) { return ""; } }
function saveBrand(id) { S.reportBrand = id; try { localStorage.setItem("cf_brand", id); } catch (e) { /* private mode */ } }
const P = () => `/api/projects/${S.rec.id}`;

function tabReview() {
  const r = S.rec, el = $("#tab");
  const active = r.claims.filter(c => !c.deleted);
  const bad = active.filter(c => !c.label || c.label === "unsupported" || c.label === "contradicted");
  const openGaps = r.gaps.filter(g => g.blocking && !g.resolved);
  const optional = r.gaps.filter(g => !g.blocking && !g.resolved);
  let next;
  if (r.can_export) next = `<div class="next ok"><b>Approved.</b> Your report is next — <a href="#p/${esc(r.id)}/report">open it</a>.</div>`;
  else if (bad.length) next = `<div class="next bad"><b>Next step:</b> ${bad.length} sentence${bad.length > 1 ? "s aren't" : " isn't"} backed by your notes (marked red). Fix or delete ${bad.length > 1 ? "them" : "it"}.</div>`;
  else if (openGaps.length) next = `<div class="next warn"><b>Next step:</b> answer ${openGaps.length} question${openGaps.length > 1 ? "s" : ""} about missing information.</div>`;
  else next = `<div class="next"><b>Read the draft.</b> When it's right, hit Approve — the report is designed for you.</div>`;

  el.innerHTML = `
    <p>CaseForge pulled <b>${r.facts.length} facts</b> from your notes and wrote <b>${active.length} sentences</b>: <b>${active.length - bad.length}</b> backed by your notes${bad.length ? `, <b>${bad.length}</b> not` : " — nothing invented"}.</p>
    ${next}
    ${openGaps.map(g => `<div class="gap"><b>${esc(g.message)}</b>
      ${["client_problem", "work_done", "technical_approach", "tools", "challenges", "results"].includes(g.field) ? `
      <div class="row"><input type="text" data-gap="${esc(g.id)}" aria-label="Add the missing information" placeholder="Add it in your own words">
        <button class="btn sm primary" data-gapadd="${esc(g.id)}">Add to case study</button>
        <button class="btn sm" data-gapskip="${esc(g.id)}">Leave it out</button></div>` : `<div class="row"><button class="btn sm" data-gapskip="${esc(g.id)}">OK</button></div>`}</div>`).join("")}
    ${optional.length ? `<details class="optional"><summary>${optional.length} optional suggestion${optional.length > 1 ? "s" : ""} to make it stronger</summary>
      <ul>${optional.map(g => `<li>${esc(g.message)}</li>`).join("")}</ul></details>` : ""}
    <div class="doc">${r.sections.map(sec => {
      const cs = r.claims.filter(c => c.section === sec.key && !c.deleted);
      return cs.length ? `<h3>${esc(sec.title)}</h3>${cs.map(claimRow).join("")}` : "";
    }).join("")}</div>
    <details class="optional" style="margin-top:14px"><summary>Add your own sentence</summary>
      <div class="two" style="margin-top:10px"><div><label for="addsec">Section</label><select id="addsec">${r.sections.map(s => `<option value="${s.key}">${esc(s.title)}</option>`).join("")}</select></div>
      <div><label for="addtxt">Sentence</label><textarea id="addtxt" rows="2"></textarea></div></div>
      <button class="btn sm primary" id="addbtn" style="margin-top:8px">Add and check it</button></details>
    ${r.claims.some(c => c.deleted) ? `<details class="optional"><summary>Deleted sentences (${r.claims.filter(c => c.deleted).length})</summary>
      <ul>${r.claims.filter(c => c.deleted).map(c => `<li><s>${esc(c.text)}</s> <button class="btn sm ghost" data-restore="${esc(c.id)}">Undo</button></li>`).join("")}</ul></details>` : ""}
    <div class="approve">${r.can_export
      ? `<div><b>Approved.</b> Edit anything and the approval is withdrawn automatically.</div><a class="btn primary" href="#p/${esc(r.id)}/report">Next: report →</a>`
      : `<div>${r.blockers.length ? `<b>${r.blockers.length} thing${r.blockers.length > 1 ? "s" : ""} to fix before you can approve</b>`
        : `<b>Everything is backed by your notes.</b> Approve and CaseForge designs the report for you.`}</div>
      <div style="display:flex;gap:.5rem">${r.blockers.length ? `<button class="btn" id="nextissue">Next issue ↓</button>` : `<button class="btn ghost" id="reject">Reject</button>`}
        <button class="btn primary" id="approve" ${r.blockers.length ? "disabled" : ""}>Approve</button></div>`}</div>`;

  el.onclick = async e => {
    const t = e.target.closest("button"); if (!t) return;
    const d = t.dataset;
    if (d.edit) { S.editing = d.edit; tabReview(); $(`textarea[data-ed="${d.edit}"]`)?.focus(); }
    else if (d.cancel) { S.editing = null; tabReview(); }
    else if (d.save) { const txt = $(`textarea[data-ed="${d.save}"]`).value; S.editing = null; update(api("POST", `${P()}/claims/${d.save}/edit`, { text: txt }), "Saved and re-checked."); }
    else if (d.del) update(api("POST", `${P()}/claims/${d.del}/delete`), "Sentence deleted.");
    else if (d.restore) update(api("POST", `${P()}/claims/${d.restore}/restore`));
    else if (d.confirm) update(api("POST", `${P()}/claims/${d.confirm}/confirm`), "Added to your notes and re-checked.");
    else if (d.gapskip) update(api("POST", `${P()}/gaps/${d.gapskip}/resolve`, { text: "Left out — not in the notes" }));
    else if (d.gapadd) { const v = $(`input[data-gap="${d.gapadd}"]`).value.trim(); if (v) update(api("POST", `${P()}/gaps/${d.gapadd}/add`, { text: v }), "Added and checked."); }
    else if (t.id === "addbtn") { const v = $("#addtxt").value.trim(); if (v) update(api("POST", `${P()}/claims`, { section: $("#addsec").value, text: v }), "Added and checked."); }
    else if (t.id === "approve") {
      const ok = await confirmBox("Approve this case study?",
        `You confirm every sentence is correct and it can go to the client. The approval is saved under your name (${esc(S.me.name)}) with the date. Any later edit removes it.`, "Yes, approve");
      if (ok && await update(api("POST", `${P()}/approve`))) { toast("Approved. Designing your report…"); go("report"); }
    }
    else if (t.id === "nextissue") {
      const items = [...document.querySelectorAll(".gap, .claim.bad")];
      const nxt = items.find(x => x.getBoundingClientRect().top > 140) || items[0];
      if (nxt) { nxt.scrollIntoView({ behavior: "smooth", block: "center" }); nxt.classList.add("flash"); setTimeout(() => nxt.classList.remove("flash"), 1200); }
    }
    else if (t.id === "reject") { const why = prompt("Why are you rejecting this draft?"); if (why !== null) update(api("POST", `${P()}/reject`, { text: why })); }
  };
}
function claimRow(c) {
  const blocking = !c.label || c.label === "unsupported" || c.label === "contradicted";
  const cls = blocking ? "bad" : c.label === "supported" ? "ok" : "";
  const editing = S.editing === c.id;
  return `<div class="claim ${cls}">
    <div class="s">${editing ? `<textarea data-ed="${esc(c.id)}" aria-label="Edit sentence">${esc(c.text)}</textarea>` : esc(c.text)}</div>
    <div class="m">${chip(c.label)}${c.edited ? ` <span class="hint">edited</span>` : ""}${c.manual ? ` <span class="hint">added by you</span>` : ""}
      ${blocking ? `<span class="why">${esc(c.reason)}</span>` : c.evidence ? `<br><q>${esc(c.evidence.slice(0, 180))}</q>` : ""}
      <div class="acts">${editing
        ? `<button class="btn sm primary" data-save="${esc(c.id)}">Save and re-check</button><button class="btn sm ghost" data-cancel="1">Cancel</button>`
        : `<button class="btn sm" data-edit="${esc(c.id)}">Edit</button><button class="btn sm ghost danger" data-del="${esc(c.id)}">Delete</button>
           ${blocking ? `<button class="btn sm ghost" data-confirm="${esc(c.id)}" title="Adds it to your notes, logged with your name">It's true</button>` : ""}`}</div>
    </div></div>`;
}

function tabOutputs() {
  const r = S.rec, el = $("#tab"), ok = r.can_export;
  const docs = [["case-study", "Case study", "Full write-up · PDF"],
                ["one-pager", "One-page summary", "For quick sharing · PDF"],
                ["portfolio", "Portfolio page", "For your website · HTML"]];
  const rr = r.report_ready && r.report && r.report.based_on_hash === r.approved_hash;
  const dl = (href, name, sub, primary) => `<a class="dl${primary ? " main" : ""}" href="${href}">
      <span class="ic" aria-hidden="true"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 4v11m0 0l-4.5-4.5M12 15l4.5-4.5M5 19h14"/></svg></span>
      <span><b>${name}</b><small>${sub}</small></span></a>`;
  el.innerHTML = `
    ${!ok ? `<div class="next warn"><b>Approve the case study first.</b> Nothing goes to a client without a person checking it.</div>` : `
    <div class="ready ${rr ? "" : "wait"}">
      <div><div class="kicker">${rr ? "Ready to send" : "Almost there"}</div>
        <h2>${rr ? "Your report is ready" : "Approve the report to unlock it"}</h2>
        <p class="hint">${rr ? `Fact-checked against your notes and approved by ${esc(r.report.approved_by)}.` : "The case study files below are already approved and ready."}</p></div>
      ${rr ? dl(`${P()}/report/pdf`, "Report PDF", `${esc(r.report.brand.name)} · ${(r.report.layout?.pages?.length || 4) + 1} pages`, true) : `<a class="btn primary" href="#p/${esc(r.id)}/report">Go to report</a>`}
    </div>
    <div class="dls">${docs.map(([k, t, d]) => dl(`${P()}/export/${k}`, t, d)).join("")}</div>
    <div class="panel verified" id="anon">
      <div class="head"><div><h3>Anonymized version</h3>
        <span class="hint">For clients who won't be named. Choose which names to swap; only those words change, so every number and fact stays exactly as approved.</span></div></div>
      <div id="anonbox"><p class="hint">Loading…</p></div>
    </div>
    <div class="panel verified" id="signoff">
      <div class="head"><div><h3>Client sign-off</h3>
        <span class="hint">Send the client one link. They confirm, fix or remove each number, quote and mention of them, from a phone, with no account. Confirmed sentences show on the Verified link.</span></div></div>
      <div class="vset">
        <div class="field"><label for="socontact">Client contact (optional)</label><input id="socontact" type="text" placeholder="e.g. Dana Lee"></div>
        <button class="btn primary" data-askclient="1">Create sign-off link</button>
      </div>
      <div id="solinks"><p class="hint">Loading…</p></div>
    </div>
    <div class="panel verified" id="verified">
      <div class="head"><div><h3>Verified link</h3>
        <span class="hint">A public page where anyone can click a sentence and see the quote from your notes behind it. The report PDF gets its QR code.</span></div></div>
      <div class="vset">
        <div class="field"><label for="vev">Show readers</label>
          <select id="vev"><option value="full">Quotes from the notes, with file and line</option>
            <option value="masked">Quotes, with details the sentence doesn't mention hidden</option>
            <option value="labels">Check results only, no quotes</option></select></div>
        <div class="field"><label for="vname">Names</label>
          <select id="vname">${r.client_signoff?.decision === "anonymous" ? "" : `<option value="show">Show the client's name</option>`}
            <option value="hide">Replace the client's name with "the client"</option>
            <option value="anon" ${r.anon_map?.length ? "" : "disabled"}>Anonymized version (your name swaps)${r.anon_map?.length ? "" : ": set it up above"}</option></select>
          ${r.client_signoff?.decision === "anonymous" ? `<span class="hint">The client asked to stay anonymous.</span>` : ""}</div>
        <button class="btn primary" data-publish="1">Publish verified link</button>
      </div>
      <div id="vlinks"><p class="hint">Loading links…</p></div>
    </div>`}
    <h2 style="margin:34px 0 4px;font-size:1.15rem">Short versions</h2>
    <p class="sub">Written from the approved case study only — and every sentence is checked against your notes again.</p>
    ${Object.entries(r.formats).map(([k, f]) => {
      const out = r.outputs[k];
      return `<div class="panel fmt"><div class="head"><div><h3>${esc(f.title)}</h3><span class="hint">${esc(f.blurb)}</span></div>
        <div style="display:flex;gap:.4rem">${f.ready ? `<button class="btn sm primary" data-copy="${k}">Copy text</button>` : ""}
          <button class="btn sm" data-write="${k}" ${ok ? "" : "disabled title='Approve the case study first'"}>${out ? "Write again" : "Write it"}</button></div></div>
        ${out ? `${f.stale ? `<p class="hint" style="color:var(--bad)">The case study changed since this was written — write it again.</p>` : ""}
          <div class="doc" style="margin-top:12px">${out.sentences.filter(s => !s.deleted).map(s => fmtRow(k, s)).join("")}</div>` : ""}</div>`;
    }).join("")}`;
  if (ok) { loadLinks(); loadSignoffs(); loadAnon(); }
  el.onclick = async e => {
    const t = e.target.closest("button"); if (!t) return;
    const d = t.dataset;
    if (d.anonsave || d.anonadd || d.anonrm) {
      const rows = [...document.querySelectorAll("#anonbox .swap")].map(x => ({
        term: x.querySelector(".st").value, replace: x.querySelector(".swr").value, on: x.querySelector(".so-on").checked }));
      if (d.anonadd) { rows.push({ term: "", replace: "", on: true, kind: "new" }); showAnon({ ...S.anon, swaps: rows }); return; }
      if (d.anonrm) { rows.splice(+d.anonrm, 1); showAnon({ ...S.anon, swaps: rows }); return; }
      const v = await act(() => api("POST", `${P()}/anon`, { swaps: rows.filter(x => x.term.trim()) }), "Name swaps saved.");
      if (v) { S.rec.anon_map = v.swaps.filter(x => x.kind === "saved").map(x => [x.term, x.replace]); showAnon(v); refreshNameChoice(); }
      return;
    }
    if (d.askclient) {
      t.disabled = true;
      const list = await act(() => api("POST", `${P()}/signoff`, { contact: $("#socontact").value }), "Sign-off link ready. Copy it and send it to the client.");
      t.disabled = false;
      if (list) showSignoffs(list);
    } else if (d.socancel) {
      if (!confirm("Cancel this sign-off link? The client won't be able to open it.")) return;
      const list = await act(() => api("DELETE", `${P()}/signoffs/${d.socancel}`), "Sign-off link cancelled.");
      if (list) showSignoffs(list);
    } else if (d.use) {
      const [tok, cid] = d.use.split(":");
      const done = busy(["Applying the client's answer", "Checking the sentence against your notes"]);
      try { await update(api("POST", `${P()}/signoffs/${tok}/use/${cid}`), "Applied. Review and approve the case study again."); } finally { done(); }
    } else if (d.publish) {
      const nm = $("#vname").value;
      const body = { evidence: $("#vev").value, show_client: nm === "show", anonymized: nm === "anon" };
      t.disabled = true;
      const links = await act(() => api("POST", `${P()}/publish`, body), "Published. Copy the link or download the PDF with its QR code.");
      t.disabled = false;
      if (links) showLinks(links);
    } else if (d.revoke) {
      if (!confirm("Unpublish this link? Anyone who opens it will see that it's no longer available.")) return;
      const links = await act(() => api("POST", `${P()}/published/${d.revoke}/revoke`), "Link unpublished.");
      if (links) showLinks(links);
    } else if (d.vcopy) {
      await navigator.clipboard.writeText(d.vcopy).then(() => toast("Link copied."), () => toast("Couldn't copy — select the link instead.", true));
    } else if (d.write) {
      const done = busy(["Writing from the approved case study", "Checking every sentence against your notes"]);
      try { await update(api("POST", `${P()}/formats/${d.write}`)); } finally { done(); }
    } else if (d.copy) {
      const txt = await act(() => api("GET", `${P()}/formats/${d.copy}/text`));
      if (txt !== null) { await navigator.clipboard.writeText(txt).then(() => toast("Copied."), () => toast("Couldn't copy — select the text instead.", true)); }
    } else if (d.fdel) update(api("POST", `${P()}/formats/${d.k}/${d.fdel}`, { delete: true }));
    else if (d.fedit) { S.editing = "f" + d.k + d.fedit; tabOutputs(); }
    else if (d.fsave) { const v = $(`textarea[data-fed="${d.k}${d.fsave}"]`).value; S.editing = null; update(api("POST", `${P()}/formats/${d.k}/${d.fsave}`, { text: v }), "Saved and re-checked."); }
    else if (d.cancel) { S.editing = null; tabOutputs(); }
  };
}
async function loadAnon() {
  const v = await act(() => api("GET", `${P()}/anon`));
  if (v) showAnon(v);
}
function refreshNameChoice() {
  const o = $("#vname option[value=anon]"); if (!o) return;
  const on = !!S.rec.anon_map?.length;
  o.disabled = !on; o.textContent = "Anonymized version (your name swaps)" + (on ? "" : ": set it up above");
}
function showAnon(v) {
  S.anon = v;
  const box = $("#anonbox"); if (!box) return;
  const r = S.rec, P2 = P(), rr = r.report_ready && r.report && r.report.based_on_hash === r.approved_hash;
  const KIND = { client: "client", name: "maybe a name", email: "email", link: "link", phone: "phone", saved: "", new: "" };
  const mark = (a, b) => esc(b);
  box.innerHTML = `
    ${v.client_wants_anonymous ? `<div class="next warn" style="margin:10px 0"><b>The client asked to stay anonymous.</b> Use these versions when you publish or send it.</div>` : ""}
    <div class="swaps">${v.swaps.map((x, i) => `<div class="swap">
        <input type="checkbox" class="so-on" ${x.on ? "checked" : ""} aria-label="Swap this name">
        <input type="text" class="st" value="${esc(x.term)}" placeholder="Name in the case study" aria-label="Name">
        <span aria-hidden="true">→</span>
        <input type="text" class="swr" value="${esc(x.replace)}" placeholder="${x.kind === "name" ? "e.g. the operations manager" : "what to call it"}" aria-label="Replace with">
        <span class="kind">${KIND[x.kind] || ""}</span>
        <button class="btn sm ghost" data-anonrm="${i}" aria-label="Remove">×</button></div>`).join("") || `<p class="hint">No names found. Add any you want swapped.</p>`}</div>
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin:10px 0 4px">
      <button class="btn sm" data-anonadd="1">+ Add a name</button>
      <button class="btn sm primary" data-anonsave="1">Save swaps</button></div>
    ${v.saved ? `
      ${v.left.length ? `<p class="hint" style="color:var(--bad)">Still in the text: ${v.left.map(esc).join(", ")}.</p>` : ""}
      ${v.has_images ? `<p class="hint">Images and the logo aren't changed. Check they don't show the client. The anonymized report hides an uploaded logo.</p>` : ""}
      <details class="fold"><summary>${v.preview.length} sentence${v.preview.length === 1 ? "" : "s"} change</summary>
        <ul>${v.preview.map(x => `<li><s>${esc(x.before)}</s><br>${mark(x.before, x.after)}</li>`).join("")}</ul></details>
      <div class="dls" style="margin-top:12px">
        ${rr ? `<a class="dl" href="${P2}/report/pdf?anonymized=1"><span><b>Report PDF, anonymized</b><small>Same design, names swapped</small></span></a>` : ""}
        <a class="dl" href="${P2}/export/case-study?anonymized=1"><span><b>Case study, anonymized</b><small>PDF</small></span></a>
        <a class="dl" href="${P2}/export/one-pager?anonymized=1"><span><b>One-pager, anonymized</b><small>PDF</small></span></a>
        <a class="dl" href="${P2}/export/portfolio?anonymized=1"><span><b>Portfolio page, anonymized</b><small>HTML</small></span></a>
      </div>` : ""}`;
}
async function loadSignoffs() {
  const list = await act(() => api("GET", `${P()}/signoffs`));
  if (list) showSignoffs(list);
}
function showSignoffs(list) {
  const box = $("#solinks"); if (!box) return;
  const ST = { open: ["Waiting for the client", ""], answered: ["Answered", "ok"], expired: ["Expired", "bad"],
               changed: ["Case study changed since: send a new link", "bad"] };
  const day = v => v ? new Date(v).toLocaleDateString() : "";
  box.innerHTML = !list.length ? `<p class="hint">No sign-off links yet.</p>` : `<ul class="vlist">${list.map(x => {
    const [label, cls] = ST[x.state] || [x.state, ""];
    const answers = x.state !== "answered" ? "" : `<ul class="soans">${x.items.map(it => {
      const act = it.action === "confirm" ? `<span class="so ok">Confirmed</span>`
        : it.action === "fix" ? `<span class="so warn">Fix suggested</span>` : `<span class="so bad">Remove</span>`;
      const btn = it.action === "confirm" ? "" : it.applied ? `<span class="hint">applied</span>`
        : `<button class="btn sm" data-use="${esc(x.token)}:${esc(it.id)}">${it.action === "fix" ? "Use this wording" : "Remove sentence"}</button>`;
      return `<li>${act}<div class="sotext">${esc(it.text)}${it.action === "fix" ? `<div class="sofix">→ ${esc(it.suggestion)}</div>` : ""}</div>${btn}</li>`;
    }).join("")}</ul>`;
    return `<li class="sorow"><div class="vmeta" style="width:100%">
        <div class="sohead"><a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.url.replace(/^https?:\/\//, ""))}</a>
          <span class="so ${cls}">${label}</span></div>
        <small>${x.contact ? esc(x.contact) + " · " : ""}${x.items.length} sentences · sent ${day(x.created_at)}
          ${x.state === "answered" ? ` · answered by ${esc(x.signed_by)} on ${day(x.submitted_at)} · ${x.decision === "named" ? "name may be published" : "<b>keep anonymous</b>"}` : ` · expires ${day(x.expires_at)}`}</small>
        ${answers}</div>
      ${x.state === "answered" ? "" : `<div class="vbtn"><button class="btn sm" data-vcopy="${esc(x.url)}">Copy</button>
        <button class="btn sm ghost" data-socancel="${esc(x.token)}">Cancel</button></div>`}
    </li>`; }).join("")}</ul>`;
}
async function loadLinks() {
  const links = await act(() => api("GET", `${P()}/published`));
  if (links) showLinks(links);
}
function showLinks(links) {
  const box = $("#vlinks"); if (!box) return;
  const live = links.filter(l => !l.revoked);
  const ev = { full: "quotes", masked: "masked quotes", labels: "check results only" };
  box.innerHTML = !live.length ? `<p class="hint">Nothing published yet.</p>` : `<ul class="vlist">${live.map(l => `
    <li class="${l.current ? "" : "old"}">
      <img src="/v/${esc(l.token)}/qr.svg" alt="QR code for the link" width="56" height="56">
      <div class="vmeta"><a href="${esc(l.url)}" target="_blank" rel="noopener">${esc(l.url.replace(/^https?:\/\//, ""))}</a>
        <small>${esc(new Date(l.created_at).toLocaleDateString())} · ${ev[l.evidence] || l.evidence}${l.anonymized ? " · anonymized" : l.show_client ? "" : " · client hidden"}
          · ${l.views} view${l.views === 1 ? "" : "s"} · ${l.checks} sentence${l.checks === 1 ? "" : "s"} checked
          ${l.current ? "" : `<b class="tag">older version</b>`}</small></div>
      <div class="vbtn"><button class="btn sm" data-vcopy="${esc(l.url)}">Copy</button>
        <button class="btn sm ghost" data-revoke="${esc(l.token)}">Unpublish</button></div>
    </li>`).join("")}</ul>${live.some(l => !l.current) ? `<p class="hint">An older version keeps showing what was approved then, with a note that the case study has changed. Publish again to share the new version.</p>` : ""}`;
}
function fmtRow(k, s) {
  const blocking = !s.label || s.label === "unsupported" || s.label === "contradicted";
  const editing = S.editing === "f" + k + s.id;
  return `<div class="claim ${blocking ? "bad" : s.label === "supported" ? "ok" : ""}">
    <div class="s">${editing ? `<textarea data-fed="${esc(k + s.id)}" aria-label="Edit sentence">${esc(s.text)}</textarea>` : esc(s.text)}</div>
    <div class="m">${chip(s.label)}${blocking ? `<span class="why">${esc(s.reason)}</span>` : ""}
      <div class="acts">${editing ? `<button class="btn sm primary" data-k="${k}" data-fsave="${esc(s.id)}">Save and re-check</button><button class="btn sm ghost" data-cancel="1">Cancel</button>`
        : `<button class="btn sm" data-k="${k}" data-fedit="${esc(s.id)}">Edit</button><button class="btn sm ghost danger" data-k="${k}" data-fdel="${esc(s.id)}">Delete</button>`}</div></div></div>`;
}

function tabDetails() {
  const r = S.rec;
  $("#tab").innerHTML = `
    <div class="panel"><h3 style="margin-top:0">Your original notes</h3><p class="hint">The only source of truth. Every sentence is checked against this.</p>
      <pre class="source">${esc(r.source_text)}</pre></div>
    <div class="panel" style="margin-top:14px"><h3 style="margin-top:0">Facts found in your notes (${r.facts.length})</h3>
      <p class="hint">Each fact must quote your notes word for word. Facts whose quote isn't in your notes are dropped before writing.</p>
      <div style="overflow:auto"><table><thead><tr><th>Fact</th><th>Quote from your notes</th><th>Topic</th></tr></thead>
      <tbody>${r.facts.map(f => `<tr><td>${esc(f.statement)}</td><td><i>${esc(f.quote)}</i></td><td>${esc(f.field.replace("_", " "))}</td></tr>`).join("")}</tbody></table></div>
      ${r.dropped_facts.length ? `<p style="color:var(--bad);margin-top:12px">${r.dropped_facts.length} fact(s) dropped because their quote wasn't in your notes.</p>` : ""}</div>
    <div class="panel" style="margin-top:14px"><h3 style="margin-top:0">History</h3>
      <div style="overflow:auto"><table><thead><tr><th>When (UTC)</th><th>What</th><th>Who</th><th>Detail</th></tr></thead>
      <tbody>${[...r.history].reverse().map(h => `<tr><td>${esc(h.at.replace("T", " ").slice(0, 16))}</td><td>${esc(h.action)}</td><td>${esc(h.by)}</td><td>${esc(h.detail)}</td></tr>`).join("")}</tbody></table></div>
      <p class="hint">AI engine: ${esc(r.engine)}</p></div>
    <div style="display:flex;gap:.5rem;margin-top:18px;flex-wrap:wrap">
      <button class="btn" id="regen">Rewrite the draft from scratch</button>
      <button class="btn danger" id="delproj">Delete this case study</button></div>`;
  $("#regen").onclick = () => { if (confirm("Rewrite the draft? Your edits will be lost.")) regenerate(); };
  $("#delproj").onclick = async () => {
    if (!confirm("Delete this case study for good?")) return;
    if (await act(() => api("DELETE", P()), "Deleted.")) { await refreshSide(); location.hash = "#new"; }
  };
}
async function regenerate() {
  const done = busy(["Reading your notes and pulling out the facts", "Writing the case study from those facts only", "Checking every sentence against your notes"]);
  try { await update(api("POST", `${P()}/generate`), "Draft written."); } finally { done(); }
}

/* ---------------------------------------------------------------- designed report */
const PATH_NAME = { title: "Title", subtitle: "Subtitle", client_line: "Client line", challenge_intro: "Challenge intro",
  brief: "The brief", solution_intro: "Solution intro", tech: "Tools", conclusion: "Closing line", quote: "Quote",
  challenges: "Challenge", pillars: "What we did", steps: "Approach step", metrics: "Big number", comparisons: "Before / after",
  outcomes: "Outcome", tags: "Tag", timeline: "Milestone", summary: "Executive summary", intro: "Introduction",
  approach_intro: "Approach intro", implementation_intro: "Implementation intro", objectives: "Objective",
  lessons: "Lesson / next step", team: "Team chart", budget: "Budget figure", architecture: "Architecture diagram",
  facts: "Project fact" };
const HEADLINE = { summary: "Summary headline", intro: "Introduction headline", challenge: "Challenge headline",
  objectives: "Objectives headline", approach: "Approach headline", solution: "Solution headline",
  implementation: "Delivery headline", technology: "Technology headline", results: "Results headline",
  journey: "Timeline headline", close: "Closing headline", lessons: "Lessons headline" };
const pathName = p => { const [h, i] = p.split("."); if (h === "headlines") return HEADLINE[i] || "Headline"; return (PATH_NAME[h] || h) + (i !== undefined ? ` ${+i + 1}` : ""); };
async function brandOptions() {
  if (!S.brands) S.brands = await act(() => api("GET", "/api/brands"));
  return S.brands ? S.brands.brands : [];
}
async function addLogoBrand() {
  const d = document.createElement("dialog");
  d.className = "confirm";
  d.innerHTML = `<h3>Use my logo</h3><p>Upload your logo — CaseForge takes your colours from it. You can fine-tune them later under Brand kits.</p>
    <label>Company name<input id="lgname" type="text" value="${esc(S.me.workspace_name || "")}"></label>
    <label style="margin-top:10px">Logo (PNG or JPG)<input id="lgfile" type="file" accept="image/png,image/jpeg"></label>
    <div class="row" style="margin-top:18px"><button class="btn" value="no">Cancel</button><button class="btn primary" value="yes">Apply</button></div>`;
  document.body.appendChild(d); d.showModal();
  d.querySelector('[value="no"]').onclick = () => { d.close(); d.remove(); };
  d.querySelector('[value="yes"]').onclick = async () => {
    const f = d.querySelector("#lgfile").files[0];
    if (!f) { toast("Choose your logo file first.", true); return; }
    const fd = new FormData(); fd.append("file", f); fd.append("name", d.querySelector("#lgname").value);
    const kit = await act(() => api("POST", "/api/brands/from-logo", fd));
    d.close(); d.remove();
    if (!kit) return;
    S.brands = null; saveBrand(kit.id);
    await update(api("POST", `${P()}/report/brand`, { brand_id: kit.id }), "Your brand is applied.");
  };
}
async function designReport(brandId, quiet, keepText) {
  if (keepText) return update(api("POST", `${P()}/report`, { brand_id: brandId, keep_text: true }), "New design — same checked text.");
  const done = busy(["Choosing a layout from your content", "Picking the key numbers, process and story", "Checking every element against your notes"]);
  try { return await update(api("POST", `${P()}/report`, { brand_id: brandId }), quiet ? null : "Report designed."); } finally { done(); }
}
async function tabReport() {
  const r = S.rec, el = $("#tab"), d = r.report;
  // no ready-made looks to pick from: Auto (your logo, else matched to your notes) plus brand kits you made yourself
  const brands = (await brandOptions()).filter(b => !String(b.id).startsWith("preset:"));
  const want = S.reportBrand || savedBrand();
  const cur = (brands.find(b => b.id === want) || (d && brands.find(b => b.kit.name === d.brand.name)) || brands[0] || {}).id || "auto";
  // automatic: approved case study + no report (or one built from an older version) → design it now
  if (!d || d.based_on_hash !== r.approved_hash) {
    if (S.autoDesigned === r.approved_hash) {
      el.innerHTML = `<div class="empty-state"><p>The report couldn't be designed automatically.</p><button class="btn primary" id="retry">Try again</button></div>`;
      $("#retry").onclick = () => designReport(cur); return;
    }
    S.autoDesigned = r.approved_hash;
    el.innerHTML = `<div class="empty-state"><p>Designing your report…</p></div>`;
    await designReport(cur, true); return;
  }
  const blockers = r.report_blockers || [], ready = r.report_ready;
  const els = d.elements.filter(e => !e.deleted);
  const bad = els.filter(e => !e.label || e.label === "unsupported" || e.label === "contradicted");
  el.innerHTML = `
    <div class="rbar">
      ${brands.length > 1 ? `<label class="inline">Brand <select id="rbrand">${brands.map(b => `<option value="${esc(b.id)}" ${b.id === cur ? "selected" : ""}>${esc(b.name)}</option>`).join("")}</select></label>`
        : `<input type="hidden" id="rbrand" value="auto">`}
      <span class="hint">${esc(d.layout?.frame || "")} · ${esc(d.layout?.theme || "")} · ${esc(d.layout?.story || "")} story · ${els.length} elements checked</span>
      <span style="flex:1"></span>
      <label class="btn sm ghost" title="The report takes this logo and its colours">${r.input.logo ? "Change logo" : "Add logo"}<input id="plogo" type="file" accept="image/png,image/jpeg" hidden></label>
      <button class="btn sm ghost" id="rrewrite" title="The AI words the report again from your approved text. New wording is checked again, so something may turn red.">Rewrite text</button>
      <button class="btn sm ghost" id="rdesign" title="A new layout, theme, cover and graph style. The checked text stays exactly as it is.">Redesign</button></div>
    <div class="report-wrap">
      <div class="preview"><iframe id="rprev" title="Report preview" src="${P()}/report/preview?t=${Date.now()}"></iframe></div>
      <div class="relems">
        <div class="chat panel">
          <div class="chat-head"><b>Change it by asking</b><span class="hint">New text is checked against your notes</span></div>
          <div class="chat-log" id="chatlog">${(d.chat || []).length ? d.chat.map(m => `<div class="msg ${m.role}">${esc(m.text)}</div>`).join("")
            : `<div class="msg ai">Tell me what to change, in your own words — the design, the graphs, the colours, the order, any text. You can also tell me a fact to add to your notes. I only use facts from your notes.</div>`}</div>
          <form id="chatform" class="chat-in"><input id="chatin" type="text" autocomplete="off" placeholder="Describe the change you want…" aria-label="Ask for a change">
            <button class="btn primary" type="submit">Send</button></form>
        </div>
        ${bad.length ? `<div class="next bad"><b>${bad.length} element${bad.length > 1 ? "s" : ""} not backed by your notes.</b> Edit or remove ${bad.length > 1 ? "them" : "it"} to approve.</div>
          <div class="doc">${bad.map(reportRow).join("")}</div>`
          : `<div class="next ok"><b>Every number and sentence is backed by your notes.</b> Check the preview, then approve.</div>`}
        ${d.coverage && d.coverage.total ? `<div class="next ok"><b>Nothing from your notes is left out.</b> All ${d.coverage.total} approved sentences are in the report: ${d.coverage.designed} on the designed pages${d.coverage.facts ? `, ${d.coverage.facts} in the Project facts table at the end` : ""}. ${(d.layout?.pages?.length || 0) + 1} pages.</div>` : ""}
        ${d.layout && d.layout.notes.length ? `<details class="fold"><summary>Why this layout</summary><ul>${d.layout.notes.map(n => `<li>${esc(n)}</li>`).join("")}</ul></details>` : ""}
        ${d.warnings.length ? `<details class="fold"><summary>Layout &amp; brand notes (${d.warnings.length})</summary><ul>${d.warnings.map(w => `<li>${esc(w)}</li>`).join("")}</ul></details>` : ""}
        <details class="fold" ${S.openElems ? "open" : ""} id="allel"><summary>Edit text (${els.length - bad.length} checked elements)</summary>
          <div class="doc">${els.filter(e => !bad.includes(e)).map(reportRow).join("")}</div></details>
      </div>
    </div>
    <div class="approve"><div>${ready ? "<b>Approved.</b> Your report is ready to download." : blockers.length ? `<b>${blockers.length} thing${blockers.length > 1 ? "s" : ""} to fix first</b>` : "<b>Looks right?</b> Approve it and it's ready to send."}</div>
      <div style="display:flex;gap:.5rem;flex-wrap:wrap">
        ${ready ? `<a class="btn primary" href="#p/${esc(r.id)}/outputs">Next: download →</a>` : `<button class="btn primary" id="rapprove" ${blockers.length ? "disabled" : ""}>Approve report</button>`}
      </div></div>`;
  $("#allel").ontoggle = e => { S.openElems = e.target.open; };
  $("#rbrand").onchange = async e => {
    const v = e.target.value;
    if (v === "__new") { e.target.value = cur; return addLogoBrand(); }
    saveBrand(v); await update(api("POST", `${P()}/report/brand`, { brand_id: v }), "New look applied.");
  };
  const log = $("#chatlog"); log.scrollTop = log.scrollHeight;
  const send = async text => {
    if (!text.trim()) return;
    log.insertAdjacentHTML("beforeend", `<div class="msg user">${esc(text)}</div><div class="msg ai typing">Working on it…</div>`);
    log.scrollTop = log.scrollHeight; $("#chatin").value = ""; $("#chatin").disabled = true;
    await update(api("POST", `${P()}/report/chat`, { text }));
    $("#chatin")?.focus();
  };
  $("#chatform").onsubmit = e => { e.preventDefault(); send($("#chatin").value); };
  $("#rdesign").onclick = () => designReport($("#rbrand").value, false, true);
  $("#rrewrite").onclick = () => designReport($("#rbrand").value);
  $("#plogo").onchange = async e => {
    const f = e.target.files[0]; if (!f) return;
    const fd = new FormData(); fd.append("file", f);
    saveBrand("auto"); S.reportBrand = "auto";
    await update(api("POST", `${P()}/logo`, fd), "Logo added — colours taken from it.");
  };
  const ap = $("#rapprove");
  if (ap) ap.onclick = async () => {
    const ok = await confirmBox("Approve this report?",
      `You checked the preview: the numbers, the headlines and the layout are right and it can go out. The approval is saved under your name (${esc(S.me.name)}) and printed in the PDF. Any later edit removes it.`, "Yes, approve");
    if (ok && await update(api("POST", `${P()}/report/approve`))) { toast("Report approved — ready to download."); go("outputs"); }
  };
  el.onclick = async e => {
    const t = e.target.closest("button"); if (!t) return;
    const x = t.dataset;
    if (x.say) { $("#chatin").value = x.say; $("#chatform").requestSubmit(); return; }
    if (x.redit) { S.editing = "r" + x.redit; tabReport(); }
    else if (x.rcancel) { S.editing = null; tabReport(); }
    else if (x.rsave) { const v = $(`textarea[data-red="${x.rsave}"]`).value; S.editing = null; update(api("POST", `${P()}/report/edit`, { path: x.rsave, text: v }), "Saved and re-checked."); }
    else if (x.rdel) update(api("POST", `${P()}/report/remove`, { path: x.rdel }), "Removed.");
    else if (x.rest) update(api("POST", `${P()}/report/estimate`, { path: x.rest, estimate: x.on === "1" }));
  };
}
function reportRow(e) {
  const blocking = !e.label || e.label === "unsupported" || e.label === "contradicted";
  const editing = S.editing === "r" + e.id, metric = e.id.startsWith("metrics.");
  const head = e.id.split(".")[0], fixed = ["facts", "team", "budget", "architecture"].includes(head);  // drawn from approved text
  const est = metric && S.rec.report.plan.metrics[+e.id.split(".")[1]]?.estimate;
  return `<div class="claim ${blocking ? "bad" : e.label === "supported" ? "ok" : ""}">
    <div class="s"><span class="hint" style="display:block;font-family:var(--sans)">${esc(pathName(e.id))}${est ? " · ESTIMATED" : ""}</span>
      ${editing ? `<textarea data-red="${esc(e.id)}" aria-label="Edit">${esc(e.text)}</textarea>` : esc(e.text)}</div>
    <div class="m">${chip(e.label)}${blocking ? `<span class="why">${esc(e.reason)}</span>` : ""}
      <div class="acts">${editing ? `<button class="btn sm primary" data-rsave="${esc(e.id)}">Save and re-check</button><button class="btn sm ghost" data-rcancel="1">Cancel</button>`
        : head === "facts" ? `<span class="hint">From the approved case study — edit it there.</span>`
        : `${fixed ? "" : `<button class="btn sm" data-redit="${esc(e.id)}">Edit</button>`}
           ${metric ? `<button class="btn sm ghost" data-rest="${esc(e.id)}" data-on="${est ? 0 : 1}">${est ? "Not an estimate" : "Mark estimate"}</button>` : ""}
           ${e.id === "title" ? "" : `<button class="btn sm ghost danger" data-rdel="${esc(e.id)}">Remove</button>`}`}</div></div></div>`;
}

/* ---------------------------------------------------------------- brand kits */
/* ---------------------------------------------------------------- proof library */
const LIB_EXAMPLES = ["logistics company, lower costs", "clinic, fewer no-shows", "replace spreadsheets with a dashboard", "mobile app for field staff"];
async function viewLibrary() {
  S.lib = S.lib || { q: "", results: null, picks: {}, anon: false };
  view.innerHTML = `
    <h1 class="page">Proof library</h1>
    <p class="sub">Search every approved case study in your workspace. Pick the sentences that fit a prospect and get a proof sheet: every line is quoted from an approved, fact-checked case study.</p>
    <form class="libsearch" id="libform" role="search">
      <input id="libq" type="text" enterkeyhint="search" placeholder="Who are you pitching? e.g. logistics company, wants lower costs" value="${esc(S.lib.q)}" aria-label="Describe the prospect">
      <button class="btn primary" type="submit">Search</button></form>
    <div class="samples"><span class="hint">Try:</span> ${LIB_EXAMPLES.map(x => `<button class="btn sm" type="button" data-ex="${esc(x)}">${esc(x)}</button>`).join(" ")}</div>
    <div id="libres"></div>
    <div class="libbar" id="libbar" hidden>
      <span id="libcount"></span>
      <label class="chk"><input type="checkbox" id="libanon" ${S.lib.anon ? "checked" : ""}> Hide all client names</label>
      <button class="btn sm" data-sheet="copy">Copy text</button>
      <button class="btn sm" data-sheet="view">Preview</button>
      <button class="btn sm primary" data-sheet="pdf">Download PDF</button>
    </div>`;
  $("#libform").onsubmit = e => { e.preventDefault(); libSearch($("#libq").value); };
  view.querySelector(".samples").onclick = e => { const x = e.target.dataset.ex; if (x) { $("#libq").value = x; libSearch(x); } };
  $("#libanon").onchange = e => { S.lib.anon = e.target.checked; };
  $("#libbar").onclick = e => { const k = e.target.dataset.sheet; if (k) libSheet(k); };
  if (S.lib.results) showLib(); else libSearch(S.lib.q);
}
async function libSearch(q) {
  S.lib.q = q.trim();
  const r = await act(() => api("GET", "/api/library?q=" + encodeURIComponent(S.lib.q)));
  if (!r) return;
  S.lib.results = r.results; S.lib.n = r.n_approved; S.lib.picks = {};
  if (S.lib.q) r.results.slice(0, 3).forEach(p => {   // the best matches start ticked, as the sheet would pick them
    const ids = p.matches.slice(0, 4).map(m => m.id);
    const metric = p.metrics.find(m => !ids.includes(m.id)); if (metric) ids.push(metric.id);
    S.lib.picks[p.id] = new Set(ids);
  });
  showLib();
}
function libPicked() { return Object.values(S.lib.picks).reduce((n, s) => n + s.size, 0); }
function showLib() {
  const box = $("#libres"); if (!box) return;
  const res = S.lib.results || [];
  const plural = n => `case stud${n === 1 ? "y" : "ies"}`;
  if (!S.lib.n) box.innerHTML = `<div class="next warn"><b>No approved case studies yet.</b> Approve one and it shows up here.</div>`;
  else if (!res.length) box.innerHTML = `<p class="hint">Nothing matches “${esc(S.lib.q)}” in your ${S.lib.n} approved ${plural(S.lib.n)}. Try other words.</p>`;
  else box.innerHTML = `<p class="hint">${S.lib.q ? `${res.length} of ${S.lib.n} approved ${plural(S.lib.n)} match.` : `${S.lib.n} approved ${plural(S.lib.n)}. Search to rank them for a prospect.`} Tick the sentences you want on the sheet.</p>
    ${res.map(p => {
      const picked = S.lib.picks[p.id] || new Set();
      const rows = [...p.matches, ...p.metrics.filter(m => !p.matches.some(x => x.id === m.id)).map(m => ({ ...m, metric: true }))];
      return `<div class="panel libcard"><div class="head"><div>
          <h3><a href="#p/${esc(p.id)}">${esc(p.title)}</a></h3>
          <span class="hint">${p.client ? esc(p.client) + " · " : ""}${p.anonymous ? `<b class="tag">client stays anonymous</b> · ` : ""}approved by ${esc(p.approved_by)} on ${esc(p.approved_on)} · ${p.n_sentences} sentences</span></div></div>
        ${rows.length ? `<ul class="libpick">${rows.map(m => `<li><label><input type="checkbox" data-pid="${esc(p.id)}" data-cid="${esc(m.id)}" ${picked.has(m.id) ? "checked" : ""}>
          <span>${esc(m.text)}${m.metric ? ` <span class="so ok">result</span>` : ""}</span></label></li>`).join("")}</ul>` : `<p class="hint">No sentence matches the search. Open it to see everything.</p>`}
      </div>`; }).join("")}`;
  box.onchange = e => {
    const t = e.target; if (!t.dataset.cid) return;
    const set = S.lib.picks[t.dataset.pid] = S.lib.picks[t.dataset.pid] || new Set();
    if (t.checked) set.add(t.dataset.cid); else set.delete(t.dataset.cid);
    libBar();
  };
  libBar();
}
function libBar() {
  const n = libPicked(), bar = $("#libbar"); if (!bar) return;
  const k = Object.values(S.lib.picks).filter(s => s.size).length;
  bar.hidden = !n;
  $("#libcount").textContent = `${n} sentence${n === 1 ? "" : "s"} from ${k} case stud${k === 1 ? "y" : "ies"}`;
}
async function libSheet(kind) {
  const picks = Object.fromEntries(Object.entries(S.lib.picks).filter(([, s]) => s.size).map(([k, s]) => [k, [...s]]));
  const body = { q: S.lib.q, picks, anonymized: S.lib.anon };
  if (kind === "copy") {
    const r = await act(() => api("POST", "/api/library/sheet", body)); if (!r) return;
    await navigator.clipboard.writeText(r.text).then(() => toast("Proof sheet copied."), () => toast("Couldn't copy.", true));
    return;
  }
  const done = kind === "pdf" ? busy(["Laying out the proof sheet", "Making the PDF"]) : () => {};
  try {
    const res = await fetch(`/api/library/sheet/${kind}`, { method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    if (!res.ok) { const d = await res.json().catch(() => ({})); throw new Error(d.detail || "Couldn't make the sheet."); }
    const url = URL.createObjectURL(await res.blob());
    if (kind === "pdf") { const a = document.createElement("a"); a.href = url; a.download = "proof-sheet.pdf"; document.body.appendChild(a); a.click(); a.remove(); }
    else window.open(url, "_blank", "noopener");
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  } catch (e) { toast(e.message, true); } finally { done(); }
}
async function viewBrands() {
  S.brands = await act(() => api("GET", "/api/brands"));
  if (!S.brands) return;
  const list = S.brands.brands, b = S.brandEdit;
  view.innerHTML = `<h1 class="page">Brand kits</h1>
    <p class="sub">Colours, fonts, logo and writing rules. Every designed report follows the kit you pick — and warns you when copy breaks a rule.</p>
    <div class="grid3">${list.map(k => `<div class="card brandcard">
      <div class="sw">${["primary", "accent", "ink", "surface", "dark"].map(c => `<i style="background:${esc(k.kit.colors[c])}"></i>`).join("")}</div>
      <h3>${esc(k.name)}${k.preset ? ` <span class="chip none">example</span>` : ""}</h3>
      <p>${esc(k.kit.heading_font)} / ${esc(k.kit.body_font)}${k.logo ? " · logo" : ""}</p>
      ${k.warnings.length ? `<p style="color:var(--bad)">${esc(k.warnings[0])}</p>` : ""}
      <div style="display:flex;gap:.4rem;flex-wrap:wrap"><button class="btn sm" data-bedit="${esc(k.id)}">${k.preset ? "Copy &amp; edit" : "Edit"}</button>
      ${k.preset ? "" : `<button class="btn sm ghost danger" data-bdel="${esc(k.id)}">Delete</button>`}</div></div>`).join("")}</div>
    <div class="panel" style="margin-top:18px"><h3 style="margin-top:0">Import from brand guidelines</h3>
      <p class="hint">Paste the guideline text or upload the PDF/Word file. CaseForge pulls out colours, fonts and banned words — you check them before saving.</p>
      <div class="two"><label>Brand name<input id="bname" placeholder="Acme Consulting"></label><label>Guidelines file<input type="file" id="bfile"></label></div>
      <label>Or paste the text<textarea id="btext" rows="4"></textarea></label>
      <button class="btn primary" id="bimport">Read guidelines</button></div>
    <div id="beditor"></div>`;
  if (b) brandEditor(b);
  view.onclick = async e => {
    const t = e.target.closest("button"); if (!t) return;
    if (t.dataset.bedit) { const k = list.find(x => x.id === t.dataset.bedit); S.brandEdit = { ...k, id: k.preset ? "" : k.id, kit: structuredClone(k.kit) }; if (k.preset) S.brandEdit.kit.name += " (copy)"; viewBrands(); }
    else if (t.dataset.bdel) { if (confirm("Delete this brand kit?") && await act(() => api("DELETE", `/api/brands/${t.dataset.bdel}`), "Deleted.")) viewBrands(); }
  };
  $("#bimport").onclick = async () => {
    const fd = new FormData(); fd.append("name", $("#bname").value || "Imported brand"); fd.append("text", $("#btext").value);
    if ($("#bfile").files[0]) fd.append("file", $("#bfile").files[0]);
    const done = busy(["Reading the guidelines", "Finding colours, fonts and rules"]);
    try { const k = await act(() => api("POST", "/api/brands/import", fd)); if (k) { S.brandEdit = k; viewBrands(); } } finally { done(); }
  };
}
function brandEditor(b) {
  const k = b.kit, fonts = S.brands.fonts, c = k.colors;
  const sel = (id, opts, v) => `<select id="${id}">${opts.map(o => `<option ${o === v ? "selected" : ""}>${esc(o)}</option>`).join("")}</select>`;
  $("#beditor").innerHTML = `<div class="panel" style="margin-top:18px"><h3 style="margin-top:0">${b.id ? "Edit" : "New"} brand kit</h3>
    ${b.warnings?.length ? `<div class="next warn">${b.warnings.map(esc).join("<br>")}</div>` : ""}
    <div class="two"><label>Name<input id="k_name" value="${esc(k.name)}"></label><label>Company<input id="k_company" value="${esc(k.company)}"></label></div>
    <div class="colors">${Object.keys(c).map(n => `<label>${n}<input type="color" data-col="${n}" value="${esc(c[n])}"></label>`).join("")}</div>
    <div class="two"><label>Heading font${sel("k_hf", fonts, k.heading_font)}</label><label>Body font${sel("k_bf", fonts, k.body_font)}</label></div>
    <div class="two"><label>Shape motif${sel("k_motif", ["hexagon", "circle", "bars", "none"], k.motif)}</label><label>Accent bar${sel("k_bar", ["left", "top", "none"], k.accent_bar)}</label></div>
    <div class="two"><label>Voice${sel("k_voice", ["we", "third person"], k.voice)}</label><label>Max words per sentence<input id="k_max" type="number" min="10" max="60" value="${esc(k.max_sentence_words)}"></label></div>
    <label>Banned words (comma separated)<input id="k_banned" value="${esc(k.banned_words.join(", "))}"></label>
    <label>Closing call to action<input id="k_cta" value="${esc(k.cta_text)}"></label>
    <label>Logo (PNG/JPG)${b.id ? `<input type="file" id="k_logo" accept="image/png,image/jpeg">` : `<span class="hint"> — save the kit first, then add a logo</span>`}</label>
    <div style="display:flex;gap:.5rem;margin-top:12px"><button class="btn primary" id="k_save">Save brand kit</button><button class="btn ghost" id="k_cancel">Cancel</button></div></div>`;
  $("#k_cancel").onclick = () => { S.brandEdit = null; viewBrands(); };
  $("#k_save").onclick = async () => {
    const kit = { ...k, name: $("#k_name").value || "Brand", company: $("#k_company").value, heading_font: $("#k_hf").value, body_font: $("#k_bf").value,
      motif: $("#k_motif").value, accent_bar: $("#k_bar").value, voice: $("#k_voice").value, max_sentence_words: +$("#k_max").value || 28,
      banned_words: $("#k_banned").value.split(",").map(s => s.trim()).filter(Boolean), cta_text: $("#k_cta").value, colors: { ...c } };
    document.querySelectorAll("[data-col]").forEach(i => { kit.colors[i.dataset.col] = i.value.toUpperCase(); });
    const res = await act(() => api("POST", "/api/brands", { id: b.id, kit }), "Brand kit saved.");
    if (!res) return;
    const f = $("#k_logo")?.files[0];
    if (f) { const fd = new FormData(); fd.append("file", f); await act(() => api("POST", `/api/brands/${res.id}/logo`, fd), "Logo uploaded."); }
    S.brandEdit = null; S.reportBrand = res.id; viewBrands();
  };
}

/* ---------------------------------------------------------------- settings */
const initials = n => String(n || "?").trim().split(/\s+/).slice(0, 2).map(w => w[0]).join("").toUpperCase();
function viewSettings() {
  const m = S.me, own = m.owner;
  view.innerHTML = `<h1 class="page">Settings</h1>
    <p class="sub">Your account, and the workspace you share with your team.</p>
    <div class="settings">
    <div class="scol">
    <section class="panel" id="s-profile"><h3>Profile</h3>
      <p class="hint">Your name shows in the review history when you approve or edit something. It never goes on a report.</p>
      <form id="fprofile" class="sform"><div class="who"><span class="avatar" aria-hidden="true">${esc(initials(m.name))}</span>
        <div class="two"><div class="field"><label for="p_name">Name</label><input id="p_name" type="text" autocomplete="name" value="${esc(m.name)}" required></div>
        <div class="field"><label for="p_email">Email</label><input id="p_email" type="email" autocomplete="email" value="${esc(m.email)}" required></div></div></div>
        <div class="go"><button class="btn primary" type="submit">Save profile</button></div></form></section>

    <section class="panel" id="s-password"><h3>Password</h3>
      <form id="fpw" class="sform"><div class="two">
        <div class="field"><label for="pw_cur">Current password</label><input id="pw_cur" type="password" autocomplete="current-password" required></div>
        <div class="field"><label for="pw_new">New password</label><input id="pw_new" type="password" autocomplete="new-password" minlength="8" required><div class="hint">At least 8 characters.</div></div></div>
        <div class="go"><button class="btn primary" type="submit">Change password</button></div></form></section>

    <section class="panel" id="s-workspace"><h3>Workspace</h3>
      <p class="hint">Everyone in this workspace sees the same case studies. Nobody else can.
        If the name is your company or agency, it goes on report headers as the publisher.</p>
      <form id="fws" class="sform"><div class="field"><label for="ws_name">Workspace name</label>
        <input id="ws_name" type="text" value="${esc(m.workspace_name)}" ${own ? "" : "disabled"} required>
        ${own ? "" : `<div class="hint">Only the owner can rename it.</div>`}</div>
        ${own ? `<div class="go"><button class="btn primary" type="submit">Save name</button></div>` : ""}</form>
      <div class="invite"><div><span class="lbl">Invite code</span><code id="inv">${esc(m.invite_code)}</code>
        <div class="hint">Teammates enter it when they create an account.</div></div>
        <div class="row"><button class="btn sm" id="copyinv" type="button">Copy code</button>
        ${own ? `<button class="btn sm ghost" id="newinv" type="button">New code</button>` : ""}</div></div></section>

    <section class="panel" id="s-members"><h3>Members <span class="count">${m.members.length}</span></h3>
      <ul class="members">${m.members.map(x => `<li><span class="avatar sm" aria-hidden="true">${esc(initials(x.name))}</span>
        <span class="mname">${esc(x.name)}${x.id === m.id ? ` <small>(you)</small>` : ""}<small class="mail">${esc(x.email)}</small></span>
        ${x.owner ? `<span class="chip ok">Owner</span>` : ""}
        ${own && !x.owner ? `<button class="btn sm ghost danger" data-rm="${esc(x.id)}" data-name="${esc(x.name)}">Remove</button>` : ""}</li>`).join("")}</ul>
      <p class="hint">${m.quota_left} of ${m.daily_limit} AI actions left today for you. Writing a draft or a format uses one.</p></section>

    <section class="panel dz" id="s-danger"><h3>Leave or delete</h3>
      ${m.members.length > 1 ? `<div class="drow"><div><b>Leave this workspace</b><p class="hint">You move to a new empty workspace. The team keeps its case studies.</p></div>
        <button class="btn sm danger" id="leave">Leave workspace</button></div>` : ""}
      <div class="drow"><div><b>Delete account</b><p class="hint">${m.members.length > 1
        ? (own ? "The next oldest member becomes owner. The team keeps its case studies." : "The team keeps its case studies.")
        : "You're the only member, so this also deletes the workspace and all its case studies."}</p></div>
        <button class="btn sm danger" id="delacc">Delete account</button></div></section>
    </div></div>`;

  const after = async (me, msg) => { if (me) { S.me = me; renderChrome(); viewSettings(); toast(msg); } };
  $("#fprofile").onsubmit = async e => { e.preventDefault();
    after(await act(() => api("POST", "/api/me/profile", { name: $("#p_name").value, email: $("#p_email").value })), "Profile saved."); };
  $("#fpw").onsubmit = async e => { e.preventDefault();
    const ok = await act(() => api("POST", "/api/me/password", { current: $("#pw_cur").value, new: $("#pw_new").value }), "Password changed.");
    if (ok) e.target.reset(); };
  if (own) {
    $("#fws").onsubmit = async e => { e.preventDefault();
      after(await act(() => api("POST", "/api/workspace/name", { name: $("#ws_name").value })), "Workspace renamed."); };
    $("#newinv").onclick = async () => {
      if (await confirmBox("Make a new invite code?", "The old code stops working. People already in the workspace stay.", "New code"))
        after(await act(() => api("POST", "/api/workspace/invite")), "New code ready.");
    };
  }
  $("#copyinv").onclick = () => navigator.clipboard.writeText(S.me.invite_code).then(() => toast("Copied."));
  view.querySelectorAll("[data-rm]").forEach(b => b.onclick = async () => {
    if (await confirmBox(`Remove ${b.dataset.name}?`, "They move to their own empty workspace and lose access to these case studies.", "Remove"))
      after(await act(() => api("POST", `/api/workspace/members/${b.dataset.rm}/remove`)), "Removed.");
  });
  const leave = $("#leave");
  if (leave) leave.onclick = async () => {
    if (!await confirmBox("Leave this workspace?", "You'll lose access to its case studies unless someone invites you back.", "Leave")) return;
    const me = await act(() => api("POST", "/api/me/leave"));
    if (me) { S.me = me; await refreshSide(); toast("You left the workspace."); viewSettings(); }
  };
  $("#delacc").onclick = async () => {
    const pw = await confirmBox("Delete your account?", `This can't be undone.</p>
      <div class="field"><label for="delpw">Your password</label><input id="delpw" type="password" autocomplete="current-password"></div><p>`, "Delete account");
    if (!pw) return;
    if (await act(() => api("POST", "/api/me/delete", { password: pw }))) { S.me = null; location.href = "/"; }
  };
}

/* ---------------------------------------------------------------- router */
async function route() {
  const h = location.hash || "";
  S.editing = null;
  if (h === "#signup" || h === "#login") { if (S.me) { location.hash = "#new"; return; } renderChrome(); viewAuth(h.slice(1)); return; }
  if (!S.me) { location.hash = "#login"; return; }
  renderChrome();
  const m = h.match(/^#p\/([^/]+)(?:\/(\w+))?/);
  if (m) await viewProject(m[1], m[2] || "review");
  else if (h === "#settings" || h === "#team") viewSettings();
  else if (h === "#brands") await viewBrands();
  else if (h === "#library") await viewLibrary();
  else viewNew();
  renderChrome();
}
(async function start() {
  S.config = await api("GET", "/api/config").catch(() => ({}));
  try { S.me = await api("GET", "/api/me"); S.projects = await api("GET", "/api/projects"); } catch (e) { S.me = null; }
  window.addEventListener("hashchange", route);
  route();
})();
