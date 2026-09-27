"""The dashboard: one HTML page that talks to the local API (shown in the app window or a browser)."""

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
  --bg: #f4f6f7; --side: #eceff1; --card: #fff; --text: #172026; --muted: #5f6b76; --line: #e0e5e8; --soft: #eef2f4; --hover: #e6ebee;
  --accent: #0f766e; --on-accent: #fff; --red: #c2352b; --amber: #a15c07; --green: #15803d; --code: #0f1720; --code-text: #d7e1e8;
  --shadow: 0 1px 2px rgba(16,24,32,.05), 0 2px 8px rgba(16,24,32,.04);
  color-scheme: light;
}
:root[data-theme="dark"] {
  --bg: #0e1215; --side: #0b0f12; --card: #161c21; --text: #e4eaee; --muted: #93a1ad; --line: #252f38; --soft: #1d252c; --hover: #232c34;
  --red: #f87171; --amber: #fbbf24; --green: #4ade80; --code: #080b0e; --code-text: #cfd8df; --shadow: none;
  color-scheme: dark;
}
:root { --accent-soft: color-mix(in srgb, var(--accent) 16%, transparent); --red-soft: color-mix(in srgb, var(--red) 14%, transparent);
  --amber-soft: color-mix(in srgb, var(--amber) 16%, transparent); --green-soft: color-mix(in srgb, var(--green) 15%, transparent); }
* { box-sizing: border-box; }
[hidden] { display: none !important; }
html, body { height: 100%; }
body { margin: 0; background: var(--bg); color: var(--text); font: 14px/1.45 "Segoe UI Variable Text", "Segoe UI", system-ui, -apple-system, sans-serif; }
button, input, select, textarea { font: inherit; color: inherit; }
button { background: var(--soft); border: 1px solid var(--line); border-radius: 8px; padding: 5px 11px; cursor: pointer; white-space: nowrap; display: inline-flex; align-items: center; gap: 6px; }
button:hover:not(:disabled) { border-color: var(--accent); }
button:disabled { opacity: .5; cursor: default; }
button:focus-visible, a:focus-visible, input:focus-visible, select:focus-visible { outline: 2px solid var(--accent); outline-offset: 1px; }
button.primary { background: var(--accent); border-color: var(--accent); color: var(--on-accent); font-weight: 600; }
button.danger { color: var(--red); }
button.ghost { background: transparent; border-color: transparent; }
button.ghost:hover:not(:disabled) { background: var(--hover); border-color: transparent; }
button.link { background: none; border: 0; padding: 0; color: var(--accent); }
button.icon { padding: 5px; }
input[type=text], input[type=search], input[type=number], input[type=password], select, textarea { background: var(--card); border: 1px solid var(--line); border-radius: 8px; padding: 6px 10px; min-width: 0; }
input:focus, select:focus, textarea:focus { outline: 2px solid var(--accent-soft); border-color: var(--accent); }
code, pre, .mono { font-family: "Cascadia Mono", ui-monospace, SFMono-Regular, Consolas, Menlo, monospace; font-size: 12.5px; }
svg.i { width: 16px; height: 16px; flex: none; fill: none; stroke: currentColor; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
kbd { font: 11.5px ui-monospace, Consolas, monospace; border: 1px solid var(--line); border-bottom-width: 2px; border-radius: 5px; padding: 0 5px; background: var(--card); color: var(--muted); }

.app { display: grid; grid-template-columns: 232px 1fr; height: 100vh; }
aside { background: var(--side); border-right: 1px solid var(--line); display: flex; flex-direction: column; min-height: 0; }
.brand { font-weight: 700; font-size: 17px; display: flex; align-items: center; gap: 9px; padding: 16px 18px 10px; }
.brand img { width: 24px; height: 24px; }
nav { flex: 1; overflow: auto; padding: 4px 10px 12px; }
nav h4 { font-size: 11.5px; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); margin: 16px 8px 6px; font-weight: 600; }
.nav { width: 100%; justify-content: flex-start; background: transparent; border: 0; border-radius: 8px; padding: 6px 8px; color: var(--text); }
.nav:hover:not(:disabled) { background: var(--hover); }
.nav.on { background: var(--accent-soft); color: var(--accent); font-weight: 600; }
.nav .count { margin-left: auto; color: var(--muted); font-size: 12px; font-weight: 500; }
.nav img { width: 18px; height: 18px; border-radius: 50%; }
.dot { width: 8px; height: 8px; border-radius: 50%; background: var(--green); flex: none; }
.side-foot { border-top: 1px solid var(--line); padding: 10px; display: flex; flex-direction: column; gap: 2px; }

.content { display: flex; flex-direction: column; min-width: 0; min-height: 0; }
header { display: flex; gap: 10px; align-items: center; padding: 12px 24px; border-bottom: 1px solid var(--line); background: var(--card); flex-wrap: wrap; }
#menu-btn { display: none; }
#add-form { flex: 1; display: flex; gap: 8px; min-width: 260px; max-width: 760px; }
#add-input { flex: 1; padding: 8px 12px; }
.head-actions { display: flex; gap: 8px; margin-left: auto; align-items: center; }
.quick { color: var(--muted); }
.scroll { flex: 1; overflow: auto; }
.summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; padding: 18px 24px 4px; max-width: 1500px; }
.stat { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 10px 14px; box-shadow: var(--shadow); }
.stat b { display: block; font-size: 20px; font-weight: 650; }
.stat span { color: var(--muted); font-size: 12.5px; }
.toolbar { display: flex; gap: 8px; align-items: center; padding: 14px 24px 0; max-width: 1500px; flex-wrap: wrap; }
.toolbar h1 { font-size: 18px; margin: 0 auto 0 0; }
#filter { width: 220px; }
main { padding: 6px 24px 60px; max-width: 1500px; }
.group h2 { font-size: 14.5px; margin: 20px 0 10px; display: flex; gap: 8px; align-items: center; }
.group h2 img { width: 22px; height: 22px; border-radius: 50%; }
.group h2 small { color: var(--muted); font-weight: 400; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(380px, 1fr)); gap: 14px; align-items: start; }

