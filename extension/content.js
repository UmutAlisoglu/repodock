// Adds "Run with repodock" to GitHub project pages and "Download for <system>" to release pages.
// It only reads the page it is on: no data leaves the browser, and it needs no permissions.
(function () {
  const { best, system, NAMES } = self.repodockFit;
  const MARK = "data-repodock";
  // First path parts that are GitHub pages, not users.
  const RESERVED = new Set(["settings", "orgs", "organizations", "marketplace", "explore", "topics", "trending", "collections",
    "notifications", "login", "logout", "signup", "join", "new", "search", "sponsors", "features", "pricing", "about",
    "enterprise", "codespaces", "issues", "pulls", "discussions", "apps", "users", "site", "security", "customer-stories",
    "readme", "team", "stars", "dashboard", "account", "copilot", "models", "github-copilot", "resources", "solutions"]);
  const NAME = /^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})\/[A-Za-z0-9._-]{1,100}$/;

  function currentRepo() {
    const meta = document.querySelector('meta[name="octolytics-dimension-repository_nwo"]');
    const parts = location.pathname.split("/").filter(Boolean);
    if (parts.length < 2 || RESERVED.has(parts[0].toLowerCase())) return null;
    const fromPath = `${parts[0]}/${parts[1]}`;
    // The meta tag is GitHub's own spelling of the name; it can be stale right after a page change.
    const repo = meta && meta.content.toLowerCase() === fromPath.toLowerCase() ? meta.content : fromPath;
    return NAME.test(repo) ? repo : null;
  }

  function el(tag, attrs, ...children) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) node.setAttribute(k, v);
    for (const c of children) node.append(c);
    return node;
  }

  function svg(path) {
    const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    s.setAttribute("viewBox", "0 0 16 16"); s.setAttribute("width", "16"); s.setAttribute("height", "16");
    s.setAttribute("aria-hidden", "true"); s.setAttribute("class", "octicon repodock-icon");
    const p = document.createElementNS("http://www.w3.org/2000/svg", "path");
    p.setAttribute("d", path); p.setAttribute("fill", "currentColor"); s.append(p);
    return s;
  }
  const PLAY = "M4 2.5v11a.5.5 0 0 0 .77.42l8.5-5.5a.5.5 0 0 0 0-.84l-8.5-5.5A.5.5 0 0 0 4 2.5Z";
  const DOWN = "M7.25 1.75a.75.75 0 0 1 1.5 0v7.19l2.22-2.22a.75.75 0 1 1 1.06 1.06l-3.5 3.5a.75.75 0 0 1-1.06 0l-3.5-3.5a.75.75 0 1 1 1.06-1.06l2.22 2.22V1.75ZM2.75 12.5h10.5a.75.75 0 0 1 0 1.5H2.75a.75.75 0 0 1 0-1.5Z";

  function runButton(repo) {
    return el("a", { href: `repodock://${repo}`, class: "btn btn-sm repodock-run", title: `Download ${repo} and run it with repodock (asks first)` },
      svg(PLAY), " Run with repodock");
  }

  function addRunButton() {
    const repo = currentRepo();
    const old = document.querySelector(`[${MARK}="run"]`);
    if (old && old.dataset.repo === repo) return;
    if (old) old.remove();
    if (!repo) return;
    const actions = document.querySelector("ul.pagehead-actions");
    if (!actions) return;
    const li = el("li", { [MARK]: "run", "data-repo": repo }, runButton(repo));
    actions.prepend(li);
  }

  function addDownloadButtons() {
    const { os, arch } = system(navigator);
    if (!os) return;
    const groups = new Map();
    for (const a of document.querySelectorAll('a[href*="/releases/download/"]')) {
      const list = a.closest("ul");
      if (!list || list.hasAttribute(MARK)) continue;
      if (!groups.has(list)) groups.set(list, []);
      groups.get(list).push(a);
    }
    for (const [list, anchors] of groups) {
      list.setAttribute(MARK, "assets");
      const names = anchors.map(a => decodeURIComponent(a.getAttribute("href").split("/").pop()));
      const pick = best(names, os, arch);
      if (!pick) continue;
      const anchor = anchors[names.indexOf(pick)];
      const row = anchor.closest("li");
      if (row) row.classList.add("repodock-best");
      const box = list.closest(".Box") || list;
      const bar = el("div", { class: "repodock-download", [MARK]: "download" },
        el("a", { href: anchor.href, class: "btn btn-primary btn-sm", rel: "nofollow" }, svg(DOWN), ` Download for ${NAMES[os]}`),
        el("span", { class: "repodock-file" }, pick),
        el("span", { class: "repodock-note" }, "picked by repodock"));
      box.before(bar);
    }
  }

  let queued = false;
  function update() {
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => {
      queued = false;
      try { addRunButton(); addDownloadButtons(); } catch (e) { /* the page changed under us; try again on the next change */ }
    });
  }

  update();
  // GitHub changes pages without reloading, and loads release files after the page.
  document.addEventListener("turbo:load", update);
  window.addEventListener("popstate", update);
  new MutationObserver(update).observe(document.documentElement, { childList: true, subtree: true });
})();
