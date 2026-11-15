/* AeroFox frontend. No build step; talks to the FastAPI backend under /api. */
(() => {
  "use strict";
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const store = {
    get(k, d) { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } },
    set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* private mode */ } },
  };
  const state = { session: null, busy: false, project: {}, filters: store.get("aerofox.filters", { measured: true, published: true, incident: true, metadata: true }) };
  const COLORS = ["#1f4e79", "#c55a11", "#548235", "#7030a0", "#2b8cbe", "#b8860b", "#8c564b", "#d62728"];

  // ------------------------------------------------------------ helpers
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const external = (url) => {
    try { return new URL(url).protocol === "https:"; } catch { return false; }
  };
  const exportUrl = (url) => /^\/api\/sessions\/[a-f0-9]{8,64}\/artifacts\/[\w-]+\.(csv|mmd)$/.test(url);
  function inline(s) {
    return esc(s)
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\[([A-Z][A-Z0-9]*(?:-[A-Za-z0-9]+)*)\]/g, '<button type="button" class="cite" data-ev="$1">$1</button>')
      .replace(/\((F\d{2}|LIT-[A-Z0-9-]+|PSI-\d+)\)/g, '<button type="button" class="cite" data-ev="$1">$1</button>');
  }
  function markdown(text) {
    const out = []; let list = null;
    for (const raw of String(text).split("\n")) {
      const line = raw.trimEnd();
      const m = line.match(/^\s*[-*•]\s+(.*)$/) || line.match(/^\s*\d+[.)]\s+(.*)$/);
      if (m) { if (!list) { list = []; } list.push(`<li>${inline(m[1])}</li>`); continue; }
      if (list) { out.push(`<ul>${list.join("")}</ul>`); list = null; }
      const h = line.match(/^#{1,4}\s+(.*)$/);
      if (h) { out.push(`<p><strong>${inline(h[1])}</strong></p>`); continue; }
      if (line.trim()) out.push(`<p>${inline(line)}</p>`);
    }
    if (list) out.push(`<ul>${list.join("")}</ul>`);
    return out.join("");
  }
  async function api(path, opts = {}) {
    const res = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
    let body = null;
    try { body = await res.json(); } catch { /* non-JSON */ }
    if (!res.ok) {
      const msg = body?.detail ? (typeof body.detail === "string" ? body.detail : "invalid input") : body?.error || `HTTP ${res.status}`;
      const e = new Error(msg); e.status = res.status; e.rid = res.headers.get("X-Request-ID"); throw e;
    }
    return body;
  }
  const evClass = (t) => t.startsWith("measured") || t.startsWith("model") ? "measured" : t.startsWith("incident") ? "incident" : t === "metadata" ? "metadata" : "published";

  // ------------------------------------------------------------ sessions and history
  function history() { return store.get("aerofox.history", []); }
  function saveHistory(h) { store.set("aerofox.history", h.slice(0, 25)); renderHistory(); }
  function renderHistory() {
    const h = history();
    $("#history").innerHTML = h.length ? h.map((c) => `<button data-sid="${esc(c.id)}" class="${c.id === state.session ? "active" : ""}" title="${esc(c.title)}">${esc(c.title)}</button>`).join("")
      : '<div class="small" style="padding:4px 10px;color:#9fb0c8">No conversations yet</div>';
  }
  function rememberConversation(sid, firstMessage) {
    const h = history().filter((c) => c.id !== sid);
    const prev = history().find((c) => c.id === sid);
    h.unshift({ id: sid, title: prev?.title || firstMessage.slice(0, 60), t: Date.now() });
    saveHistory(h);
  }
  async function openConversation(sid) {
    state.pending?.abort();
    const navigation = state.navigation = (state.navigation || 0) + 1;
    showView("chat");
    try {
      const s = await api(`/api/sessions/${sid}`);
      if (navigation !== state.navigation) return;
      state.session = sid; state.project = s.project || {};
      $("#thread").innerHTML = ""; $("#home").classList.add("hidden");
      for (const t of s.turns) {
        if (t.role === "user") addUser(t.text);
        else addAssistant({ answer: t.text, blocks: [], evidence: [], warnings: [], mode: "restored" });
      }
      renderHistory();
    } catch (e) {
      if (navigation !== state.navigation) return;
      saveHistory(history().filter((c) => c.id !== sid));
      newConversation();
      addError("That conversation has expired on the server (sessions are kept for 6 hours). A new one was started.");
    }
  }
  function newConversation() {
    state.pending?.abort();
    state.navigation = (state.navigation || 0) + 1;
    state.session = null; state.project = {};
    $("#thread").innerHTML = ""; $("#home").classList.remove("hidden");
    showView("chat"); renderHistory(); $("#input").focus();
  }

  // ------------------------------------------------------------ rendering
  function addUser(text) {
    const d = document.createElement("div"); d.className = "msg-user"; d.textContent = text; $("#thread").append(d); scrollEnd();
  }
  function addError(msg) {
    const d = document.createElement("div"); d.className = "err"; d.textContent = msg; $("#thread").append(d); scrollEnd();
  }
  function scrollEnd() { const s = $("#scroll"); s.scrollTop = s.scrollHeight; }

  function chartBlock(b, host) {
    const traces = (b.series || []).filter(s => Array.isArray(s.x) && Array.isArray(s.y) && s.x.length > 0 && s.x.length === s.y.length).map((s, i) => {
      const t = { name: s.name, x: s.x, y: s.y, text: s.text, hovertemplate: s.text ? "%{text}<br>%{x}, %{y}<extra>%{fullData.name}</extra>" : undefined };
      const color = COLORS[i % COLORS.length];
      if (b.kind === "bar") {
        Object.assign(t, { type: "bar", marker: { color } });
        if (s.error_plus) t.error_y = { type: "data", symmetric: false, array: s.error_plus, arrayminus: s.error_minus, color: "#333" };
      } else {
        const mode = s.mode || (b.kind === "line" ? "lines" : "markers");
        Object.assign(t, { type: "scatter", mode, line: { color, width: 2 }, marker: { color, size: s.marker ? 13 : 6, opacity: s.marker ? 1 : 0.7, symbol: s.marker === "star" ? "star" : s.marker === "diamond" ? "diamond" : "circle", line: s.marker ? { color: "#111", width: 1 } : undefined } });
        if (s.marker === "star") { t.mode = "markers+text"; t.textposition = "top right"; t.textfont = { size: 11 }; }
      }
      return t;
    });
    const layout = {
      margin: { l: 64, r: 18, t: 10, b: 52 }, font: { family: "Inter, system-ui, sans-serif", size: 12, color: "#2d3a4f" },
      xaxis: { title: { text: b.x_label }, gridcolor: "#eef1f5", zeroline: false, range: b.x_range },
      yaxis: { title: { text: b.y_label }, gridcolor: "#eef1f5", zeroline: false, range: b.y_range },
      legend: { orientation: "h", y: -0.22, font: { size: 11 } }, barmode: "group", paper_bgcolor: "#fff", plot_bgcolor: "#fff",
      shapes: (b.shapes || []).filter((s) => s.type === "vline").map((s) => ({ type: "line", x0: s.x, x1: s.x, yref: "paper", y0: 0, y1: 1, line: { dash: "dash", color: "#333", width: 1 } })),
      annotations: (b.shapes || []).filter((s) => s.type === "vline" && s.label).map((s) => ({ x: s.x, yref: "paper", y: 1, text: s.label, showarrow: false, xanchor: "left", font: { size: 11 } })),
    };
    const div = document.createElement("div"); div.className = "plot"; host.append(div);
    div.setAttribute("aria-label", [b.title, b.x_label, b.y_label].filter(Boolean).join(". "));
    const failed = () => {
      if (window.Plotly) {
        try { window.Plotly.purge(div); } catch { /* keep the source and CSV available */ }
      }
      div.className = "plot-fallback";
      div.textContent = exportUrl(b.csv_url) ? "The plot could not be displayed. Download its values as CSV." : "The plot could not be displayed.";
    };
    if (window.Plotly && traces.length) {
      Promise.resolve().then(() => window.Plotly.newPlot(div, traces, layout, {
        responsive: true, displaylogo: false, modeBarButtonsToRemove: ["lasso2d", "select2d"],
        toImageButtonOptions: { format: "png", filename: "aerofox-chart", scale: 2 },
      })).then(() => div.setAttribute("data-rendered", "true")).catch(failed);
    } else { failed(); }
  }
  function flowchartBlock(block, host) {
    const list = document.createElement("ol");
    list.className = "decision-flow";
    list.setAttribute("aria-label", block.title);
    const nodes = new Map(block.nodes.map(node => [node.id, node]));
    const anchor = id => `workflow-${block.artifact_id}-${id}`;
    for (const node of nodes.values()) {
      const step = document.createElement("li");
      step.className = node.decision ? "decision-node" : "step-node";
      step.id = anchor(node.id);
      const edges = block.edges.filter(edge => edge.from === node.id && nodes.has(edge.to));
      step.innerHTML = `<div class="flow-label">${esc(node.label)} ${node.refs.map(ref => inline(`[${ref}]`)).join(" ")}</div>`;
      if (edges.length) {
        const branches = document.createElement("ul");
        branches.className = "flow-branches";
        branches.innerHTML = edges.map(edge => `<li><a href="#${esc(anchor(edge.to))}"><b>${esc(edge.label)}</b><span aria-hidden="true"> → </span>${esc(nodes.get(edge.to).label)}</a></li>`).join("");
        step.append(branches);
      }
      list.append(step);
    }
    host.append(list);
  }
  function tableBlock(columns, rows, host, levels) {
    const w = document.createElement("div"); w.className = "table-wrap" + (rows.length > 14 ? " tall" : "");
    w.innerHTML = `<table class="data"><thead><tr>${columns.map((c) => `<th>${esc(c)}</th>`).join("")}</tr></thead><tbody>${rows.map((r, i) =>
      `<tr>${r.map((c, j) => `<td class="${levels && levels[i] && levels[i][j - 1] ? "lv-" + esc(levels[i][j - 1]) : ""}">${esc(c)}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
    host.append(w);
  }
  function renderBlock(b, host) {
    if (b.type === "downloads") {
      const d = document.createElement("div"); d.className = "block downloads";
      d.innerHTML = (b.links || []).filter((link) => exportUrl(link.url)).map((l) => `<a href="${esc(l.url)}" download>⬇ ${esc(l.title)} (${esc(l.format || "CSV")})</a>`).join("") || "<p>No data to export yet.</p>";
      host.append(d); return;
    }
    const box = document.createElement("div"); box.className = "block"; box.dataset.blockType = b.type;
    const href = b.mermaid_url || b.csv_url;
    box.innerHTML = `<div class="block-head"><h4>${esc(b.title)}</h4>${exportUrl(href) ? `<a href="${esc(href)}" download>${b.mermaid_url ? "Download Mermaid (.mmd)" : "Download data (CSV)"}</a>` : ""}</div>`;
    host.append(box);
    if (b.type === "chart") chartBlock(b, box);
    else if (b.type === "flowchart") flowchartBlock(b, box);
    else if (b.type === "table") tableBlock(b.columns, b.rows, box);
    else if (b.type === "matrix") tableBlock([""].concat(b.columns), b.rows.map((r) => [r.label].concat(r.cells)), box, b.rows.map((r) => r.levels));
    const cap = document.createElement("div"); cap.className = "caption";
    cap.innerHTML = `${esc(b.caption || "")}<span class="src">Source: ${esc(b.source || "")}</span>`;
    box.append(cap);
  }
  function addAssistant(r) {
    const wrap = document.createElement("div"); wrap.className = "msg-ai";
    wrap.innerHTML = '<div class="avatar"><img src="assets/fox.svg" alt="" width="24" height="24"></div><div class="body"></div>';
    const body = $(".body", wrap);
    const pt = r.language === "pt";
    if (r.mode && r.mode !== "restored") {
      const meta = document.createElement("div"); meta.className = "meta-row";
      meta.innerHTML = r.mode === "llm" ? `<span class="badge llm">${pt ? "Modelo local" : "Local model"} · ${esc(r.model || "")}</span>`
        : `<span class="badge off">${pt ? "Resposta offline" : "Offline engine"}</span>`;
      meta.innerHTML += `<span>${(r.elapsed_s ?? 0).toFixed(1)} s</span>`;
      if (r.project_changes && Object.keys(r.project_changes).length) meta.innerHTML += `<span>Updated project: ${esc(Object.keys(r.project_changes).join(", "))}</span>`;
      body.append(meta);
    }
    if (r.notice) { const n = document.createElement("div"); n.className = "notice"; n.textContent = r.notice; body.append(n); }
    const ans = document.createElement("div"); ans.className = "answer"; ans.innerHTML = markdown(r.answer || ""); body.append(ans);
    const mainResult = (r.verified_results || []).find(result => [
      "assess_atmosphere", "flex_run", "flex035_case_study", "saffire2_flow_case_study",
      "compare_ventilation_designs", "simulate_ventilation", "convert_units", "droplet_burn_time",
    ].includes(result.tool));
    if (mainResult) {
      const node = document.createElement("p");
      node.className = "verified-summary";
      node.innerHTML = `<strong>${pt ? "Resultado verificado" : "Verified result"}</strong> ${inline(mainResult.text)}`;
      body.append(node);
    }
    if (r.verified_results?.length) {
      const results = document.createElement("details");
      results.className = "trace";
      results.innerHTML = `<summary>${pt ? "Resultados verificados" : "Verified results"}</summary><ul>${r.verified_results.map(
        result => `<li>${inline(result.text)} ${result.evidence.map(id => inline(`[${id}]`)).join(" ")}</li>`
      ).join("")}</ul>`;
      body.append(results);
    }
    (r.blocks || []).forEach((b) => renderBlock(b, body));
    if (r.warnings && r.warnings.length && !/Limits of this answer|Limites desta resposta/.test(r.answer || "")) {
      const w = document.createElement("div"); w.className = "warnings";
      w.innerHTML = `<b>${pt ? "Limites da análise" : "Limits of this answer"}</b><ul>${r.warnings.map((x) => `<li>${inline(x)}</li>`).join("")}</ul>`;
      body.append(w);
    }
    const ev = (r.evidence || []).filter((e) => state.filters[evClass(e.evidence_type)] !== false);
    if (ev.length) {
      const g = document.createElement("div"); g.className = "evidence";
      g.innerHTML = ev.map((e, i) => `<button class="ev${i >= 6 ? " extra hidden" : ""}" data-ev="${esc(e.id)}"><div class="id">${esc(e.id)} · ${esc(e.status)}</div><div class="t">${esc(e.kind === "investigation" ? e.title : e.text)}</div><div class="s">${esc((e.source || "").slice(0, 90))}</div></button>`).join("");
      body.append(g);
      if (ev.length > 6) {
        const more = document.createElement("button"); more.className = "link-btn more-ev"; more.textContent = `Show all ${ev.length} evidence items`;
        more.addEventListener("click", () => { $$(".extra", g).forEach((x) => x.classList.remove("hidden")); more.hidden = true; });
        body.append(more);
      }
    }
    if (r.tools && r.tools.length) {
      const d = document.createElement("details"); d.className = "trace";
      d.innerHTML = `<summary>How this was computed (${r.tools.length} tool call${r.tools.length > 1 ? "s" : ""}, request ${esc(r.request_id || "")})</summary><ul>${r.tools.map((t) => `<li>${esc(t.name)} — ${t.ok ? "ok" : "failed: " + esc(t.error)} (${t.elapsed_s ?? "?"} s)</li>`).join("")}</ul>`;
      body.append(d);
    }
    $("#thread").append(wrap); scrollEnd();
  }

  // ------------------------------------------------------------ chat
  async function send(text) {
    text = (text || "").trim();
    if (!text || state.busy) return;
    state.busy = true; $("#send").disabled = true;
    const pending = new AbortController();
    state.pending = pending;
    $("#home").classList.add("hidden"); showView("chat");
    addUser(text);
    const typing = document.createElement("div"); typing.className = "typing";
    typing.innerHTML = '<span class="pulse"></span> Preparing a review from NASA evidence… <button type="button">Cancel</button>';
    typing.querySelector("button").onclick = () => pending.abort();
    $("#thread").append(typing); scrollEnd();
    try {
      const r = await api("/api/chat", { method: "POST", body: JSON.stringify({ message: text, session_id: state.session }), signal: pending.signal });
      typing.remove();
      if (pending.signal.aborted) return;
      const first = !state.session;
      state.session = r.session_id; state.project = r.project || {};
      if (first || !history().some((c) => c.id === r.session_id)) rememberConversation(r.session_id, text);
      addAssistant(r);
    } catch (e) {
      typing.remove();
      if (pending.signal.aborted) return;
      addError(e.status === 429 ? "Too many requests from this address — please wait a minute and try again."
        : e.status ? `${e.message}${e.rid ? ` (request ${e.rid})` : ""}` : "Cannot reach the AeroFox server. Is it still running?");
    } finally {
      state.pending = null;
      state.busy = false; $("#send").disabled = false;
    }
  }

  // ------------------------------------------------------------ drawers
  function openDrawer(id) { $$(".drawer").forEach((d) => (d.hidden = d.id !== id)); $("#scrim").hidden = false; }
  function closeDrawers() { $$(".drawer").forEach((d) => (d.hidden = true)); $("#scrim").hidden = true; }
  async function showEvidence(id) {
    openDrawer("evidenceDrawer");
    $("#evidenceBody").innerHTML = '<p class="muted">Loading…</p>';
    try {
      const e = await api(`/api/evidence/${encodeURIComponent(id)}`);
      $("#evidenceBody").innerHTML = `<div class="ev-detail"><p class="mono">${esc(e.id)} · ${esc(e.status)}</p><h3>${esc(e.title)}</h3>
        <p>${esc(e.text)}</p>${e.quote ? `<blockquote>“${esc(e.quote)}”</blockquote>` : ""}
        <dl><dt>Source</dt><dd>${esc(e.source)}</dd><dt>Locator</dt><dd>${esc(e.locator)}</dd>
        ${e.uncertainty ? `<dt>Uncertainty</dt><dd>${esc(e.uncertainty)}</dd>` : ""}${e.limitations ? `<dt>Limitations</dt><dd>${esc(e.limitations)}</dd>` : ""}
        ${external(e.url) ? `<dt>Link</dt><dd><a href="${esc(e.url)}" target="_blank" rel="noopener">${esc(e.url)}</a></dd>` : ""}</dl></div>`;
    } catch { $("#evidenceBody").innerHTML = '<p class="err">Evidence item not found.</p>'; }
  }
  function fillProjectForm() {
    const f = $("#projectForm"); const p = state.project || {};
    for (const el of f.elements) {
      if (!el.name) continue;
      const v = p[el.name];
      el.value = Array.isArray(v) ? v.join(", ") : v ?? "";
    }
  }
  async function saveProject(ev) {
    ev?.preventDefault();
    const f = $("#projectForm"); const body = {};
    for (const el of f.elements) {
      if (!el.name) continue;
      const v = el.value.trim();
      if (el.name === "materials") body.materials = v ? v.split(",").map((x) => x.trim()).filter(Boolean) : [];
      else if (["pressure_kPa", "o2_pct", "crew_size"].includes(el.name)) body[el.name] = v === "" ? null : Number(v);
      else body[el.name] = v || null;
    }
    try {
      if (!state.session) { const s = await api("/api/sessions", { method: "POST" }); state.session = s.session_id; rememberConversation(s.session_id, "Project setup"); }
      const r = await api(`/api/sessions/${state.session}/project`, { method: "PATCH", body: JSON.stringify(body) });
      state.project = r.project; $("#projectMsg").textContent = "Saved. All analyses in this conversation will use these values.";
      return true;
    } catch (e) { $("#projectMsg").textContent = `Not saved: ${e.message}`; return false; }
  }

  // ------------------------------------------------------------ library
  const views = { chat: "Research assistant", datasets: "NASA datasets", findings: "Findings", references: "References", fields: "Field dictionary", provenance: "Coverage & provenance" };
  function showView(v) {
    $("#viewTitle").textContent = views[v] || views.chat;
    $("#chatView").classList.toggle("hidden", v !== "chat");
    $("#libraryView").classList.toggle("hidden", v === "chat");
    $$(".nav-item").forEach((n) => n.classList.toggle("active", n.dataset.view === v));
    $("#sidebar").classList.remove("open");
  }
  async function openLibrary(v) {
    showView(v);
    const L = $("#library"); L.innerHTML = '<p class="muted">Loading…</p>';
    try {
      if (v === "datasets") {
        const inv = await api("/api/library/investigations");
        L.innerHTML = `<h2>NASA datasets</h2><p class="intro">The ${inv.length} combustion investigations in NASA's Physical Sciences Informatics repository. File counts are catalog entries referenced by PSI; AeroFox holds a verified ~40 MB snapshot of the analysis-ready tables, test sheets and droplet histories.</p><div class="lib-grid">${inv.map((i) =>
          `<div class="lib-card"><div class="k">${esc(i.accession)}</div><h3>${esc(i.acronym || i.title)}</h3><p>${esc(i.title)}</p>
           <p class="small muted">${esc(i.project_type)} · ${esc(i.flight_program || "—")} · ${esc(i.start || "")}–${esc(i.end || "")}</p>
           <p class="small">${(i.catalog_files || 0).toLocaleString()} files · ${((i.catalog_bytes || 0) / 1e9).toFixed(1)} GB referenced · ${i.n_experiment_tables} table(s) · license ${esc(i.license)}</p>
           ${external(i.psi_url) ? `<a href="${esc(i.psi_url)}" target="_blank" rel="noopener">Open in PSI ↗</a>` : ""}<button class="link-btn" style="color:var(--accent)" data-ask="Tell me about ${esc(i.acronym || i.accession)} (${esc(i.accession)}).">Ask AeroFox</button></div>`).join("")}</div>
          <h2 style="margin-top:28px">Processed tables</h2><p class="intro">Download the cleaned tables AeroFox computes from (raw values are kept next to cleaned ones).</p>
          <div class="lib-grid">${["flex_tests", "flex_droplet_fits", "flex035_timeseries", "saffire_samples", "saffire2_flow", "bass2_tests", "same_reduced", "same_r_detectors", "cfi_tests", "investigations"].map((t) => `<div class="lib-card"><h3>${t}</h3><a href="/api/datasets/${t}.csv" download>Download CSV</a></div>`).join("")}</div>`;
      } else if (v === "findings") {
        const f = await api("/api/library/findings");
        L.innerHTML = `<h2>Findings</h2><p class="intro">Results produced by the AeroFox analysis notebook from NASA data. Each finding states its method, uncertainty and limits, and is cited in answers by its id.</p><div class="lib-grid">${f.map((x) =>
          `<div class="lib-card finding"><div class="k">${esc(x.id)} · ${esc(x.status)}</div><h3>${esc(x.title)}</h3><p>${esc(x.text)}</p><p class="small muted">${esc(x.locator)}</p>${x.limitations ? `<p class="small"><b>Limits:</b> ${esc(x.limitations)}</p>` : ""}</div>`).join("")}</div>`;
      } else if (v === "references") {
        const r = await api("/api/library/references");
        L.innerHTML = `<h2>References</h2><p class="intro">NASA sources used by AeroFox. Quotations are short and attributed; full texts stay with NASA.</p><div class="lib-grid">${r.map((x) =>
          `<div class="lib-card"><div class="k">${esc(x.id)}</div><h3>${esc(x.title)}</h3><p class="small">${esc(x.authors || "")}${x.year ? " (" + esc(x.year) + ")" : ""}${x.venue ? ". " + esc(x.venue) : ""}</p>${external(x.url) ? `<a href="${esc(x.url)}" target="_blank" rel="noopener">Open source ↗</a>` : ""}</div>`).join("")}</div>`;
      } else if (v === "fields") {
        const d = await api("/api/library/fields");
        L.innerHTML = `<h2>Field dictionary</h2><p class="intro">Columns of the processed datasets, with units and meaning.</p>` + Object.entries(d).map(([t, spec]) =>
          `<div class="block"><div class="block-head"><h4>${esc(t)}</h4><a href="/api/datasets/${esc(t)}.csv" download>CSV</a></div><p class="caption">${esc(spec.description)} Source: ${esc(spec.source)}</p><div class="table-wrap"><table class="data"><thead><tr><th>field</th><th>unit</th><th>meaning</th></tr></thead><tbody>${Object.entries(spec.fields).map(([k, [u, m]]) => `<tr><td class="mono">${esc(k)}</td><td>${esc(u)}</td><td>${esc(m)}</td></tr>`).join("")}</tbody></table></div></div>`).join("");
      } else if (v === "provenance") {
        const p = await api("/api/library/provenance");
        const run = p.last_run || {};
        L.innerHTML = `<h2>Coverage &amp; provenance</h2><p class="intro">Every file in the snapshot is checksummed (SHA-256) and listed with its NASA source URL. AeroFox never needs NASA's servers to answer a question.</p>
          <div class="lib-grid"><div class="lib-card"><h3>Snapshot ${esc(p.snapshot)}</h3><p>${p.entries} files in manifest</p><p class="small">${Object.entries(p.by_status).map(([k, v]) => `<span class="tag">${esc(k)}: ${v}</span>`).join("")}</p><p class="small muted">Last acquisition: ${esc(run.started || "")} → ${esc(run.finished || "")}</p></div>
          <div class="lib-card"><h3>PSI catalog</h3><p>${p.derivation.entries.toLocaleString()} entries referenced (${(p.derivation.referenced_bytes / 1e12).toFixed(2)} TB); ${p.derivation.unique_keys.toLocaleString()} unique objects (${(p.derivation.referenced_bytes_dedup_name_size / 1e12).toFixed(2)} TB).</p><p class="small muted">Not downloaded: imagery and video stay in NASA PSI.</p></div>
          <div class="lib-card"><h3>Files by kind</h3><p class="small">${Object.entries(p.by_kind).map(([k, v]) => `<span class="tag">${esc(k)}: ${v}</span>`).join("")}</p></div></div>
          <p class="small muted" style="margin-top:16px">AeroFox is an independent student project for the NASA Space Apps Challenge. It is not endorsed by NASA. Analyses are preliminary and not a substitute for certified hazard analysis.</p>`;
      }
    } catch (e) { L.innerHTML = `<p class="err">Could not load this view: ${esc(e.message)}</p>`; }
  }

  // ------------------------------------------------------------ wiring
  function updateFilterState() {
    const off = Object.entries(state.filters).filter(([, v]) => !v).map(([k]) => k);
    $("#filterState").textContent = off.length ? `hiding: ${off.join(", ")}` : "";
  }
  document.addEventListener("click", (e) => {
    const t = e.target.closest("button, a"); if (!t) return;
    if (t.matches(".cite, .ev")) { showEvidence(t.dataset.ev); return; }
    if (t.dataset.prompt) { send(t.dataset.prompt); return; }
    if (t.dataset.ask) { send(t.dataset.ask); return; }
    if (t.dataset.view) { openLibrary(t.dataset.view); return; }
    if (t.dataset.sid) { openConversation(t.dataset.sid); return; }
    if (t.dataset.close) { closeDrawers(); }
  });
  $("#composer").addEventListener("submit", (e) => { e.preventDefault(); const v = $("#input").value; $("#input").value = ""; send(v); });
  $("#input").addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); $("#composer").requestSubmit(); } });
  $("#newChat").addEventListener("click", newConversation);
  for (const id of ["#openProject", "#composerProject"]) $(id).addEventListener("click", () => { fillProjectForm(); $("#projectMsg").textContent = ""; openDrawer("projectDrawer"); });
  $("#composerFilters").addEventListener("click", () => openDrawer("filterDrawer"));
  $("#projectForm").addEventListener("submit", saveProject);
  $("#analyseProject").addEventListener("click", async () => { if (await saveProject()) { closeDrawers(); send("Run a fire-safety design review of my project and chart the main factors."); } });
  $("#filterForm").addEventListener("change", (e) => { state.filters[e.target.name] = e.target.checked; store.set("aerofox.filters", state.filters); updateFilterState(); });
  $("#scrim").addEventListener("click", closeDrawers);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeDrawers(); });
  $("#openSidebar").addEventListener("click", () => $("#sidebar").classList.add("open"));
  $("#closeSidebar").addEventListener("click", () => $("#sidebar").classList.remove("open"));
  for (const el of $("#filterForm").elements) if (el.name) el.checked = state.filters[el.name] !== false;
  updateFilterState();

  (async function init() {
    renderHistory();
    try {
      const h = await api("/api/health");
      $("#snapshot").textContent = h.snapshot;
      $("#statusDot").className = "dot ok";
      $("#engineLabel").textContent = h.llm.ready ? `Local model ready · v${h.version}` : `Offline engine · v${h.version}`;
      $("#engineLabel").title = h.llm.ready ? `Model ${h.llm.model} · ${h.llm.runtime}` : "The local model is unavailable or switched off. Verified offline evidence remains available.";
      const [inv, fnd] = await Promise.all([api("/api/library/investigations"), api("/api/library/findings")]);
      $("#datasetCount").textContent = inv.length; $("#findingCount").textContent = fnd.length;
    } catch {
      $("#statusDot").className = "dot warn"; $("#engineLabel").textContent = "Server unreachable";
    }
  })();
})();