.card { background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 14px 16px; display: flex; flex-direction: column; gap: 9px; box-shadow: var(--shadow); scroll-margin: 90px; }
.card.running { border-color: var(--green); box-shadow: 0 0 0 1px var(--green) inset; }
.card.flash { animation: flash 1.2s; }
@keyframes flash { 0%, 60% { box-shadow: 0 0 0 3px var(--accent); } }
.top { display: flex; gap: 10px; align-items: flex-start; }
.avatar { width: 34px; height: 34px; border-radius: 9px; background: var(--soft); flex: none; object-fit: cover; }
.top .title { flex: 1; min-width: 0; }
.name { font-weight: 650; font-size: 15px; color: var(--text); text-decoration: none; overflow-wrap: anywhere; }
.name:hover { color: var(--accent); }
.owner { color: var(--muted); font-weight: 400; }
.meta { color: var(--muted); font-size: 12.5px; display: flex; gap: 4px 10px; flex-wrap: wrap; margin-top: 1px; }
.desc { color: var(--muted); margin: 0; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.badges { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
.badge { font-size: 12px; font-weight: 600; border-radius: 999px; padding: 1px 9px; background: var(--soft); color: var(--muted); white-space: nowrap; }
.badge.run { background: var(--green); color: #fff; } .badge.busy { background: var(--amber-soft); color: var(--amber); }
.badge.bad { background: var(--red-soft); color: var(--red); } .badge.new { background: var(--accent-soft); color: var(--accent); }
.tag { font-size: 12px; border-radius: 6px; padding: 0 7px; background: var(--soft); color: var(--muted); border: 1px solid var(--line); }
.star { color: var(--muted); }
.star.on { color: #eab308; }
.star.on svg.i { fill: #eab308; }
.live { display: flex; gap: 14px; align-items: center; flex-wrap: wrap; font-size: 12.5px; color: var(--muted); background: var(--green-soft); border-radius: 9px; padding: 6px 10px; }
.live b { color: var(--text); font-weight: 600; }
.live .spacer { flex: 1; }
.cmd { display: flex; gap: 6px; }
.cmd select { flex: 1; width: 100%; min-width: 0; text-overflow: ellipsis; }
.cmd input { flex: 1; min-width: 0; }
.hint { font-size: 12.5px; color: var(--muted); display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.hint.warn { color: var(--amber); } .hint.bad { color: var(--red); }
.hints { display: flex; flex-direction: column; gap: 4px; }
.actions { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
.actions .spacer { flex: 1; }
.actions button:not(.primary) { font-size: 13px; padding: 4px 9px; }
.menu-wrap { position: relative; }
.menu { position: absolute; right: 0; top: calc(100% + 4px); background: var(--card); border: 1px solid var(--line); border-radius: 10px; box-shadow: 0 10px 30px rgba(0,0,0,.18); padding: 5px; z-index: 30; min-width: 190px; display: flex; flex-direction: column; }
.menu button { background: transparent; border: 0; justify-content: flex-start; padding: 7px 10px; border-radius: 7px; font-size: 13.5px; }
.menu button:hover:not(:disabled) { background: var(--hover); }
.menu hr { border: 0; border-top: 1px solid var(--line); margin: 4px 2px; }
.logbox { display: flex; flex-direction: column; gap: 6px; }
.logbar { display: flex; gap: 6px; align-items: center; }
.logbar input { flex: 1; padding: 4px 9px; font-size: 13px; }
.logbar select { font-size: 13px; padding: 4px 6px; max-width: 45%; }
.log { background: var(--code); color: var(--code-text); border-radius: 9px; padding: 10px 12px; margin: 0; max-height: 340px; min-height: 90px; overflow: auto; white-space: pre-wrap; overflow-wrap: anywhere; }
.log mark { background: #fde047; color: #111; border-radius: 2px; }

main.list .grid { grid-template-columns: 1fr; gap: 8px; }
main.list .card { flex-direction: row; flex-wrap: wrap; align-items: center; padding: 10px 14px; gap: 8px 14px; }
main.list .card .top { flex: 1 1 440px; min-width: min(440px, 100%); align-items: center; }
main.list .card .avatar { width: 28px; height: 28px; }
main.list .card .desc, main.list .card .cmdrow, main.list .card .hints { display: none; }
main.list .card .live { order: 2; flex: 0 1 auto; padding: 4px 10px; }
main.list .card .actions { order: 3; }
main.list .card .logbox { order: 4; flex-basis: 100%; }
main.list .card .actions .spacer { display: none; }

.empty { text-align: center; color: var(--muted); padding: 70px 20px; max-width: 560px; margin: 0 auto; }
.empty h2 { color: var(--text); margin: 0 0 8px; font-size: 22px; }
.empty .buttons { display: flex; gap: 8px; justify-content: center; margin-top: 16px; flex-wrap: wrap; }
.banner { margin: 14px 24px 0; max-width: 1452px; border-radius: 10px; padding: 9px 14px; background: var(--accent-soft); display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }

dialog { border: 1px solid var(--line); border-radius: 16px; background: var(--card); color: var(--text); padding: 0; width: min(640px, calc(100vw - 32px)); box-shadow: 0 24px 70px rgba(0,0,0,.3); }
dialog.wide { width: min(820px, calc(100vw - 32px)); }
dialog.palette { margin-top: 12vh; }
dialog::backdrop { background: rgba(10,15,20,.45); }
.dlg { padding: 20px 22px; display: flex; flex-direction: column; gap: 12px; max-height: calc(100vh - 60px); }
.dlg h3 { margin: 0; font-size: 17px; }
.dlg p { margin: 0; }
.dlg pre { background: var(--code); color: var(--code-text); border-radius: 9px; padding: 10px 12px; margin: 0; white-space: pre-wrap; overflow-wrap: anywhere; }
.dlg .buttons { display: flex; gap: 8px; justify-content: flex-end; flex-wrap: wrap; margin-top: 4px; align-items: center; }
.dlg .buttons .spacer { flex: 1; }
.dlg label.field { display: flex; flex-direction: column; gap: 4px; font-weight: 600; font-size: 13px; }
.dlg label.field span { font-weight: 400; color: var(--muted); }
.dlg .row { display: flex; gap: 8px; align-items: center; }
.dlg .row > input { flex: 1; }
.check { display: flex; gap: 10px; align-items: flex-start; cursor: pointer; }
.check input { margin-top: 3px; }
.check small { display: block; color: var(--muted); }
.callout { border-radius: 9px; padding: 10px 12px; background: var(--amber-soft); color: var(--text); }
.callout.info { background: var(--accent-soft); }
.tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--line); }
.tabs button { background: none; border: 0; border-bottom: 2px solid transparent; border-radius: 0; padding: 6px 10px; color: var(--muted); }
.tabs button.on { color: var(--text); border-bottom-color: var(--accent); font-weight: 600; }
.pick { max-height: 50vh; overflow: auto; border: 1px solid var(--line); border-radius: 10px; }
.pick > label, .pick > .item { display: flex; gap: 10px; padding: 9px 12px; border-bottom: 1px solid var(--line); align-items: flex-start; }
.pick > label { cursor: pointer; }
.pick > :last-child { border-bottom: 0; }
.pick .info { flex: 1; min-width: 0; }
.pick .info b { overflow-wrap: anywhere; }
.pick .sub { color: var(--muted); font-size: 12.5px; }
.pick input[type=checkbox] { margin-top: 3px; }
.envrow { display: grid; grid-template-columns: minmax(0, 2fr) minmax(0, 3fr) auto auto; gap: 6px; }
.segmented { display: inline-flex; border: 1px solid var(--line); border-radius: 9px; padding: 2px; background: var(--soft); }
.segmented button { border: 0; background: transparent; padding: 4px 12px; border-radius: 7px; }
.segmented button.on { background: var(--card); box-shadow: var(--shadow); font-weight: 600; }
.swatches { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.swatch { width: 26px; height: 26px; border-radius: 50%; padding: 0; border: 2px solid var(--card); box-shadow: 0 0 0 1px var(--line); }
.swatch.on { box-shadow: 0 0 0 2px var(--text); }
.settings-grid { display: grid; grid-template-columns: 150px 1fr; gap: 14px 16px; align-items: center; }
.settings-grid > b { font-size: 13px; }
.pal-input { font-size: 16px; padding: 10px 12px !important; }
.pal-list { max-height: 50vh; overflow: auto; display: flex; flex-direction: column; }
.pal-item { display: flex; gap: 10px; align-items: center; padding: 8px 10px; border-radius: 8px; cursor: pointer; }
.pal-item.on { background: var(--accent-soft); }
.pal-item .sub { color: var(--muted); font-size: 12.5px; margin-left: auto; }
.shortcuts { display: grid; grid-template-columns: auto 1fr; gap: 8px 16px; }
#toast { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: var(--text); color: var(--bg); padding: 10px 16px; border-radius: 10px; opacity: 0; transition: opacity .2s; pointer-events: none; max-width: min(640px, calc(100vw - 32px)); z-index: 50; }
#toast.show { opacity: 1; pointer-events: auto; }
#toast.bad { background: var(--red); color: #fff; }
@media (max-width: 900px) {
  .app { grid-template-columns: 1fr; }
  aside { position: fixed; inset: 0 auto 0 0; width: 260px; z-index: 40; transform: translateX(-100%); transition: transform .2s; }
  aside.open { transform: none; box-shadow: 0 0 40px rgba(0,0,0,.3); }
  #menu-btn { display: inline-flex; }
  header, .summary, .toolbar, main { padding-left: 16px; padding-right: 16px; }
  .banner { margin-left: 16px; margin-right: 16px; }
  .grid { grid-template-columns: 1fr; }
  #filter { width: 100%; }
  .quick, .head-actions .label { display: none; }
  .settings-grid { grid-template-columns: 1fr; gap: 6px; }
  .top { flex-wrap: wrap; }
  .top .badges { order: 4; flex-basis: 100%; }
  .summary { grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
  .stat { padding: 8px 10px; }
  .stat b { font-size: 16px; }
  .envrow { grid-template-columns: 1fr 1fr auto auto; }
}
</style>
</head>
<body>
<svg width="0" height="0" style="position:absolute" aria-hidden="true">
  <symbol id="i-play" viewBox="0 0 24 24"><path d="M7 4.5v15l12-7.5z"/></symbol>
  <symbol id="i-stop" viewBox="0 0 24 24"><rect x="6" y="6" width="12" height="12" rx="2"/></symbol>
  <symbol id="i-star" viewBox="0 0 24 24"><path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2L12 17.3 6.4 20.2l1.1-6.2L3 9.6l6.2-.9z"/></symbol>
  <symbol id="i-more" viewBox="0 0 24 24"><circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/></symbol>
  <symbol id="i-gear" viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/></symbol>
  <symbol id="i-search" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></symbol>
  <symbol id="i-grid" viewBox="0 0 24 24"><rect x="4" y="4" width="7" height="7" rx="1"/><rect x="13" y="4" width="7" height="7" rx="1"/><rect x="4" y="13" width="7" height="7" rx="1"/><rect x="13" y="13" width="7" height="7" rx="1"/></symbol>
  <symbol id="i-list" viewBox="0 0 24 24"><path d="M8 6h13M8 12h13M8 18h13M3.5 6h.01M3.5 12h.01M3.5 18h.01"/></symbol>
  <symbol id="i-box" viewBox="0 0 24 24"><path d="M21 8 12 3 3 8v8l9 5 9-5z"/><path d="m3 8 9 5 9-5M12 13v8"/></symbol>
  <symbol id="i-bolt" viewBox="0 0 24 24"><path d="M13 3 4 14h7l-1 7 9-11h-7z"/></symbol>
  <symbol id="i-down" viewBox="0 0 24 24"><path d="M12 4v12m0 0-5-5m5 5 5-5M5 20h14"/></symbol>
  <symbol id="i-ext" viewBox="0 0 24 24"><path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/></symbol>
  <symbol id="i-menu" viewBox="0 0 24 24"><path d="M4 7h16M4 12h16M4 17h16"/></symbol>
  <symbol id="i-refresh" viewBox="0 0 24 24"><path d="M20 11a8 8 0 0 0-14.9-3.9M4 5v4h4M4 13a8 8 0 0 0 14.9 3.9M20 19v-4h-4"/></symbol>
  <symbol id="i-eye" viewBox="0 0 24 24"><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></symbol>
  <symbol id="i-x" viewBox="0 0 24 24"><path d="M6 6l12 12M18 6 6 18"/></symbol>
</svg>
<div class="app">
  <aside id="side">
    <div class="brand"><img src="favicon.svg" alt="">repodock</div>
    <nav id="nav"></nav>
    <div class="side-foot">
      <button type="button" class="nav" id="search-gh"><svg class="i"><use href="#i-search"/></svg>Search GitHub</button>
      <button type="button" class="nav" id="open-settings"><svg class="i"><use href="#i-gear"/></svg>Settings</button>
    </div>
  </aside>
  <div class="content">
    <header>
      <button type="button" class="ghost icon" id="menu-btn" aria-label="Menu"><svg class="i"><use href="#i-menu"/></svg></button>
      <form id="add-form">
        <input id="add-input" type="text" placeholder="Paste a GitHub link, owner/repo or a username" autocomplete="off" spellcheck="false" aria-label="GitHub link">
        <button class="primary" id="add-btn" type="submit">Add</button>
      </form>
      <div class="head-actions">
        <button type="button" class="ghost quick" id="quick-btn" title="Jump to a project">Jump to <kbd>Ctrl</kbd><kbd>K</kbd></button>
        <button type="button" id="update-all" hidden><svg class="i"><use href="#i-down"/></svg><span class="label">Update all</span></button>
        <button type="button" class="danger" id="stop-all" hidden><svg class="i"><use href="#i-stop"/></svg><span class="label">Stop all</span></button>
      </div>
    </header>
    <div class="scroll" id="scroll">
      <div id="banners"></div>
      <div class="summary" id="summary" hidden></div>
      <div class="toolbar" id="toolbar" hidden>
        <h1 id="view-title">All projects</h1>
        <input id="filter" type="search" placeholder="Filter  (press /)" aria-label="Filter projects">
        <select id="sort" aria-label="Sort"><option value="name">Name</option><option value="recent">Last run</option><option value="favorite">Favourites first</option><option value="size">Size</option></select>
        <div class="segmented" role="group" aria-label="Layout">
          <button type="button" data-view="grid" title="Cards"><svg class="i"><use href="#i-grid"/></svg></button>
          <button type="button" data-view="list" title="List"><svg class="i"><use href="#i-list"/></svg></button>
        </div>
      </div>
      <main id="main"></main>
    </div>
  </div>
</div>
<input type="file" id="import-file" accept=".json,application/json" hidden>
<dialog id="dlg"><form method="dialog" class="dlg" id="dlg-body"></form></dialog>
<div id="toast" role="status"></div>

<script>
"use strict";
const $ = (tag, attrs = {}, ...kids) => {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "value") el.value = v;
    else if (k === "checked") el.checked = !!v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat()) if (kid !== null && kid !== undefined && kid !== false) el.append(kid);
  return el;
};
const icon = (name) => { const s = document.createElementNS("http://www.w3.org/2000/svg", "svg"); s.setAttribute("class", "i");
  const u = document.createElementNS("http://www.w3.org/2000/svg", "use"); u.setAttribute("href", "#i-" + name); s.append(u); return s; };
const avatar = (owner, size = 64) => `https://github.com/${encodeURIComponent(owner)}.png?size=${size}`;

async function api(path, body) {
  const opts = body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json", "X-Repodock": "1" }, body: JSON.stringify(body) };
  const res = await fetch(path, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || res.statusText);
  return data;
}

let toastTimer;
function toast(msg, bad = false) {
  const t = document.getElementById("toast");
  t.textContent = msg; t.classList.toggle("bad", bad); t.classList.add("show");
  clearTimeout(toastTimer); toastTimer = setTimeout(() => t.classList.remove("show"), bad ? 7000 : 4000);
}
const fail = e => toast(e.message, true);

function ago(value) {
  if (!value) return "";
  const t = typeof value === "number" ? value * 1000 : new Date(value).getTime();
  const s = (Date.now() - t) / 1000;
  if (s < 60) return "just now";
  for (const [div, name] of [[31536000, "year"], [2592000, "month"], [86400, "day"], [3600, "hour"], [60, "minute"]])
    if (s >= div) { const n = Math.floor(s / div); return `${n} ${name}${n === 1 ? "" : "s"} ago`; }
}
function bytes(n) {
  if (n === undefined || n === null) return "";
  if (n < 1024 * 1024) return `${Math.max(1, Math.round(n / 1024))} KB`;
  if (n < 1024 ** 3) return `${(n / 1024 ** 2).toFixed(n < 10 * 1024 ** 2 ? 1 : 0)} MB`;
  return `${(n / 1024 ** 3).toFixed(1)} GB`;
}
function uptime(start) {
  const s = Math.max(0, Math.floor(Date.now() / 1000 - start));
  const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), sec = s % 60;
  return h ? `${h}h ${String(m).padStart(2, "0")}m` : `${m}:${String(sec).padStart(2, "0")}`;
}
function openUrl(url) { api("/api/open-url", { url }).catch(() => window.open(url, "_blank", "noopener")); }
// Offline, or GitHub unreachable: show the owner's initial instead of a broken picture.
document.addEventListener("error", e => {
  const img = e.target;
  if (img.tagName !== "IMG" || img.dataset.fallback) return;
  const m = /github\.com\/([^.?/]+)\.png/.exec(img.src); if (!m) return;
  img.dataset.fallback = "1";
  const letter = decodeURIComponent(m[1]).charAt(0).toUpperCase();
  const hue = [...m[1]].reduce((h, c) => (h * 31 + c.charCodeAt(0)) % 360, 7);
  img.src = "data:image/svg+xml," + encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40"><rect width="40" height="40" fill="hsl(${hue},45%,45%)"/><text x="20" y="27" font-family="Segoe UI,sans-serif" font-size="20" font-weight="600" fill="#fff" text-anchor="middle">${letter}</text></svg>`);
}, true);

document.addEventListener("click", e => {
  const a = e.target.closest("a[target=_blank]");
  if (a && /^https?:/.test(a.href)) { e.preventDefault(); openUrl(a.href); }
});

// Theme ------------------------------------------------------------------------
const ACCENTS = ["#0f766e", "#2563eb", "#7c3aed", "#db2777", "#ea580c", "#16a34a", "#475569"];
let settings = {};
function applyTheme(s) {
  const root = document.documentElement;
  const dark = s.theme === "dark" || (s.theme !== "light" && matchMedia("(prefers-color-scheme: dark)").matches);
  root.dataset.theme = dark ? "dark" : "light";
  const hex = /^#[0-9a-f]{6}$/i.test(s.accent || "") ? s.accent : ACCENTS[0];
  const [r, g, b] = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16));
  // Lighten the accent a little in dark mode so it stays readable.
  const mix = (c) => dark ? Math.round(c + (255 - c) * 0.3) : c;
  const accent = dark ? `rgb(${mix(r)}, ${mix(g)}, ${mix(b)})` : hex;
  const lum = (0.299 * mix(r) + 0.587 * mix(g) + 0.114 * mix(b)) / 255;
  root.style.setProperty("--accent", accent);
  root.style.setProperty("--on-accent", lum > 0.62 ? "#0b1215" : "#fff");
  document.getElementById("main").classList.toggle("list", s.view === "list");
  for (const b of document.querySelectorAll("[data-view]")) b.classList.toggle("on", b.dataset.view === (s.view || "grid"));
  document.getElementById("sort").value = s.sort || "name";
}
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => applyTheme(settings));
async function saveSettings(changes) {
  try { const res = await api("/api/settings", { changes }); settings = res.settings; applyTheme(settings); refresh(); }
  catch (e) { fail(e); }
}

// Dialogs ------------------------------------------------------------------
function dialog(build, cls = "") {
  return new Promise(resolve => {
    const dlg = document.getElementById("dlg"), body = document.getElementById("dlg-body");
    dlg.className = cls;
    body.replaceChildren();
    let done = false;
    const close = value => { if (done) return; done = true; dlg.close(); resolve(value); };
    build(body, close);
    dlg.onclose = () => { if (!done) { done = true; resolve(undefined); } };
    // Escape closes the dialog, even from a search box (which would otherwise just clear itself).
    dlg.onkeydown = e => { if (e.key === "Escape") { e.preventDefault(); close(undefined); } };
    dlg.showModal();
    const first = body.querySelector("[autofocus]") || body.querySelector("button.primary");
    if (first) first.focus();
  });
}
const cancelBtn = (close, label = "Cancel") => $("button", { type: "button", onclick: () => close(undefined) }, label);

function confirmRun(key, info) {
  return dialog((b, close) => {
    b.append($("h3", {}, info.action ? `${info.action}: ${key}?` : `Run ${key}?`));
    if (!info.owned) b.append($("div", { class: "callout" },
      $("b", {}, `This code comes from ${info.owner}. `),
      "It will run on this computer with your permissions. Only run projects you trust."));
    if (info.missing_tool) b.append($("div", { class: "callout" }, `${info.missing_tool} doesn't seem to be installed, so this will probably fail. Install it first, or pick another run command.`));
    if (info.deps) {
      b.append($("p", {}, "It needs dependencies first. This command installs them into the project folder:"), $("pre", {}, info.deps));
      b.append($("p", {}, "Then it runs:"), $("pre", {}, info.command));
      b.append($("div", { class: "buttons" }, cancelBtn(close),
        $("button", { type: "button", onclick: () => close({ install: false }) }, "Run without installing"),
        $("button", { class: "primary", type: "button", onclick: () => close({ install: true }) }, "Install and run")));
    } else {
      b.append($("p", {}, "This command will run in the project folder:"), $("pre", {}, info.command));
      b.append($("div", { class: "buttons" }, cancelBtn(close),
        $("button", { class: "primary", type: "button", onclick: () => close({}) }, info.action || "Run")));
    }
  });
}

function askInstall(key, command) {
  return dialog((b, close) => {
    b.append($("h3", {}, "Install dependencies?"),
      $("p", {}, `${key} needs its dependencies before it runs. This installs them:`), $("pre", {}, command),
      $("div", { class: "buttons" }, cancelBtn(close),
        $("button", { type: "button", onclick: () => close(false) }, "Run without installing"),
        $("button", { class: "primary", type: "button", onclick: () => close(true) }, "Install and run")));
  });
}

function repoRow(r, control) {
  const tags = [r.fork && "fork", r.archived && "archived", r.present && "already added"].filter(Boolean);
  return [control, $("img", { class: "avatar", src: avatar(r.owner, 48), alt: "", loading: "lazy", style: "width:28px;height:28px;border-radius:7px" }),
    $("div", { class: "info" },
      $("b", {}, r.full_name), tags.length ? $("span", { class: "badge", style: "margin-left:6px" }, tags.join(", ")) : null,
      r.description ? $("div", { class: "sub" }, r.description) : null,
      $("div", { class: "sub" }, [r.language, `${(r.size_kb / 1024).toFixed(1)} MB`, r.stars ? `★ ${r.stars}` : null, r.pushed_at ? `updated ${ago(r.pushed_at)}` : null].filter(Boolean).join(" · ")))];
}

function pickRepos(owner, repos) {
  return dialog((b, close) => {
    const boxes = [];
    const rows = repos.map(r => {
      const box = $("input", { type: "checkbox", value: r.full_name, disabled: r.present });
      box.checked = r.suggested; boxes.push(box);
      return $("label", {}, ...repoRow(r, box));
    });
    const count = $("span", { class: "hint" });
    const addBtn = $("button", { class: "primary", type: "button", onclick: () => close(boxes.filter(x => x.checked && !x.disabled).map(x => x.value)) });
    const update = () => {
      const picked = boxes.filter(x => x.checked && !x.disabled);
      const mb = repos.filter(r => picked.some(p => p.value === r.full_name)).reduce((s, r) => s + r.size_kb, 0) / 1024;
      addBtn.textContent = `Add ${picked.length} repo${picked.length === 1 ? "" : "s"}`;
      addBtn.disabled = !picked.length;
      count.textContent = `${picked.length} selected, about ${mb.toFixed(1)} MB`;
    };
    boxes.forEach(x => x.addEventListener("change", update));
    const setAll = on => { boxes.forEach(x => { if (!x.disabled) x.checked = on; }); update(); };
    b.append($("h3", { style: "display:flex;gap:10px;align-items:center" }, $("img", { class: "avatar", src: avatar(owner), alt: "" }), `Add repositories from ${owner}`),
      $("p", { class: "hint" }, "Forks and archived repositories are left out unless you tick them."),
      $("div", { class: "actions" }, $("button", { type: "button", class: "link", onclick: () => setAll(true) }, "Select all"), " · ",
        $("button", { type: "button", class: "link", onclick: () => setAll(false) }, "Select none"), $("span", { class: "spacer" }), count),
      $("div", { class: "pick" }, rows.length ? rows : $("p", { class: "hint", style: "padding:12px" }, "No public repositories.")),
      $("div", { class: "buttons" }, cancelBtn(close), addBtn));
    update();
  }, "wide");
}

function confirmDialog(title, text, action, danger = false) {
  return dialog((b, close) => {
    b.append($("h3", {}, title), typeof text === "string" ? $("p", {}, text) : text,
      $("div", { class: "buttons" }, cancelBtn(close),
        $("button", { class: "primary", type: "button", style: danger ? "background:var(--red);border-color:var(--red);color:#fff" : null, onclick: () => close(true) }, action)));
  });
}

// GitHub search ------------------------------------------------------------------
function searchGitHub(initial = "") {
  return dialog((b, close) => {
    const input = $("input", { type: "search", class: "pal-input", placeholder: "Search GitHub, e.g. markdown editor, or user:octocat", value: initial, autofocus: true });
    const results = $("div", { class: "pick" }, $("p", { class: "hint", style: "padding:12px" }, "Type a few words and press Enter. GitHub search syntax works too (language:go stars:>100)."));
    const go = async () => {
      const q = input.value.trim(); if (!q) return;
      results.replaceChildren($("p", { class: "hint", style: "padding:12px" }, "Searching..."));
      try {
        const res = await api("/api/search", { query: q });
        if (!res.repos.length) { results.replaceChildren($("p", { class: "hint", style: "padding:12px" }, "Nothing found.")); return; }
        results.replaceChildren(...res.repos.map(r => {
          const btn = $("button", { type: "button", class: r.present ? "" : "primary", disabled: r.present }, r.present ? "Added" : "Add");
          btn.addEventListener("click", async () => {
            btn.disabled = true; btn.textContent = "Adding...";
            try { await api("/api/add-many", { repos: [r.full_name] }); btn.textContent = "Added"; btn.className = ""; openLogs.add(r.full_name); refresh(); }
            catch (e) { btn.disabled = false; btn.textContent = "Add"; fail(e); }
          });
          return $("div", { class: "item" }, ...repoRow(r, null), btn);
        }));
      } catch (e) { results.replaceChildren($("p", { class: "hint bad", style: "padding:12px" }, e.message)); }
    };
    input.addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); go(); } });
    b.append($("h3", {}, "Search GitHub"), $("div", { class: "row" }, input, $("button", { type: "button", class: "primary", onclick: go }, "Search")), results,
      $("div", { class: "buttons" }, cancelBtn(close, "Done")));
    if (initial) go();
  }, "wide");
}

