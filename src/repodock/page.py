"""The dashboard: one HTML page that talks to the local API."""

FAVICON = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="7" fill="#0f766e"/><path d="M7 20h18l-2.5 5h-13z" fill="#fff"/><rect x="9" y="8" width="6" height="10" rx="1.5" fill="#fff"/><rect x="17" y="11" width="6" height="7" rx="1.5" fill="#fff" opacity=".75"/></svg>'

PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>repodock</title>
<link rel="icon" href="favicon.svg">
<style>
:root {
  --bg: #f5f7f8; --card: #fff; --text: #172026; --muted: #5f6b76; --line: #e2e7ea; --soft: #eef2f4;
  --accent: #0f766e; --accent-soft: #d8f0ec; --red: #c2352b; --red-soft: #fbe4e1; --amber: #a15c07; --amber-soft: #fdf0d8;
  --green: #15803d; --code: #0f1720; --code-text: #d7e1e8;
}
@media (prefers-color-scheme: dark) {
  :root { --bg: #0d1114; --card: #151b20; --text: #e4eaee; --muted: #93a1ad; --line: #26303a; --soft: #1d252c;
          --accent: #2dd4bf; --accent-soft: #123a36; --red: #f87171; --red-soft: #3a1a1a; --amber: #fbbf24; --amber-soft: #3a2c10;
          --green: #4ade80; --code: #0a0e11; --code-text: #cfd8df; }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text); font: 14px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; }
button, input, select { font: inherit; color: inherit; }
button { background: var(--soft); border: 1px solid var(--line); border-radius: 7px; padding: 5px 11px; cursor: pointer; white-space: nowrap; }
button:hover:not(:disabled) { border-color: var(--accent); }
button:disabled { opacity: .5; cursor: default; }
button.primary { background: var(--accent); border-color: var(--accent); color: #fff; font-weight: 600; }
@media (prefers-color-scheme: dark) { button.primary { color: #06201d; } }
button.danger { color: var(--red); }
button.link { background: none; border: 0; padding: 0; color: var(--accent); }
input[type=text], input[type=search], select { background: var(--card); border: 1px solid var(--line); border-radius: 7px; padding: 6px 10px; min-width: 0; }
input:focus, select:focus { outline: 2px solid var(--accent-soft); border-color: var(--accent); }
code, pre, .mono { font-family: ui-monospace, SFMono-Regular, Consolas, Menlo, monospace; font-size: 12.5px; }

header { position: sticky; top: 0; z-index: 5; background: var(--card); border-bottom: 1px solid var(--line); }
.bar { max-width: 1400px; margin: 0 auto; display: flex; gap: 14px; align-items: center; padding: 12px 24px; flex-wrap: wrap; }
.brand { font-weight: 700; font-size: 17px; display: flex; align-items: center; gap: 8px; }
.brand img { width: 22px; height: 22px; }
#add-form { flex: 1; display: flex; gap: 8px; min-width: 280px; max-width: 720px; }
#add-input { flex: 1; padding: 8px 12px; }
.where { color: var(--muted); font-size: 12.5px; margin-left: auto; }

.tools { max-width: 1400px; margin: 0 auto; padding: 16px 24px 0; display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.chip { border-radius: 999px; padding: 3px 12px; font-size: 13px; background: var(--card); color: var(--muted); }
.chip.on { background: var(--accent); border-color: var(--accent); color: #fff; }
#filter { margin-left: auto; width: 200px; }
main { max-width: 1400px; margin: 0 auto; padding: 8px 24px 60px; }
.group h2 { font-size: 15px; margin: 22px 0 10px; display: flex; gap: 8px; align-items: baseline; }
.group h2 small { color: var(--muted); font-weight: 400; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(400px, 1fr)); gap: 14px; align-items: start; }

.card { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 14px 16px; display: flex; flex-direction: column; gap: 9px; }
.card.running { border-color: var(--green); box-shadow: 0 0 0 1px var(--green) inset; }
.top { display: flex; gap: 8px; align-items: flex-start; }
.top .title { flex: 1; min-width: 0; }
.name { font-weight: 650; font-size: 15.5px; color: var(--text); text-decoration: none; overflow-wrap: anywhere; }
.name:hover { color: var(--accent); }
.meta { color: var(--muted); font-size: 12.5px; display: flex; gap: 10px; flex-wrap: wrap; margin-top: 1px; }
.desc { color: var(--muted); margin: 0; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.badge { font-size: 12px; font-weight: 600; border-radius: 999px; padding: 1px 9px; background: var(--soft); color: var(--muted); white-space: nowrap; }
.badge.run { background: var(--green); color: #fff; } .badge.busy { background: var(--amber-soft); color: var(--amber); }
.badge.bad { background: var(--red-soft); color: var(--red); }
.cmd { display: flex; gap: 6px; }
.cmd select { flex: 1; width: 100%; min-width: 0; text-overflow: ellipsis; }
.cmd input { flex: 1; min-width: 0; }
.hint { font-size: 12.5px; color: var(--muted); }
.hint.warn { color: var(--amber); } .hint.bad { color: var(--red); }
.actions { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
.actions .spacer { flex: 1; }
.actions button:not(.primary) { font-size: 13px; padding: 4px 9px; }
.log { background: var(--code); color: var(--code-text); border-radius: 8px; padding: 10px 12px; margin: 0; max-height: 320px; min-height: 80px; overflow: auto; white-space: pre-wrap; overflow-wrap: anywhere; }
.empty { text-align: center; color: var(--muted); padding: 80px 20px; }
.empty h2 { color: var(--text); margin: 0 0 6px; font-size: 20px; }

dialog { border: 1px solid var(--line); border-radius: 14px; background: var(--card); color: var(--text); padding: 0; width: min(620px, calc(100vw - 32px)); box-shadow: 0 20px 60px rgba(0,0,0,.25); }
dialog::backdrop { background: rgba(10,15,20,.45); }
.dlg { padding: 20px 22px; display: flex; flex-direction: column; gap: 12px; }
.dlg h3 { margin: 0; font-size: 17px; }
.dlg p { margin: 0; }
.dlg pre { background: var(--code); color: var(--code-text); border-radius: 8px; padding: 10px 12px; margin: 0; white-space: pre-wrap; overflow-wrap: anywhere; }
.dlg .buttons { display: flex; gap: 8px; justify-content: flex-end; flex-wrap: wrap; margin-top: 4px; }
.callout { border-radius: 8px; padding: 10px 12px; background: var(--amber-soft); color: var(--text); }
.callout.info { background: var(--accent-soft); }
.pick { max-height: 50vh; overflow: auto; border: 1px solid var(--line); border-radius: 8px; }
.pick label { display: flex; gap: 10px; padding: 8px 12px; border-bottom: 1px solid var(--line); cursor: pointer; align-items: flex-start; }
.pick label:last-child { border-bottom: 0; }
.pick .info { flex: 1; min-width: 0; }
.pick .info b { overflow-wrap: anywhere; }
.pick .sub { color: var(--muted); font-size: 12.5px; }
.pick input { margin-top: 3px; }
#toast { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: var(--text); color: var(--bg); padding: 9px 16px; border-radius: 8px; opacity: 0; transition: opacity .2s; pointer-events: none; max-width: calc(100vw - 32px); z-index: 20; }
#toast.show { opacity: 1; }
@media (max-width: 640px) {
  .bar, .tools, main { padding-left: 16px; padding-right: 16px; }
  .grid { grid-template-columns: 1fr; }
  #filter { width: 100%; margin-left: 0; }
  .where { display: none; }
}
</style>
</head>
<body>
<header><div class="bar">
  <div class="brand"><img src="favicon.svg" alt="">repodock</div>
  <form id="add-form">
    <input id="add-input" type="text" placeholder="Paste a GitHub link, owner/repo or a username" autocomplete="off" spellcheck="false" aria-label="GitHub link">
    <button class="primary" id="add-btn" type="submit">Add</button>
  </form>
  <span class="where mono" id="where"></span>
</div></header>
<div class="tools" id="tools" hidden>
  <div id="owners" style="display:flex;gap:6px;flex-wrap:wrap"></div>
  <input id="filter" type="search" placeholder="Filter" aria-label="Filter repositories">
</div>
<main id="main"></main>

<dialog id="dlg"><form method="dialog" class="dlg" id="dlg-body"></form></dialog>
<div id="toast" role="status"></div>

<script>
const $ = (tag, attrs = {}, ...kids) => {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "value") el.value = v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat()) if (kid !== null && kid !== undefined && kid !== false) el.append(kid);
  return el;
};

async function api(path, body) {
  const opts = body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json", "X-Repodock": "1" }, body: JSON.stringify(body) };
  const res = await fetch(path, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || res.statusText);
  return data;
}

let toastTimer;
function toast(msg) {
  const t = document.getElementById("toast");
  t.textContent = msg; t.classList.add("show");
  clearTimeout(toastTimer); toastTimer = setTimeout(() => t.classList.remove("show"), 4000);
}

function ago(value) {
  if (!value) return "";
  const t = typeof value === "number" ? value * 1000 : new Date(value).getTime();
  const s = (Date.now() - t) / 1000;
  if (s < 60) return "just now";
  for (const [div, name] of [[31536000, "year"], [2592000, "month"], [86400, "day"], [3600, "hour"], [60, "minute"]])
    if (s >= div) { const n = Math.floor(s / div); return `${n} ${name}${n === 1 ? "" : "s"} ago`; }
}

// Dialogs ------------------------------------------------------------------
function dialog(build) {
  return new Promise(resolve => {
    const dlg = document.getElementById("dlg"), body = document.getElementById("dlg-body");
    body.replaceChildren();
    const close = value => { dlg.close(); resolve(value); };
    build(body, close);
    dlg.onclose = () => resolve(undefined);
    dlg.onkeydown = e => { if (e.key === "Escape") resolve(undefined); };
    dlg.showModal();
    const primary = body.querySelector("button.primary"); if (primary) primary.focus();
  });
}

function confirmRun(key, info) {
  return dialog((b, close) => {
    b.append($("h3", {}, `Run ${key}?`));
    if (!info.owned) b.append($("div", { class: "callout" },
      $("b", {}, `This code comes from ${info.owner}. `),
      "It will run on this computer with your permissions. Only run projects you trust."));
    if (info.missing_tool) b.append($("div", { class: "callout" }, `${info.missing_tool} doesn't seem to be installed, so this will probably fail. Install it first, or pick another run command.`));
    if (info.deps) {
      b.append($("p", {}, "It needs dependencies first. This command installs them into the project folder:"), $("pre", {}, info.deps));
      b.append($("p", {}, "Then it runs:"), $("pre", {}, info.command));
      b.append($("div", { class: "buttons" },
        $("button", { value: "cancel", onclick: () => close(null) }, "Cancel"),
        $("button", { type: "button", onclick: () => close({ install: false }) }, "Run without installing"),
        $("button", { class: "primary", type: "button", onclick: () => close({ install: true }) }, "Install and run")));
    } else {
      b.append($("p", {}, "This command will run in the project folder:"), $("pre", {}, info.command));
      b.append($("div", { class: "buttons" },
        $("button", { value: "cancel", onclick: () => close(null) }, "Cancel"),
        $("button", { class: "primary", type: "button", onclick: () => close({}) }, "Run")));
    }
  });
}

function askInstall(key, command) {
  return dialog((b, close) => {
    b.append($("h3", {}, "Install dependencies?"),
      $("p", {}, `${key} needs its dependencies before it runs. This installs them:`), $("pre", {}, command),
      $("div", { class: "buttons" },
        $("button", { value: "cancel", onclick: () => close(undefined) }, "Cancel"),
        $("button", { type: "button", onclick: () => close(false) }, "Run without installing"),
        $("button", { class: "primary", type: "button", onclick: () => close(true) }, "Install and run")));
  });
}

function pickRepos(owner, repos) {
  return dialog((b, close) => {
    const boxes = [];
    const rows = repos.map(r => {
      const box = $("input", { type: "checkbox", value: r.full_name, disabled: r.present });
      box.checked = r.suggested; boxes.push(box);
      const tags = [r.fork && "fork", r.archived && "archived", r.present && "already added"].filter(Boolean);
      return $("label", {}, box, $("div", { class: "info" },
        $("b", {}, r.name), tags.length ? $("span", { class: "badge", style: "margin-left:6px" }, tags.join(", ")) : null,
        r.description ? $("div", { class: "sub" }, r.description) : null,
        $("div", { class: "sub" }, [r.language, `${(r.size_kb / 1024).toFixed(1)} MB`, r.stars ? `★ ${r.stars}` : null, r.pushed_at ? `updated ${ago(r.pushed_at)}` : null].filter(Boolean).join(" · "))));
    });
    const count = $("span", {});
    const addBtn = $("button", { class: "primary", type: "button", onclick: () => close(boxes.filter(x => x.checked && !x.disabled).map(x => x.value)) });
    const refresh = () => {
      const picked = boxes.filter(x => x.checked && !x.disabled);
      const mb = repos.filter(r => picked.some(p => p.value === r.full_name)).reduce((s, r) => s + r.size_kb, 0) / 1024;
      addBtn.textContent = `Add ${picked.length} repo${picked.length === 1 ? "" : "s"}`;
      addBtn.disabled = !picked.length;
      count.textContent = `${picked.length} selected, about ${mb.toFixed(1)} MB`;
    };
    boxes.forEach(x => x.addEventListener("change", refresh));
    const setAll = on => { boxes.forEach(x => { if (!x.disabled) x.checked = on; }); refresh(); };
    b.append($("h3", {}, `Add repositories from ${owner}`),
      $("p", { class: "hint" }, "Forks and archived repositories are left out unless you tick them."),
      $("div", { class: "actions" }, $("button", { type: "button", class: "link", onclick: () => setAll(true) }, "Select all"), " · ",
        $("button", { type: "button", class: "link", onclick: () => setAll(false) }, "Select none"), $("span", { class: "spacer" }), count),
      $("div", { class: "pick" }, rows.length ? rows : $("p", { class: "hint", style: "padding:12px" }, "No public repositories.")),
      $("div", { class: "buttons" }, $("button", { value: "cancel", onclick: () => close(null) }, "Cancel"), addBtn));
    refresh();
  });
}

function confirmDelete(key) {
  return dialog((b, close) => {
    b.append($("h3", {}, `Delete ${key}?`),
      $("p", {}, "This stops it if it's running and deletes its folder, including installed dependencies and any changes you made there."),
      $("div", { class: "buttons" },
        $("button", { value: "cancel", onclick: () => close(false) }, "Cancel"),
        $("button", { class: "primary", type: "button", style: "background:var(--red);border-color:var(--red)", onclick: () => close(true) }, "Delete")));
  });
}

// Actions --------------------------------------------------------------------
async function run(key, command) {
  try {
    let res = await api("/api/run", { key, command });
    if (res.confirm) {
      const choice = await confirmRun(key, res.confirm);
      if (!choice) return;
      res = await api("/api/run", { key, confirmed: true, install: res.confirm.deps ? choice.install : undefined });
    }
    if (res.install) {
      const install = await askInstall(key, res.install.command);
      if (install === undefined) return;
      res = await api("/api/run", { key, confirmed: true, install });
    }
    openLogs.add(key);
    refresh();
  } catch (e) { toast(e.message); }
}

async function act(path, key, extra = {}) {
  try { await api(path, { key, ...extra }); refresh(); } catch (e) { toast(e.message); }
}

document.getElementById("add-form").addEventListener("submit", async e => {
  e.preventDefault();
  const input = document.getElementById("add-input"), btn = document.getElementById("add-btn");
  const text = input.value.trim(); if (!text) return;
  btn.disabled = true; btn.textContent = "Adding...";
  try {
    const res = await api("/api/add", { input: text });
    if (res.kind === "user") {
      const picked = await pickRepos(res.owner, res.repos);
      if (picked && picked.length) {
        const out = await api("/api/add-many", { repos: picked });
        const failed = Object.entries(out.errors);
        if (failed.length) toast(failed.map(([k, v]) => `${k}: ${v}`).join("; "));
        else toast(`Downloading ${out.added.length} repositories`);
      }
    } else {
      openLogs.add(res.key);
    }
    input.value = "";
    refresh();
  } catch (err) { toast(err.message); }
  finally { btn.disabled = false; btn.textContent = "Add"; }
});

// Rendering ------------------------------------------------------------------
const cards = new Map();          // key -> {el, parts}
const openLogs = new Set();       // keys whose log is visible
const logSeq = new Map();         // key -> last line number shown
let ownerFilter = "", textFilter = "", lastState = null;

function statusBadge(r) {
  const j = r.job;
  if (j && j.running) {
    const text = { run: "Running", install: "Installing", clone: "Downloading", update: "Updating" }[j.kind] || "Busy";
    return $("span", { class: "badge " + (j.kind === "run" ? "run" : "busy") }, j.stopping ? "Stopping" : text);
  }
  if (r.status === "failed") return $("span", { class: "badge bad" }, "Download failed");
  if (j && j.kind === "run" && j.exit_code !== null && !j.stopping && j.exit_code !== 0) return $("span", { class: "badge bad" }, `Exited (${j.exit_code})`);
  if (j && j.kind === "install" && j.exit_code) return $("span", { class: "badge bad" }, "Install failed");
  return null;
}

function buildCard(key) {
  const p = {};
  p.el = $("div", { class: "card" });
  p.badge = $("span", {});
  p.name = $("a", { class: "name", target: "_blank", rel: "noopener" });
  p.meta = $("div", { class: "meta" });
  p.desc = $("p", { class: "desc" });
  p.select = $("select", { "aria-label": "Run command" });
  p.custom = $("input", { type: "text", class: "mono", placeholder: "Type a command", spellcheck: "false", "aria-label": "Custom run command" });
  p.save = $("button", { type: "button" }, "Save");
  p.cmdRow = $("div", { class: "cmd" }, p.select, p.custom, p.save);
  p.hints = $("div", {});
  p.run = $("button", { class: "primary", type: "button" });
  p.openApp = $("button", { type: "button" }, "Open app");
  p.install = $("button", { type: "button" }, "Install deps");
  p.logBtn = $("button", { type: "button" }, "Log");
  p.folder = $("button", { type: "button", title: "Open the project folder" }, "Folder");
  p.update = $("button", { type: "button", title: "Download the latest version" }, "Update");
  p.retry = $("button", { type: "button" }, "Retry");
  p.del = $("button", { type: "button", class: "danger" }, "Delete");
  p.log = $("pre", { class: "log", hidden: true });
  p.el.append(
    $("div", { class: "top" }, $("div", { class: "title" }, p.name, p.meta), p.badge),
    p.desc, p.cmdRow, p.hints,
    $("div", { class: "actions" }, p.run, p.openApp, p.install, p.logBtn, $("span", { class: "spacer" }), p.folder, p.update, p.retry, p.del),
    p.log);

  p.select.addEventListener("change", async () => {
    if (p.select.value === "__custom") { p.custom.hidden = false; p.save.hidden = false; p.custom.focus(); return; }
    await act("/api/command", key, { command: p.select.value });
  });
  const saveCustom = () => act("/api/command", key, { command: p.custom.value });
  p.save.addEventListener("click", saveCustom);
  p.custom.addEventListener("keydown", e => { if (e.key === "Enter") saveCustom(); });
  p.run.addEventListener("click", () => {
    const r = lastState.repos.find(x => x.key === key);
    if (r && r.job && r.job.running) act("/api/stop", key); else run(key);
  });
  p.openApp.addEventListener("click", () => { const r = lastState.repos.find(x => x.key === key); if (r && r.job && r.job.url) window.open(r.job.url, "_blank", "noopener"); });
  p.install.addEventListener("click", () => { openLogs.add(key); act("/api/install", key); });
  p.logBtn.addEventListener("click", () => { if (openLogs.has(key)) openLogs.delete(key); else openLogs.add(key); refresh(); });
  p.folder.addEventListener("click", () => act("/api/open", key));
  p.update.addEventListener("click", () => { openLogs.add(key); act("/api/update", key); });
  p.retry.addEventListener("click", async () => {
    try { await api("/api/delete", { key, files: true }); await api("/api/add", { input: key }); openLogs.add(key); refresh(); } catch (e) { toast(e.message); }
  });
  p.del.addEventListener("click", async () => { if (await confirmDelete(key)) { cards.get(key)?.el.remove(); cards.delete(key); act("/api/delete", key, { files: true }); } });
  return p;
}

function updateCard(p, r) {
  const j = r.job, running = !!(j && j.running), ready = r.status === "ready" && r.exists;
  p.el.classList.toggle("running", running && j.kind === "run");
  p.badge.replaceChildren(statusBadge(r) || "");
  p.name.textContent = r.name || r.key.split("/")[1];
  p.name.href = r.html_url || `https://github.com/${r.key}`;
  p.meta.replaceChildren(...[r.language, r.stars ? `★ ${r.stars}` : null, r.pushed_at ? `updated ${ago(r.pushed_at)}` : null,
    r.git === false && r.exists ? "zip download" : null].filter(Boolean).map(t => $("span", {}, t)));
  p.desc.textContent = r.description || ""; p.desc.hidden = !r.description;

  p.cmdRow.hidden = !ready;
  if (ready && document.activeElement !== p.select && document.activeElement !== p.custom) {
    const opts = r.candidates.map(c => $("option", { value: c.command, title: c.preview }, `${c.label}  ·  ${c.preview}`));
    if (r.custom) opts.push($("option", { value: r.command, title: r.command_preview }, `Custom · ${r.command_preview}`));
    opts.push($("option", { value: "__custom" }, "Custom command..."));
    p.select.replaceChildren(...opts);
    p.select.value = r.command || "__custom";
    const editing = !r.command;
    p.custom.hidden = !editing; p.save.hidden = !editing;
    if (!editing) p.custom.value = r.command || "";
  }
  const hints = [];
  if (ready && !r.candidates.length && !r.command) hints.push($("div", { class: "hint warn" }, "repodock couldn't tell how to run this project. Check its README and type the command."));
  if (ready && r.missing_tool) hints.push($("div", { class: "hint bad" }, `Needs ${r.missing_tool}, which isn't installed.`));
  if (ready && r.deps) hints.push($("div", { class: "hint" + (r.needs_deps ? " warn" : "") }, "Dependencies: ", $("code", {}, r.deps), r.needs_deps ? " (not installed yet)" : " (installed)"));
  for (const n of (ready && r.notes) || []) hints.push($("div", { class: "hint" }, n));
  if (r.status === "failed" && r.error) hints.push($("div", { class: "hint bad" }, r.error));
  p.hints.replaceChildren(...hints);

  const busyOther = running && j.kind !== "run";
  p.run.hidden = !ready;
  p.run.textContent = running && j.kind === "run" ? "Stop" : "Run";
  p.run.disabled = busyOther && j.kind !== "install" ? true : false;
  if (running && j.kind === "install") p.run.textContent = "Stop";
  p.openApp.hidden = !(running && j.kind === "run" && j.url);
  p.install.hidden = !(ready && r.deps && !running);
  p.install.textContent = r.needs_deps ? "Install deps" : "Reinstall";
  p.folder.hidden = !r.exists;
  p.update.hidden = !ready || running;
  p.retry.hidden = r.status !== "failed";
  p.del.disabled = running && (j.kind === "clone" || j.kind === "update");
  const showLog = openLogs.has(r.key) && !!j;
  p.logBtn.hidden = !j;
  p.logBtn.textContent = showLog ? "Hide log" : "Log";
  if (showLog && p.log.hidden) { p.log.textContent = ""; logSeq.set(r.key, 0); }
  p.log.hidden = !showLog;
  if (showLog && (j.seq || 0) > (logSeq.get(r.key) || 0)) pullLog(r.key, p.log);
}

async function pullLog(key, pre) {
  try {
    const res = await api(`/api/log?key=${encodeURIComponent(key)}&after=${logSeq.get(key) || 0}`);
    if (!res.lines.length) return;
    const stick = pre.scrollHeight - pre.scrollTop - pre.clientHeight < 30;
    pre.append(res.lines.map(([, line]) => line).join("\n") + "\n");
    logSeq.set(key, res.lines[res.lines.length - 1][0]);
    if (pre.textContent.length > 400000) pre.textContent = pre.textContent.slice(-300000);
    if (stick) pre.scrollTop = pre.scrollHeight;
  } catch (e) { /* next poll retries */ }
}

function render(state) {
  lastState = state;
  document.getElementById("where").textContent = state.root;
  const main = document.getElementById("main");
  const repos = state.repos;
  document.getElementById("tools").hidden = !repos.length;
  if (!repos.length) {
    main.replaceChildren($("div", { class: "empty" }, $("h2", {}, "Nothing here yet"),
      $("p", {}, "Paste a GitHub link above, like https://github.com/owner/project, or just a username to pick from all of their repositories."),
      !state.git ? $("p", { class: "hint warn" }, "Git isn't installed, so repodock downloads zip archives. Install Git to update projects faster.") : null));
    cards.clear();
    main.dataset.sig = "";
    return;
  }
  const owners = {};
  for (const r of repos) { const o = r.key.split("/")[0]; owners[o] = (owners[o] || 0) + 1; }
  if (ownerFilter && !owners[ownerFilter]) ownerFilter = "";
  const chips = [["", `All (${repos.length})`], ...Object.entries(owners).map(([o, n]) => [o, `${o} (${n})`])];
  document.getElementById("owners").replaceChildren(...(Object.keys(owners).length > 1 ? chips : []).map(([o, label]) =>
    $("button", { type: "button", class: "chip" + (o === ownerFilter ? " on" : ""), onclick: () => { ownerFilter = o; render(lastState); } }, label)));

  const words = textFilter.toLowerCase().split(/\s+/).filter(Boolean);
  const visible = repos.filter(r => (!ownerFilter || r.key.split("/")[0] === ownerFilter)
    && words.every(w => `${r.key} ${r.description || ""} ${r.language || ""}`.toLowerCase().includes(w)));
  const groups = new Map();
  for (const r of visible) { const o = r.key.split("/")[0]; if (!groups.has(o)) groups.set(o, []); groups.get(o).push(r); }
  for (const r of repos) {
    if (!cards.has(r.key)) cards.set(r.key, buildCard(r.key));
    updateCard(cards.get(r.key), r);
  }
  for (const key of [...cards.keys()]) if (!repos.some(r => r.key === key)) cards.delete(key);
  // Rebuild the layout only when the set of visible cards changed, so typing and scrolling aren't disturbed.
  const signature = [...groups].map(([o, list]) => o + ":" + list.map(r => r.key).join(",")).join("|") + "|" + (state.me || "");
  if (main.dataset.sig === signature) return;
  main.dataset.sig = signature;
  const sections = [];
  for (const [owner, list] of groups) {
    const mine = state.me && owner.toLowerCase() === state.me.toLowerCase();
    sections.push($("section", { class: "group" }, $("h2", {}, owner, $("small", {}, `${list.length} repo${list.length === 1 ? "" : "s"}${mine ? " · you" : ""}`)),
      $("div", { class: "grid" }, list.map(r => cards.get(r.key).el))));
  }
  if (!sections.length) sections.push($("p", { class: "empty" }, "No repository matches the filter."));
  main.replaceChildren(...sections);
}

document.getElementById("filter").addEventListener("input", e => { textFilter = e.target.value; render(lastState); });

async function refresh() {
  try { render(await api("/api/state")); } catch (e) { /* server restarting */ }
}
refresh();
setInterval(() => { if (!document.hidden && !document.getElementById("dlg").open) refresh(); }, 1500);
</script>
</body>
</html>
"""
