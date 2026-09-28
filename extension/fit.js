// Which release file suits this computer: the same rules repodock uses (github.py, asset_fit).
// Loaded before content.js in the browser, and by test.js in Node.
(function (root) {
  const KINDS = {
    win: [".exe", ".msi", ".zip"],
    darwin: [".dmg", ".pkg", ".zip", ".tar.gz"],
    linux: [".appimage", ".deb", ".rpm", ".tar.gz", ".tgz", ".zip"],
  };
  const OTHER_OS = {
    win: ["mac", "macos", "darwin", "osx", "linux", "ubuntu", "debian", "appimage", "android", "ios"],
    darwin: ["win", "win32", "win64", "windows", "linux", "ubuntu", "debian", "android", "ios"],
    linux: ["win", "win32", "win64", "windows", "mac", "macos", "darwin", "osx", "android", "ios"],
  };
  const MINE = {
    win: ["win", "windows", "win64", "x64", "setup", "installer"],
    darwin: ["mac", "macos", "darwin", "osx", "universal"],
    linux: ["linux", "x86_64", "amd64", "x64"],
  };
  const ARM = ["arm64", "aarch64", "arm", "armv7", "armhf"];
  const X86_32 = ["x86", "i386", "i686", "386", "win32", "ia32"];

  // 0 = not for this computer, higher is better.
  function fit(name, os, arch) {
    const lower = name.toLowerCase();
    const kinds = KINDS[os];
    const kind = kinds.findIndex(ext => lower.endsWith(ext));
    if (kind < 0) return 0;
    const words = lower.split(/[^a-z0-9_]+/);
    if (OTHER_OS[os].some(w => words.includes(w))) return 0;
    if (os !== "win" && (lower.endsWith(".exe") || lower.endsWith(".msi"))) return 0;
    if (["src", "source", "sources"].some(w => words.includes(w))) return 0;
    let score = 10 - kind;
    // An installer type only this system uses (.exe, .dmg, .AppImage, ...) counts as naming the system.
    const own = !lower.endsWith(".zip") && !lower.endsWith(".tar.gz") && !lower.endsWith(".tgz");
    if (own || MINE[os].some(w => words.includes(w))) score += 5;
    if (os === "win" && /setup|install/.test(lower)) score += 1;
    const arm = arch === "arm";
    if (ARM.some(w => words.includes(w))) score += arm ? 3 : -6;
    else if (arm && os === "darwin" && !words.includes("universal")) score -= 1;
    if (X86_32.some(w => words.includes(w)) && !words.includes("x86_64")) score -= 3;
    if (words.includes("debug") || words.includes("symbols") || words.includes("pdb")) score -= 5;
    return Math.max(score, 1);
  }

  function best(names, os, arch) {
    let top = null, topScore = 0;
    for (const n of names) {
      const s = fit(n, os, arch);
      if (s > topScore) { top = n; topScore = s; }
    }
    return top;
  }

  function system(nav) {
    const p = ((nav.userAgentData && nav.userAgentData.platform) || nav.platform || nav.userAgent || "").toLowerCase();
    const os = p.includes("win") ? "win" : p.includes("mac") ? "darwin" : p.includes("linux") || p.includes("x11") ? "linux" : null;
    const ua = (nav.userAgent || "").toLowerCase();
    const arch = /arm|aarch64/.test(ua) && os !== "darwin" ? "arm" : "x64";
    return { os, arch };
  }

  const NAMES = { win: "Windows", darwin: "macOS", linux: "Linux" };
  const api = { fit, best, system, NAMES };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.repodockFit = api;
})(typeof self !== "undefined" ? self : this);