// Project settings (general + .env) ---------------------------------------------------
async function repoSettings(key, tab = "general") {
  const r = lastState.repos.find(x => x.key === key); if (!r) return;
  let env;
  try { env = await api("/api/env", { key }); } catch (e) { return fail(e); }
  const result = await dialog((b, close) => {
    const tabs = $("div", { class: "tabs" });
    const panes = {};
    const show = name => { for (const [n, p] of Object.entries(panes)) p.hidden = n !== name; for (const t of tabs.children) t.classList.toggle("on", t.dataset.tab === name); };
    for (const [name, label] of [["general", "General"], ["buttons", "Command buttons"], ["env", "Environment (.env)"]])
      tabs.append($("button", { type: "button", "data-tab": name, onclick: () => show(name) }, label));

    const port = $("input", { type: "number", min: 1, max: 65535, placeholder: "any free port", value: r.port || "" });
    const tags = $("input", { type: "text", placeholder: "e.g. work, games, tools", value: (r.tags || []).join(", ") });
    const restart = $("input", { type: "checkbox", checked: r.auto_restart });
    const fav = $("input", { type: "checkbox", checked: r.favorite });
    panes.general = $("div", { style: "display:flex;flex-direction:column;gap:12px" },
      $("label", { class: "field" }, "Port", $("span", {}, "Used for {port} in the run command, and passed as the PORT variable. Leave empty to pick a free port each time."), port),
      $("label", { class: "field" }, "Tags", $("span", {}, "Separate with commas. Tags show up in the sidebar."), tags),
      $("label", { class: "check" }, fav, $("div", {}, "Favourite", $("small", {}, "Shown in Favourites and first when sorting by favourites."))),
      $("label", { class: "check" }, restart, $("div", {}, "Restart automatically if it crashes", $("small", {}, "Up to 3 times in 5 minutes, then repodock gives up and tells you."))));

    const actionRows = $("div", { style: "display:flex;flex-direction:column;gap:6px" });
    const addAction = (a = { name: "", command: "" }) => {
      const row = $("div", { class: "row" },
        $("input", { type: "text", placeholder: "Name, e.g. Build", value: a.name, style: "flex:0 0 140px", maxlength: 24 }),
        $("input", { type: "text", class: "mono", placeholder: "Command, e.g. npm run build", value: a.command, spellcheck: "false" }),
        $("button", { type: "button", class: "ghost icon", title: "Remove", onclick: () => row.remove() }, icon("x")));
      actionRows.append(row);
    };
    (r.actions || []).forEach(addAction);
    panes.buttons = $("div", { style: "display:flex;flex-direction:column;gap:10px" },
      $("p", { class: "hint" }, "Extra buttons on the card, like Build or Test. They run in the project folder, and each one is confirmed the first time."),
      actionRows, $("div", {}, $("button", { type: "button", onclick: () => addAction() }, "Add a button")));

    const envRows = $("div", { style: "display:flex;flex-direction:column;gap:6px" });
    const addEnv = (k = "", v = "") => {
      const value = $("input", { type: "password", class: "mono", value: v, placeholder: "value", autocomplete: "off", spellcheck: "false" });
      const row = $("div", { class: "envrow" },
        $("input", { type: "text", class: "mono", value: k, placeholder: "NAME", spellcheck: "false" }), value,
        $("button", { type: "button", class: "ghost icon", title: "Show or hide", onclick: () => { value.type = value.type === "password" ? "text" : "password"; } }, icon("eye")),
        $("button", { type: "button", class: "ghost icon", title: "Remove", onclick: () => row.remove() }, icon("x")));
      envRows.append(row);
    };
    env.vars.forEach(([k, v]) => addEnv(k, v));
    const fromExample = env.example.length && !env.vars.length
      ? $("button", { type: "button", onclick: () => { env.example.forEach(([k, v]) => addEnv(k, v)); fromExample.remove(); } }, `Start from ${env.example_name}`) : null;
    panes.env = $("div", { style: "display:flex;flex-direction:column;gap:10px" },
      $("p", { class: "hint" }, env.exists ? "Variables from the project's .env file. They're also passed to the app when it runs." : "This project has no .env file yet. Variables you add here are saved to one and passed to the app when it runs."),
      envRows, $("div", { class: "actions" }, $("button", { type: "button", onclick: () => addEnv() }, "Add a variable"), fromExample));

    const save = () => close({
      fields: { port: port.value ? Number(port.value) : null, tags: tags.value.split(",").map(t => t.trim()).filter(Boolean), auto_restart: restart.checked, favorite: fav.checked,
        actions: [...actionRows.children].map(row => { const [n, c] = row.querySelectorAll("input"); return { name: n.value.trim(), command: c.value.trim() }; }).filter(a => a.name || a.command) },
      vars: [...envRows.children].map(row => { const [k, v] = row.querySelectorAll("input"); return [k.value.trim(), v.value]; }).filter(([k]) => k),
    });
    b.append($("h3", {}, `${key} settings`), tabs, panes.general, panes.buttons, panes.env,
      $("div", { class: "buttons" }, cancelBtn(close), $("button", { type: "button", class: "primary", onclick: save }, "Save")));
    show(tab);
  }, "wide");
  if (!result) return;
  try {
    await api("/api/configure", { key, fields: result.fields });
    const before = JSON.stringify(env.vars), after = JSON.stringify(result.vars);
    if (before !== after) await api("/api/set-env", { key, vars: result.vars });
    toast("Saved"); refresh();
  } catch (e) { fail(e); }
}

