// node extension/test.js
const assert = require("assert");
const { fit, best, system } = require("./fit.js");

const ollama = ["Ollama-darwin.zip", "OllamaSetup.exe", "ollama-linux-amd64.tgz", "ollama-linux-arm64.tgz", "ollama-windows-amd64.zip", "sha256sum.txt"];
assert.strictEqual(best(ollama, "win", "x64"), "OllamaSetup.exe");
assert.strictEqual(best(ollama, "linux", "x64"), "ollama-linux-amd64.tgz");
assert.strictEqual(best(ollama, "linux", "arm"), "ollama-linux-arm64.tgz");
assert.strictEqual(best(ollama, "darwin", "x64"), "Ollama-darwin.zip");

const obsidian = ["Obsidian-1.9.14.AppImage", "Obsidian-1.9.14-arm64.AppImage", "Obsidian-1.9.14.dmg", "Obsidian-1.9.14.exe", "obsidian_1.9.14_amd64.deb", "Obsidian.1.9.14.exe.sig"];
assert.strictEqual(best(obsidian, "win", "x64"), "Obsidian-1.9.14.exe");
assert.strictEqual(best(obsidian, "darwin", "x64"), "Obsidian-1.9.14.dmg");
assert.strictEqual(best(obsidian, "linux", "x64"), "Obsidian-1.9.14.AppImage");

const rustdesk = ["rustdesk-1.4.2-x86_64.exe", "rustdesk-1.4.2-x86_64.msi", "rustdesk-1.4.2-x86-sciter.exe", "rustdesk-1.4.2-aarch64.dmg", "rustdesk-1.4.2-x86_64.dmg", "rustdesk-1.4.2-x86_64.deb"];
assert.strictEqual(best(rustdesk, "win", "x64"), "rustdesk-1.4.2-x86_64.exe");
assert.strictEqual(best(rustdesk, "darwin", "x64"), "rustdesk-1.4.2-x86_64.dmg");

assert.strictEqual(fit("tool-1.0-source.zip", "win", "x64"), 0);
assert.strictEqual(fit("tool-linux.tar.gz", "win", "x64"), 0);
assert.strictEqual(fit("tool.exe", "linux", "x64"), 0);
assert.strictEqual(best(["checksums.txt", "notes.md"], "win", "x64"), null);

assert.deepStrictEqual(system({ userAgentData: { platform: "Windows" }, userAgent: "" }), { os: "win", arch: "x64" });
assert.deepStrictEqual(system({ platform: "MacIntel", userAgent: "Mozilla/5.0 (Macintosh)" }), { os: "darwin", arch: "x64" });
assert.deepStrictEqual(system({ platform: "Linux aarch64", userAgent: "X11; Linux aarch64" }), { os: "linux", arch: "arm" });
console.log("fit.js: all tests passed");