// Releases -----------------------------------------------------------------------------
async function showReleases(key) {
  const chosen = await dialog((b, close) => {
    const list = $("div", { class: "pick" }, $("p", { class: "hint", style: "padding:12px" }, "Loading releases..."));
    b.append($("h3", {}, `Releases of ${key}`),
      $("p", { class: "hint" }, "Download a ready-made program from the project's GitHub releases. It's saved next to your projects, and runs only when you press Run."),
      list, $("div", { class: "buttons" }, $("button", { type: "button", class: "link", onclick: () => api("/api/open", { key, which: "releases" }).catch(fail) }, "Open downloads folder"),
        $("span", { class: "spacer" }), cancelBtn(close, "Close")));
    api("/api/releases", { key }).then(res => {
      if (!res.releases.length) { list.replaceChildren($("p", { class: "hint", style: "padding:12px" }, "This project has no releases on GitHub.")); return; }
      list.replaceChildren(...res.releases.map((rel, i) => {
        const fit = rel.assets.filter(a => a.fit > 0), other = rel.assets.filter(a => !a.fit);
        const assetRow = (a, best) => $("div", { class: "row", style: "justify-content:space-between" },
          $("span", { class: "mono", style: "overflow-wrap:anywhere" }, a.name, $("span", { class: "sub" }, `  ${bytes(a.size)}`)),
          $("button", { type: "button", class: best ? "primary" : "", onclick: () => close({ tag: rel.tag, asset: a.name }) }, icon("down"), "Download"));
        const more = other.length ? $("details", {}, $("summary", { class: "sub" }, `${other.length} other file${other.length === 1 ? "" : "s"} (other systems or source code)`),
          ...other.map(a => assetRow(a, false))) : null;
        return $("div", { class: "item", style: "flex-direction:column;gap:6px" },
          $("div", { class: "row" }, $("b", {}, rel.name || rel.tag), rel.prerelease ? $("span", { class: "badge busy" }, "pre-release") : null,
            i === 0 && !rel.prerelease ? $("span", { class: "badge new" }, "latest") : null, $("span", { class: "sub", style: "margin-left:auto" }, ago(rel.published_at))),
          fit.length ? fit.map((a, j) => assetRow(a, i === 0 && j === 0)) : $("span", { class: "sub" }, "No download for this system."), more);
      }));
    }).catch(e => list.replaceChildren($("p", { class: "hint bad", style: "padding:12px" }, e.message)));
  }, "wide");
  if (!chosen) return;
  try { await api("/api/download-release", { key, ...chosen }); openLogs.add(key); refresh(); toast(`Downloading ${chosen.asset}`); } catch (e) { fail(e); }
}

// Cleaning -------------------------------------------------------------------------------
async function cleanRepo(key) {
  let items;
  try { items = (await api("/api/cleanable", { key })).items; } catch (e) { return fail(e); }
  if (!items.length) return toast("Nothing to clean: no dependencies or build output in this project.");
  const names = await dialog((b, close) => {
    const boxes = items.map(it => $("input", { type: "checkbox", value: it.name, checked: true }));
    b.append($("h3", {}, `Free up space in ${key}`),
      $("p", {}, "These folders hold installed dependencies, caches or build output. They're recreated the next time you install or build."),
      $("div", { class: "pick" }, items.map((it, i) => $("label", {}, boxes[i], $("div", { class: "info" }, $("b", { class: "mono" }, it.name)), $("span", { class: "sub" }, bytes(it.size))))),
      $("div", { class: "buttons" }, cancelBtn(close), $("button", { type: "button", class: "primary", onclick: () => close(boxes.filter(x => x.checked).map(x => x.value)) }, "Delete selected")));
  });
  if (!names || !names.length) return;
  try { const res = await api("/api/clean", { key, names }); toast(`Freed ${bytes(res.freed)}`); refresh(); } catch (e) { fail(e); }
}

// Toolchains ------------------------------------------------------------------------------
async function installTool(info) {
  if (!info.command) return openUrl(info.page);
  const ok = await confirmDialog(`Install ${info.tool}?`, $("div", { style: "display:flex;flex-direction:column;gap:10px" },
    $("p", {}, "repodock will run this Windows Package Manager command. Windows may ask for permission."), $("pre", {}, info.command),
    $("p", { class: "hint" }, "Or ", $("button", { type: "button", class: "link", onclick: () => openUrl(info.page) }, "download it yourself"), ".")), "Install");
  if (!ok) return;
  try { await api("/api/install-tool", { tool: info.tool }); toast(`Installing ${info.tool}...`); refresh(); } catch (e) { fail(e); }
}

// App settings -----------------------------------------------------------------------------
function appSettings() {
  const st = lastState;
  return dialog((b, close) => {
    const seg = (name, options) => $("div", { class: "segmented" }, options.map(([v, label]) =>
      $("button", { type: "button", class: settings[name] === v ? "on" : "", onclick: e => { saveSettings({ [name]: v }); for (const x of e.target.parentNode.children) x.classList.toggle("on", x === e.target); } }, label)));
    const custom = $("input", { type: "color", value: settings.accent || ACCENTS[0], title: "Custom colour", style: "width:34px;height:28px;padding:0;border:0;background:none" });
    custom.addEventListener("change", () => saveSettings({ accent: custom.value }));
    const toggle = (name, label, hint) => $("label", { class: "check" }, $("input", { type: "checkbox", checked: settings[name], onchange: e => {
        if (name === "notify" && e.target.checked) askNotifications();
        saveSettings({ [name]: e.target.checked }); } }),
      $("div", {}, label, hint ? $("small", {}, hint) : null));
    const auto = st.app.autostart_supported ? $("label", { class: "check" }, $("input", { type: "checkbox", checked: st.app.autostart,
      onchange: async e => { try { await api("/api/settings", { changes: { start_with_windows: e.target.checked } }); refresh(); } catch (err) { e.target.checked = !e.target.checked; fail(err); } } }),
      $("div", {}, "Start with Windows", $("small", {}, "Opens in the tray when you sign in."))) : null;
    b.append($("h3", {}, "Settings"),
      $("div", { class: "settings-grid" },
        $("b", {}, "Theme"), seg("theme", [["system", "System"], ["light", "Light"], ["dark", "Dark"]]),
        $("b", {}, "Accent colour"), $("div", { class: "swatches" }, ACCENTS.map(c => $("button", { type: "button", class: "swatch" + (c === settings.accent ? " on" : ""), style: `background:${c}`, title: c,
          onclick: e => { saveSettings({ accent: c }); for (const x of e.target.parentNode.querySelectorAll(".swatch")) x.classList.toggle("on", x === e.target); } })), custom),
        $("b", {}, "Layout"), seg("view", [["grid", "Cards"], ["list", "List"]]),
        $("b", {}, "Group"), seg("group", [["owner", "By owner"], ["none", "No groups"]]),
        $("b", {}, "Behaviour"), $("div", { style: "display:flex;flex-direction:column;gap:8px" },
          toggle("notify", "Tell me when an app crashes"),
          toggle("check_updates", "Check for updates in the background", "Runs git fetch every 30 minutes."),
          st.app.tray ? toggle("close_to_tray", "Closing the window keeps repodock in the tray") : null, auto),
        $("b", {}, "Library"), $("div", { class: "actions" },
          $("button", { type: "button", onclick: exportLibrary }, "Export..."),
          $("button", { type: "button", onclick: () => document.getElementById("import-file").click() }, "Import..."),
          $("button", { type: "button", onclick: () => api("/api/check-updates", {}).then(() => toast("Checking for updates...")).catch(fail) }, "Check for updates now")),
        $("b", {}, "About"), $("div", { class: "hint" }, `repodock ${st.version} · projects are kept in `, $("code", {}, st.root))),
      $("div", { class: "buttons" },
        st.app.can_quit ? $("button", { type: "button", class: "danger", onclick: quitApp }, "Quit repodock") : null,
        $("span", { class: "spacer" }), $("button", { type: "button", class: "primary", onclick: () => close() }, "Done")));
  }, "wide");
}

async function quitApp() {
  const running = lastState.repos.filter(r => r.job && r.job.running && r.job.kind === "run").length;
  if (running && !await confirmDialog("Quit repodock?", `This stops ${running} running app${running === 1 ? "" : "s"}.`, "Quit", true)) return;
  try { await api("/api/quit", {}); } catch (e) { fail(e); }
}

async function exportLibrary() {
  try {
    const res = await fetch("/api/export");
    const blob = await res.blob();
    const a = $("a", { href: URL.createObjectURL(blob), download: `repodock-library-${new Date().toISOString().slice(0, 10)}.json` });
    document.body.append(a); a.click(); a.remove();
    toast("Library exported. Import it on another computer to download the same projects with your settings (.env files aren't included).");
  } catch (e) { fail(e); }
}
document.getElementById("import-file").addEventListener("change", async e => {
  const file = e.target.files[0]; e.target.value = "";
  if (!file) return;
  try {
    const library = JSON.parse(await file.text());
    const n = (library.repos || []).length;
    if (!await confirmDialog("Import library?", `${n} project${n === 1 ? "" : "s"}. Projects you don't have yet are downloaded, and settings are applied to the ones you have.`, "Import")) return;
    const res = await api("/api/import", { library });
    const errors = Object.entries(res.errors);
    toast(`Added ${res.added.length}, updated ${res.updated.length}` + (errors.length ? `. Problems: ${errors.map(([k, v]) => `${k}: ${v}`).join("; ")}` : ""), !!errors.length);
    const s = await api("/api/state"); settings = s.settings; applyTheme(settings); render(s);
  } catch (err) { fail(err); }
});

// Command palette (Ctrl+K) ------------------------------------------------------------------
function palette() {
  return dialog((b, close) => {
    const input = $("input", { type: "search", class: "pal-input", placeholder: "Jump to a project or command...", autofocus: true });
    const list = $("div", { class: "pal-list" });
    let items = [], sel = 0;
    const commands = [
      ["Search GitHub", () => searchGitHub(input.value)], ["Settings", appSettings], ["Stop all running apps", () => api("/api/stop-all", {}).then(refresh).catch(fail)],
      ["Update all", () => api("/api/update-all", {}).then(refresh).catch(fail)], ["Check for updates", () => api("/api/check-updates", {}).then(() => toast("Checking...")).catch(fail)],
      ["Switch to list view", () => saveSettings({ view: "list" })], ["Switch to card view", () => saveSettings({ view: "grid" })], ["Keyboard shortcuts", shortcuts],
    ];
    const draw = () => {
      const words = input.value.toLowerCase().split(/\s+/).filter(Boolean);
      const match = t => words.every(w => t.toLowerCase().includes(w));
      items = [
        ...lastState.repos.filter(r => match(`${r.key} ${(r.tags || []).join(" ")} ${r.description || ""}`)).map(r => ({ repo: r })),
        ...commands.filter(([t]) => match(t)).map(([t, fn]) => ({ label: t, fn })),
      ].slice(0, 40);
      sel = Math.min(sel, Math.max(items.length - 1, 0));
      list.replaceChildren(...items.map((it, i) => {
        const running = it.repo && it.repo.job && it.repo.job.running && it.repo.job.kind === "run";
        const row = it.repo
          ? $("div", { class: "pal-item" + (i === sel ? " on" : "") }, $("img", { class: "avatar", src: avatar(it.repo.key.split("/")[0], 40), alt: "", style: "width:22px;height:22px;border-radius:6px" }),
              $("span", {}, it.repo.key), running ? $("span", { class: "dot" }) : null, $("span", { class: "sub" }, running ? "Enter: go · Shift+Enter: stop" : "Enter: go · Shift+Enter: run"))
          : $("div", { class: "pal-item" + (i === sel ? " on" : "") }, icon("bolt"), $("span", {}, it.label));
        row.addEventListener("click", () => pick(it, false));
        row.addEventListener("mousemove", () => { if (sel !== i) { sel = i; draw(); } });
        return row;
      }));
      if (!items.length) list.append($("p", { class: "hint", style: "padding:8px 10px" }, "No match. Press Enter to search GitHub for it."));
    };
    const pick = (it, alt) => {
      close();
      if (!it) { if (input.value.trim()) searchGitHub(input.value.trim()); return; }
      if (it.fn) return it.fn();
      const r = it.repo, running = r.job && r.job.running && r.job.kind === "run";
      if (alt) return running ? act("/api/stop", r.key) : run(r.key);
      jumpTo(r.key);
    };
    input.addEventListener("input", () => { sel = 0; draw(); });
    input.addEventListener("keydown", e => {
      if (e.key === "ArrowDown") { sel = Math.min(sel + 1, items.length - 1); draw(); e.preventDefault(); }
      else if (e.key === "ArrowUp") { sel = Math.max(sel - 1, 0); draw(); e.preventDefault(); }
      else if (e.key === "Enter") { e.preventDefault(); pick(items[sel], e.shiftKey); }
    });
    b.append(input, list);
    draw();
  }, "palette");
}

function jumpTo(key) {
  if (!visibleKeys.has(key)) { view = "all"; textFilter = ""; document.getElementById("filter").value = ""; render(lastState); }
  const p = cards.get(key); if (!p) return;
  p.el.scrollIntoView({ behavior: "smooth", block: "center" });
  p.el.classList.remove("flash"); void p.el.offsetWidth; p.el.classList.add("flash");
}

function shortcuts() {
  return dialog((b, close) => b.append($("h3", {}, "Keyboard shortcuts"), $("div", { class: "shortcuts" },
    $("span", {}, $("kbd", {}, "Ctrl"), " ", $("kbd", {}, "K")), $("span", {}, "Jump to a project or command (Shift+Enter runs it)"),
    $("kbd", {}, "/"), $("span", {}, "Filter projects"),
    $("kbd", {}, "A"), $("span", {}, "Add a project (focus the link box)"),
    $("kbd", {}, "S"), $("span", {}, "Search GitHub"),
    $("kbd", {}, "L"), $("span", {}, "Switch between cards and list"),
    $("kbd", {}, "?"), $("span", {}, "This list"),
    $("kbd", {}, "Esc"), $("span", {}, "Close a dialog")),
    $("div", { class: "buttons" }, $("button", { type: "button", class: "primary", onclick: () => close() }, "Done"))));
}

document.addEventListener("keydown", e => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); if (!document.getElementById("dlg").open) palette(); return; }
  const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName) || document.getElementById("dlg").open;
  if (typing || e.ctrlKey || e.metaKey || e.altKey) return;
  if (e.key === "/") { e.preventDefault(); document.getElementById("filter").focus(); }
  else if (e.key === "a") { e.preventDefault(); document.getElementById("add-input").focus(); }
  else if (e.key === "s") { e.preventDefault(); searchGitHub(); }
  else if (e.key === "l") { saveSettings({ view: settings.view === "list" ? "grid" : "list" }); }
  else if (e.key === "?") { shortcuts(); }
});

// Actions --------------------------------------------------------------------
function askNotifications() {
  // In a browser tab, crash notices can also pop up as system notifications (asked once, on a click).
  if (lastState && lastState.app.mode !== "window" && settings.notify && "Notification" in window && Notification.permission === "default")
    Notification.requestPermission().catch(() => {});
}

async function run(key, action) {
  askNotifications();
  try {
    let res = await api("/api/run", { key, action });
    if (res.confirm) {
      const choice = await confirmRun(key, res.confirm);
      if (!choice) return;
      res = await api("/api/run", { key, action, confirmed: true, install: res.confirm.deps ? choice.install : undefined });
    }
    if (res.install) {
      const install = await askInstall(key, res.install.command);
      if (install === undefined) return;
      res = await api("/api/run", { key, action, confirmed: true, install });
    }
    openLogs.add(key);
    refresh();
  } catch (e) { fail(e); }
}

async function act(path, key, extra = {}) {
  try { await api(path, { key, ...extra }); refresh(); } catch (e) { fail(e); }
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
        if (failed.length) toast(failed.map(([k, v]) => `${k}: ${v}`).join("; "), true);
        else toast(`Downloading ${out.added.length} repositories`);
      }
    } else {
      openLogs.add(res.key);
      setTimeout(() => jumpTo(res.key), 300);
    }
    input.value = "";
    refresh();
  } catch (err) {
    // Words that aren't a link or a name: offer a GitHub search instead.
    if (/\s/.test(text) || /not a GitHub link/.test(err.message)) searchGitHub(text); else fail(err);
  }
  finally { btn.disabled = false; btn.textContent = "Add"; }
});
document.getElementById("search-gh").addEventListener("click", () => searchGitHub());
document.getElementById("open-settings").addEventListener("click", appSettings);
document.getElementById("quick-btn").addEventListener("click", palette);
document.getElementById("stop-all").addEventListener("click", async () => {
  if (await confirmDialog("Stop everything?", "Every running app and install is stopped.", "Stop all", true)) api("/api/stop-all", {}).then(refresh).catch(fail);
});
document.getElementById("update-all").addEventListener("click", async () => {
  try { const res = await api("/api/update-all", {}); toast(`Updating ${res.updating.length} project${res.updating.length === 1 ? "" : "s"}` + (res.skipped.length ? `; stop ${res.skipped.join(", ")} to update ${res.skipped.length === 1 ? "it" : "them"}` : "")); refresh(); } catch (e) { fail(e); }
});
document.getElementById("menu-btn").addEventListener("click", () => document.getElementById("side").classList.toggle("open"));
for (const b of document.querySelectorAll("[data-view]")) b.addEventListener("click", () => saveSettings({ view: b.dataset.view }));
document.getElementById("sort").addEventListener("change", e => saveSettings({ sort: e.target.value }));
document.addEventListener("click", e => {
  if (!e.target.closest(".menu-wrap")) for (const m of document.querySelectorAll(".menu")) m.hidden = true;
  if (!e.target.closest("aside") && !e.target.closest("#menu-btn")) document.getElementById("side").classList.remove("open");
});

// Rendering ------------------------------------------------------------------
const cards = new Map();          // key -> parts
const openLogs = new Set();       // keys whose log is visible
const logs = new Map();           // key -> {seq, lines, past}
let view = "all", textFilter = "", lastState = null, lastEvent = null, visibleKeys = new Set();

function statusBadge(r) {
  const j = r.job;
  if (j && j.running) {
    const text = { run: j.label ? j.label + "..." : "Running", install: "Installing", clone: "Downloading", update: "Updating", release: "Downloading release" }[j.kind] || "Busy";
    return $("span", { class: "badge " + (j.kind === "run" ? "run" : "busy") }, j.stopping ? "Stopping" : text);
  }
  if (r.status === "failed") return $("span", { class: "badge bad" }, "Download failed");
  if (j && j.kind === "run" && j.exit_code !== null && !j.stopping && j.exit_code !== 0) return $("span", { class: "badge bad" }, `Crashed (exit ${j.exit_code})`);
  if (j && j.kind === "install" && j.exit_code) return $("span", { class: "badge bad" }, "Install failed");
  if (j && j.kind === "release" && j.error) return $("span", { class: "badge bad" }, "Release download failed");
  return null;
}

function menuButton(items) {
  const menu = $("div", { class: "menu", hidden: true });
  const btn = $("button", { type: "button", class: "ghost icon", title: "More", "aria-label": "More actions" }, icon("more"));
  btn.addEventListener("click", e => {
    e.stopPropagation();
    const open = menu.hidden;
    for (const m of document.querySelectorAll(".menu")) m.hidden = true;
    if (!open) return;
    menu.replaceChildren(...items().filter(Boolean).map(it => it === "-" ? $("hr") : $("button", { type: "button", class: it.danger ? "danger" : "", disabled: it.disabled,
      onclick: () => { menu.hidden = true; it.fn(); } }, it.label)));
    menu.hidden = false;
  });
  return $("div", { class: "menu-wrap" }, btn, menu);
}

function buildCard(key) {
  const p = { key };
  const [owner] = key.split("/");
  p.el = $("div", { class: "card", "data-key": key });
  p.badges = $("div", { class: "badges" });
  p.star = $("button", { type: "button", class: "ghost icon star", title: "Favourite" }, icon("star"));
  p.name = $("a", { class: "name", target: "_blank", rel: "noopener" });
  p.meta = $("div", { class: "meta" });
  p.desc = $("p", { class: "desc" });
  p.live = $("div", { class: "live", hidden: true });
  p.select = $("select", { "aria-label": "Run command" });
  p.custom = $("input", { type: "text", class: "mono", placeholder: "Type a command", spellcheck: "false", "aria-label": "Custom run command" });
  p.save = $("button", { type: "button" }, "Save");
  p.cmdRow = $("div", { class: "cmd cmdrow" }, p.select, p.custom, p.save);
  p.hints = $("div", { class: "hints" });
  p.run = $("button", { class: "primary", type: "button" });
  p.extra = $("span", { style: "display:contents" });
  p.logBtn = $("button", { type: "button" }, "Log");
  p.update = $("button", { type: "button", title: "Download the latest version" }, icon("down"), "Update");
  p.retry = $("button", { type: "button" }, "Retry");
  p.more = menuButton(() => {
    const r = lastState.repos.find(x => x.key === key); if (!r) return [];
    const j = r.job, busy = !!(j && j.running), ready = r.status === "ready" && r.exists;
    return [
      ready && { label: "Project settings...", fn: () => repoSettings(key) },
      ready && { label: "Environment (.env)...", fn: () => repoSettings(key, "env") },
      ready && { label: "Releases (download a program)...", fn: () => showReleases(key), disabled: busy },
      "-",
      r.exists && { label: "Open folder", fn: () => act("/api/open", key) },
      ready && r.git && { label: "Check for updates", fn: () => act("/api/check-updates", null, { keys: [key] }) },
      ready && r.deps && { label: r.needs_deps ? "Install dependencies" : "Reinstall dependencies", fn: () => { openLogs.add(key); act("/api/install", key); }, disabled: busy },
      ready && { label: "Detect run commands again", fn: () => act("/api/redetect", key) },
      ready && { label: "Free up space...", fn: () => cleanRepo(key), disabled: busy },
      { label: "Saved logs", fn: () => { openLogs.add(key); refresh(); setTimeout(() => cards.get(key)?.past.focus(), 50); } },
      "-",
      { label: "Delete...", danger: true, fn: async () => { if (await confirmDialog(`Delete ${key}?`, "This stops it if it's running and deletes its folder, including installed dependencies, downloaded releases and any changes you made there.", "Delete", true)) { cards.get(key)?.el.remove(); cards.delete(key); act("/api/delete", key, { files: true }); } }, disabled: busy && j.kind !== "run" && j.kind !== "install" },
    ];
  });
  p.logSearch = $("input", { type: "search", placeholder: "Search the log", "aria-label": "Search the log" });
  p.past = $("select", { "aria-label": "Past runs" });
  p.log = $("pre", { class: "log" });
  p.logBox = $("div", { class: "logbox", hidden: true }, $("div", { class: "logbar" }, p.logSearch, p.past), p.log);
  p.el.append(
    $("div", { class: "top" }, $("img", { class: "avatar", src: avatar(owner), alt: "", loading: "lazy" }),
      $("div", { class: "title" }, p.name, p.meta), p.badges, p.star),
    p.desc, p.live, p.cmdRow, p.hints,
    $("div", { class: "actions" }, p.run, p.extra, p.logBtn, $("span", { class: "spacer" }), p.update, p.retry, p.more),
    p.logBox);

  p.star.addEventListener("click", () => { const r = lastState.repos.find(x => x.key === key); act("/api/configure", key, { fields: { favorite: !(r && r.favorite) } }); });
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
  p.logBtn.addEventListener("click", () => { if (openLogs.has(key)) openLogs.delete(key); else openLogs.add(key); refresh(); });
  p.update.addEventListener("click", () => { openLogs.add(key); act("/api/update", key); });
  p.retry.addEventListener("click", async () => {
    try { await api("/api/delete", { key, files: true }); await api("/api/add", { input: key }); openLogs.add(key); refresh(); } catch (e) { fail(e); }
  });
  p.logSearch.addEventListener("input", () => drawLog(key));
  p.past.addEventListener("focus", () => loadPast(key));
  p.past.addEventListener("change", async () => {
    const entry = logs.get(key);
    if (!p.past.value) { entry.past = null; drawLog(key); return; }
    try { entry.past = (await api("/api/log-file", { key, name: p.past.value })).text.split("\n"); drawLog(key); } catch (e) { fail(e); }
  });
  return p;
}

async function loadPast(key) {
  const p = cards.get(key); if (!p) return;
  try {
    const res = await api("/api/logs", { key });
    const current = p.past.value;
    p.past.replaceChildren($("option", { value: "" }, "Live output"), ...res.logs.map(l => $("option", { value: l.name }, `${new Date(l.time * 1000).toLocaleString()} (${l.name.replace(/^\d+-\d+-|\.log$/g, "")})`)));
    p.past.value = current;
  } catch (e) { /* ignore */ }
}

function drawLog(key) {
  const p = cards.get(key), entry = logs.get(key); if (!p || !entry) return;
  const lines = entry.past || entry.lines;
  const q = p.logSearch.value.trim().toLowerCase();
  const stick = p.log.scrollHeight - p.log.scrollTop - p.log.clientHeight < 30;
  if (!q) p.log.textContent = lines.join("\n");
  else {
    const hits = lines.filter(l => l.toLowerCase().includes(q));
    p.log.replaceChildren(...hits.flatMap(l => {
      const parts = [], lower = l.toLowerCase(); let i = 0, at;
      while ((at = lower.indexOf(q, i)) !== -1) { parts.push(l.slice(i, at), $("mark", {}, l.slice(at, at + q.length))); i = at + q.length; }
      parts.push(l.slice(i), "\n"); return parts;
    }));
    if (!hits.length) p.log.textContent = `No lines contain "${p.logSearch.value.trim()}".`;
  }
  if (stick || !q) p.log.scrollTop = p.log.scrollHeight;
}

async function pullLog(key) {
  const entry = logs.get(key);
  try {
    const res = await api(`/api/log?key=${encodeURIComponent(key)}&after=${entry.seq}`);
    if (!res.lines.length) return;
    entry.lines.push(...res.lines.map(([, line]) => line));
    if (entry.lines.length > 6000) entry.lines.splice(0, entry.lines.length - 5000);
    entry.seq = res.lines[res.lines.length - 1][0];
    if (!entry.past) drawLog(key);
  } catch (e) { /* next poll retries */ }
}

function updateCard(p, r) {
  const j = r.job, running = !!(j && j.running), isRun = running && j.kind === "run", ready = r.status === "ready" && r.exists;
  p.el.classList.toggle("running", isRun);
  const badges = [statusBadge(r)];
  if (r.behind > 0) badges.push($("span", { class: "badge new", title: "New commits on GitHub" }, `${r.behind} new commit${r.behind === 1 ? "" : "s"}`));
  else if (r.behind === -1) badges.push($("span", { class: "badge new" }, "Update available"));
  for (const t of r.tags || []) badges.push($("span", { class: "tag" }, t));
  p.badges.replaceChildren(...badges.filter(Boolean));
  p.star.classList.toggle("on", !!r.favorite);
  p.star.title = r.favorite ? "Remove from favourites" : "Add to favourites";
  const [owner, name] = r.key.split("/");
  p.name.replaceChildren(settings.group === "none" ? $("span", { class: "owner" }, `${owner} / `) : "", r.name || name);
  p.name.href = r.html_url || `https://github.com/${r.key}`;
  p.meta.replaceChildren(...[r.language, r.stars ? `★ ${r.stars}` : null, r.size ? bytes(r.size) : null, r.last_run ? `ran ${ago(r.last_run)}` : (r.pushed_at ? `updated ${ago(r.pushed_at)}` : null),
    r.git === false && r.exists ? "zip download" : null, r.auto_restart ? "auto-restart" : null].filter(Boolean).map(t => $("span", {}, t)));
  p.desc.textContent = r.description || ""; p.desc.hidden = !r.description;

  // Live stats while something runs.
  p.live.hidden = !(running && j.pid);
  if (running && j.pid) {
    const s = r.stats || {};
    const open = isRun && j.url ? $("button", { type: "button", class: "primary", style: "padding:3px 10px;font-size:12.5px", onclick: () => openUrl(j.url) }, icon("ext"), "Open in browser") : null;
    p.live.replaceChildren($("span", {}, "CPU ", $("b", {}, s.cpu !== undefined ? `${s.cpu}%` : "...")), $("span", {}, "RAM ", $("b", {}, s.rss ? bytes(s.rss) : "...")),
      $("span", {}, "Up ", $("b", {}, uptime(j.started))), s.procs > 1 ? $("span", {}, `${s.procs} processes`) : null, $("span", { class: "spacer" }), open);
  }

  p.cmdRow.hidden = !ready;
  if (ready && document.activeElement !== p.select && document.activeElement !== p.custom) {
    const opts = r.candidates.map(c => $("option", { value: c.command, title: c.preview }, `${c.label}  ·  ${c.preview}`));
    if (r.custom) opts.push($("option", { value: r.command, title: r.command_preview }, `Custom · ${r.command_preview}`));
    opts.push($("option", { value: "__custom" }, "Custom command..."));
    const sig = JSON.stringify([r.candidates.map(c => c.preview), r.command, r.custom]);
    if (p.selectSig !== sig) { p.select.replaceChildren(...opts); p.selectSig = sig; }
    p.select.value = r.command || "__custom";
    const editing = !r.command;
    p.custom.hidden = !editing; p.save.hidden = !editing;
    if (!editing) p.custom.value = r.command || "";
  }
  const hints = [];
  if (ready && !r.candidates.length && !r.command) hints.push($("div", { class: "hint warn" }, "repodock couldn't tell how to run this project. Check its README and type the command, or look for a ready-made program under ⋯ > Releases."));
  if (ready && r.missing_tool) {
    const tool = tools.get(r.missing_tool);
    const info = r.tool_install;
    hints.push($("div", { class: "hint bad" }, `Needs ${r.missing_tool}, which isn't installed.`,
      tool && tool.running ? $("span", { class: "badge busy" }, "Installing...") :
      info ? $("button", { type: "button", style: "font-size:12.5px;padding:2px 9px", onclick: () => installTool(info) }, info.command ? `Install ${info.tool}` : `Download ${info.tool}`) : null));
  }
  if (ready && r.deps) hints.push($("div", { class: "hint" + (r.needs_deps ? " warn" : "") }, "Dependencies: ", $("code", {}, r.deps), r.needs_deps ? " (not installed yet)" : " (installed)"));
  for (const n of (ready && r.notes) || []) hints.push($("div", { class: "hint" }, n));
  if (r.error) hints.push($("div", { class: "hint bad" }, r.error));
  if (r.check_error && !r.error) hints.push($("div", { class: "hint" }, `Couldn't check for updates: ${r.check_error}`));
  p.hints.replaceChildren(...hints);
  p.hints.hidden = !hints.length;

  p.run.hidden = !ready;
  p.run.replaceChildren(icon(running && (j.kind === "run" || j.kind === "install") ? "stop" : "play"), running && (j.kind === "run" || j.kind === "install") ? "Stop" : "Run");
  p.run.disabled = running && !(j.kind === "run" || j.kind === "install");
  const actionSig = JSON.stringify([r.actions, running, ready]);
  if (p.actionSig !== actionSig) {
    p.actionSig = actionSig;
    p.extra.replaceChildren(...(ready ? r.actions : []).map(a => $("button", { type: "button", disabled: running, title: a.command, onclick: () => run(r.key, a.name) }, a.name)));
  }
  p.update.hidden = !(ready && !running && (r.behind > 0 || r.behind === -1));
  p.retry.hidden = r.status !== "failed";
  const showLog = openLogs.has(r.key) && (!!j || true);
  p.logBtn.textContent = showLog ? "Hide log" : "Log";
  p.logBtn.hidden = !j && !r.last_run;
  if (showLog && p.logBox.hidden) { logs.set(r.key, { seq: 0, lines: [], past: null }); p.logSearch.value = ""; p.log.textContent = ""; loadPast(r.key); }
  p.logBox.hidden = !showLog;
  if (showLog && j && (j.seq || 0) > logs.get(r.key).seq) pullLog(r.key);
}

let tools = new Map();
function banners(state) {
  const out = [];
  for (const [tool, j] of Object.entries(state.tools || {})) {
    tools.set(tool, j);
    if (j.running) out.push($("div", { class: "banner" }, $("b", {}, `Installing ${tool}...`), $("span", { class: "hint" }, "Windows may ask for permission.")));
    else if (j.exit_code && Date.now() / 1000 - j.ended < 120) out.push($("div", { class: "banner", style: "background:var(--red-soft)" }, `Installing ${tool} failed (exit code ${j.exit_code}).`));
  }
  if (!state.git) out.push($("div", { class: "banner" }, "Git isn't installed, so projects are downloaded as zip files and updates take longer.",
    $("button", { type: "button", onclick: () => installTool({ tool: "Git", page: "https://git-scm.com/downloads", command: state.platform.startsWith("win") ? "winget install --id Git.Git -e --source winget --accept-source-agreements --accept-package-agreements" : null }) }, "Get Git")));
  document.getElementById("banners").replaceChildren(...out);
}

function notifyEvents(state) {
  const events = state.events || [];
  if (lastEvent === null) { lastEvent = events.length ? events[events.length - 1].id : 0; return; }
  for (const ev of events.filter(e => e.id > lastEvent)) {
    toast(ev.message, ev.type !== "tool");
    // In a browser tab, also use a system notification (the app window uses the tray for this).
    if (state.app.mode !== "window" && settings.notify && "Notification" in window && Notification.permission === "granted" && document.hidden)
      new Notification("repodock", { body: ev.message, icon: "favicon.svg" });
    lastEvent = ev.id;
  }
}

function nav(state) {
  const repos = state.repos;
  const count = f => repos.filter(f).length;
  const isRunning = r => r.job && r.job.running && r.job.kind === "run";
  const views = [["all", "All projects", repos.length, "box"], ["running", "Running", count(isRunning), "play"],
    ["favorites", "Favourites", count(r => r.favorite), "star"], ["updates", "Updates", count(r => r.behind > 0 || r.behind === -1), "down"]];
  const owners = {}, tags = {};
  for (const r of repos) { const o = r.key.split("/")[0]; owners[o] = (owners[o] || 0) + 1; for (const t of r.tags || []) tags[t] = (tags[t] || 0) + 1; }
  const item = (id, label, n, ic) => $("button", { type: "button", class: "nav" + (view === id ? " on" : ""), onclick: () => { view = id; document.getElementById("side").classList.remove("open"); render(lastState); document.getElementById("scroll").scrollTop = 0; } },
    typeof ic === "string" ? icon(ic) : ic, $("span", {}, label), $("span", { class: "count" }, n ? String(n) : ""));
  const out = views.map(([id, label, n, ic]) => item(id, label, n, ic));
  if (Object.keys(tags).length) { out.push($("h4", {}, "Tags")); for (const [t, n] of Object.entries(tags).sort()) out.push(item("tag:" + t, t, n, $("span", { class: "tag", style: "padding:0 4px" }, "#"))); }
  out.push($("h4", {}, "Owners"));
  for (const [o, n] of Object.entries(owners).sort((a, b) => a[0].localeCompare(b[0], undefined, { sensitivity: "base" })))
    out.push(item("owner:" + o, o, n, $("img", { src: avatar(o, 40), alt: "", loading: "lazy" })));
  document.getElementById("nav").replaceChildren(...out);
  const running = repos.filter(r => r.job && r.job.running && r.job.pid);
  document.getElementById("stop-all").hidden = !running.length;
  const updates = count(r => (r.behind > 0 || r.behind === -1) && !(r.job && r.job.running));
  const ua = document.getElementById("update-all"); ua.hidden = !updates; ua.querySelector(".label").textContent = `Update all (${updates})`;
  const titles = { all: "All projects", running: "Running", favorites: "Favourites", updates: "Updates available" };
  document.getElementById("view-title").textContent = titles[view] || (view.startsWith("tag:") ? `#${view.slice(4)}` : view.slice(6));
}

function summary(state) {
  const repos = state.repos, el = document.getElementById("summary");
  el.hidden = !repos.length;
  if (!repos.length) return;
  const running = repos.filter(r => r.job && r.job.running && r.job.kind === "run");
  const cpu = running.reduce((s, r) => s + ((r.stats || {}).cpu || 0), 0), ram = running.reduce((s, r) => s + ((r.stats || {}).rss || 0), 0);
  const disk = repos.reduce((s, r) => s + (r.size || 0), 0);
  const updates = repos.filter(r => r.behind > 0 || r.behind === -1).length;
  const tile = (value, label) => $("div", { class: "stat" }, $("b", {}, value), $("span", {}, label));
  el.replaceChildren(tile(String(repos.length), `project${repos.length === 1 ? "" : "s"}`), tile(String(running.length), "running"),
    tile(running.length ? `${cpu.toFixed(1)}%` : "0%", "CPU in use"), tile(running.length ? bytes(ram) : "0 MB", "memory in use"),
    tile(bytes(disk) || "0 MB", "on disk"), tile(String(updates), updates === 1 ? "update available" : "updates available"));
}

function render(state) {
  lastState = state;
  settings = state.settings; applyTheme(settings);
  notifyEvents(state);
  banners(state);
  nav(state);
  summary(state);
  const main = document.getElementById("main");
  const repos = state.repos;
  document.getElementById("toolbar").hidden = !repos.length;
  if (!repos.length) {
    main.replaceChildren($("div", { class: "empty" }, $("h2", {}, "Welcome to repodock"),
      $("p", {}, "Paste a GitHub link above, like https://github.com/owner/project, or a username to pick from all of their repositories. repodock downloads it, works out how to run it, and asks before it installs or runs anything."),
      $("div", { class: "buttons" }, $("button", { type: "button", class: "primary", onclick: () => searchGitHub() }, icon("search"), "Search GitHub"),
        $("button", { type: "button", onclick: () => document.getElementById("import-file").click() }, "Import a library"))));
    cards.clear(); main.dataset.sig = ""; visibleKeys = new Set();
    return;
  }
  const words = textFilter.toLowerCase().split(/\s+/).filter(Boolean);
  const inView = r => view === "all" || (view === "running" && r.job && r.job.running && r.job.kind === "run") || (view === "favorites" && r.favorite)
    || (view === "updates" && (r.behind > 0 || r.behind === -1)) || (view.startsWith("tag:") && (r.tags || []).includes(view.slice(4)))
    || (view.startsWith("owner:") && r.key.split("/")[0] === view.slice(6));
  let visible = repos.filter(r => inView(r) && words.every(w => `${r.key} ${r.description || ""} ${r.language || ""} ${(r.tags || []).join(" ")}`.toLowerCase().includes(w)));
  const sort = settings.sort || "name";
  const byName = (a, b) => a.key.localeCompare(b.key, undefined, { sensitivity: "base" });
  visible = visible.slice().sort(sort === "recent" ? (a, b) => (b.last_run || 0) - (a.last_run || 0) || byName(a, b)
    : sort === "favorite" ? (a, b) => (b.favorite ? 1 : 0) - (a.favorite ? 1 : 0) || byName(a, b)
    : sort === "size" ? (a, b) => (b.size || 0) - (a.size || 0) || byName(a, b) : byName);
  visibleKeys = new Set(visible.map(r => r.key));
  const groups = new Map();
  const grouped = settings.group !== "none" && !view.startsWith("owner:");
  for (const r of visible) { const o = grouped ? r.key.split("/")[0] : ""; if (!groups.has(o)) groups.set(o, []); groups.get(o).push(r); }
  for (const r of repos) {
    if (!cards.has(r.key)) cards.set(r.key, buildCard(r.key));
    updateCard(cards.get(r.key), r);
  }
  for (const key of [...cards.keys()]) if (!repos.some(r => r.key === key)) cards.delete(key);
  // Rebuild the layout only when the set or order of visible cards changed, so typing and scrolling aren't disturbed.
  const signature = [...groups].map(([o, list]) => o + ":" + list.map(r => r.key).join(",")).join("|") + "|" + (state.me || "");
  if (main.dataset.sig === signature) return;
  main.dataset.sig = signature;
  const sections = [];
  for (const [owner, list] of groups) {
    const mine = state.me && owner.toLowerCase() === state.me.toLowerCase();
    const head = owner ? $("h2", {}, $("img", { src: avatar(owner, 44), alt: "", loading: "lazy" }), owner, $("small", {}, `${list.length} project${list.length === 1 ? "" : "s"}${mine ? " · you" : ""}`)) : null;
    sections.push($("section", { class: "group" }, head, $("div", { class: "grid", style: owner ? null : "margin-top:14px" }, list.map(r => cards.get(r.key).el))));
  }
  if (!sections.length) sections.push($("p", { class: "empty" }, view === "running" ? "Nothing is running." : view === "updates" ? "Everything is up to date." : view === "favorites" ? "No favourites yet. Click the star on a project to add it." : "No project matches the filter."));
  main.replaceChildren(...sections);
}

document.getElementById("filter").addEventListener("input", e => { textFilter = e.target.value; render(lastState); });

async function refresh() {
  try { render(await api("/api/state")); } catch (e) { /* server restarting */ }
}
refresh();
setInterval(() => { if (!document.getElementById("dlg").open && !document.querySelector(".menu:not([hidden])")) refresh(); }, 1500);
</script>
</body>
</html>
"""
