"""The 0.2 features: settings per project, releases, stats, updates, logs, cleaning, export and import."""

import io
import subprocess
import sys
import time
import unittest
import zipfile

from repodock import envfile
from repodock.app import KEEP_LOGS, Dock, DockError
from repodock.detect import q
from repodock.disk import size_of
from repodock.github import GitHub, asset_fit
from repodock.procstats import Sampler, parse_cputime
from repodock.runner import Job
from repodock.store import Store

from helpers import PY, FakeGitHub, TempDir, git, make_remote, push_change, repo_json, wait_for

APP = {"main.py": "print('hello')\n"}
WIN = sys.platform.startswith("win")


def py(code: str) -> str:
    """A shell command that runs a line of Python (single quotes only inside)."""
    return f'{q(PY)} -c "{code}"'


class FeatureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TempDir()
        self.remotes = self.tmp.path / "remotes"
        self.gh = FakeGitHub()
        self.gh.repos["octo/app"] = repo_json("octo/app")
        make_remote(self.remotes, "octo/app", APP)
        self.dock = self.make_dock()
        self.key = self.dock.add("octo/app")["key"]
        wait_for(lambda: self.dock.store.get(self.key)["status"] == "ready")

    def tearDown(self):
        self.dock.close()
        self.gh.close()
        self.tmp.cleanup()

    def make_dock(self, name="dock", **kw):
        return Dock(Store(self.tmp.path / name), GitHub(None, self.gh.url), git_base=str(self.remotes), me="me", **kw)

    def view(self, key=None):
        return next(r for r in self.dock.state()["repos"] if r["key"] == (key or self.key))

    def run_to_end(self, **kw):
        res = self.dock.run(self.key, confirmed=True, **kw)
        self.assertEqual(res, {"started": "run"})
        job = self.dock.runner.job(self.key)
        wait_for(lambda: not job.running, 30)
        return job

    # Per-project settings -------------------------------------------------

    def test_configure_validates(self):
        self.dock.configure(self.key, favorite=True, tags=[" Work", "work", "games"], port="8123", auto_restart=1,
                            actions=[{"name": "Build", "command": "make"}, {"name": "", "command": ""}])
        v = self.view()
        self.assertTrue(v["favorite"])
        self.assertEqual(v["tags"], ["work", "games"])
        self.assertEqual(v["port"], 8123)
        self.assertEqual(v["actions"], [{"name": "Build", "command": "make"}])
        with self.assertRaisesRegex(DockError, "port"):
            self.dock.configure(self.key, port=70000)
        with self.assertRaisesRegex(DockError, "needs a command"):
            self.dock.configure(self.key, actions=[{"name": "Test", "command": ""}])
        with self.assertRaisesRegex(DockError, "unknown"):
            self.dock.configure(self.key, command="rm -rf /")

    def test_command_buttons_are_confirmed_once(self):
        self.dock.configure(self.key, actions=[{"name": "Say hi", "command": py("print('hi from button')")}])
        res = self.dock.run(self.key, action="Say hi")
        self.assertEqual(res["confirm"]["action"], "Say hi")
        self.assertIn("hi from button", res["confirm"]["command"])
        job = self.run_to_end(action="Say hi")
        self.assertEqual(job.label, "Say hi")
        self.assertIn("hi from button", job.own_output())
        # Approved now: runs straight away, and the main run command still asks.
        self.assertEqual(self.dock.run(self.key, action="Say hi"), {"started": "run"})
        wait_for(lambda: not self.dock.runner.busy(self.key))
        self.assertIn("confirm", self.dock.run(self.key))
        with self.assertRaisesRegex(DockError, "no Nope button"):
            self.dock.run(self.key, action="Nope")

    def test_port_and_env_file_reach_the_app(self):
        folder = self.dock.store.folder(self.key)
        self.dock.set_env(self.key, [("GREETING", "hello there"), ("EMPTY", "")])
        self.assertEqual(self.dock.env(self.key)["vars"], [("GREETING", "hello there"), ("EMPTY", "")])
        self.assertIn('GREETING="hello there"', (folder / ".env").read_text())
        self.dock.configure(self.key, port=8123)
        self.dock.set_command(self.key, py("import os; print(os.environ['GREETING'], os.environ['PORT'])") + " {port}")
        self.assertIn("8123", self.view()["command_preview"])
        job = self.run_to_end()
        self.assertIn("hello there 8123", job.own_output())
        with self.assertRaisesRegex(DockError, "valid variable"):
            self.dock.set_env(self.key, [("BAD NAME", "x")])

    def test_env_example_is_offered(self):
        (self.dock.store.folder(self.key) / ".env.example").write_text("# settings\nAPI_KEY=\nDEBUG=true\n")
        env = self.dock.env(self.key)
        self.assertFalse(env["exists"])
        self.assertEqual(env["example"], [("API_KEY", ""), ("DEBUG", "true")])
        self.assertEqual(self.view()["env_example"], ".env.example")

    # Running: stats, links, crashes, logs ------------------------------------

    def test_live_stats_for_the_process_tree(self):
        self.dock.set_command(self.key, py("import subprocess,sys,time; p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); print('started', flush=True); time.sleep(30)"))
        self.dock.run(self.key, confirmed=True)
        job = self.dock.runner.job(self.key)
        wait_for(lambda: "started" in job.own_output(), 30)
        self.dock.state()
        time.sleep(1.1)
        stats = self.view()["stats"]
        self.assertGreater(stats["rss"], 1_000_000)
        self.assertGreaterEqual(stats["procs"], 2)
        self.assertGreaterEqual(stats["cpu"], 0)
        self.assertEqual(self.dock.running_apps(), [self.key])
        self.assertEqual(self.dock.stop_all(), 1)
        wait_for(lambda: not job.running, 15)

    def test_crash_is_reported_and_restarted(self):
        self.dock.set_command(self.key, py("import sys; print('boom'); sys.exit(3)"))
        heard = []
        self.dock.listeners.append(heard.append)
        self.dock.configure(self.key, auto_restart=True)
        self.dock.run(self.key, confirmed=True)
        # The first run plus three restarts, then repodock gives up.
        wait_for(lambda: any(e["type"] == "gave-up" for e in self.dock.events), 40)
        crashes = [e for e in self.dock.events if e["type"] == "crash"]
        self.assertEqual(len(crashes), 4)
        self.assertIn("exit code 3", crashes[0]["message"])
        self.assertEqual(len(heard), 5)
        self.assertEqual(self.dock.state()["events"][-1]["type"], "gave-up")

    def test_stopping_is_not_a_crash(self):
        self.dock.set_command(self.key, py("import time; print('up', flush=True); time.sleep(30)"))
        self.dock.run(self.key, confirmed=True)
        job = self.dock.runner.job(self.key)
        wait_for(lambda: "up" in job.own_output(), 30)
        self.dock.stop(self.key)
        wait_for(lambda: not job.running, 15)
        self.assertEqual(list(self.dock.events), [])

    def test_logs_are_kept_for_the_last_runs(self):
        for i in range(KEEP_LOGS + 2):
            self.dock.set_command(self.key, py(f"print('run number {i}')"))
            self.run_to_end()
            time.sleep(1.05)  # log names have one-second resolution
        logs = self.dock.logs(self.key)
        self.assertEqual(len(logs), KEEP_LOGS)
        newest = self.dock.log_file(self.key, logs[0]["name"])
        self.assertIn(f"run number {KEEP_LOGS + 1}", newest)
        self.assertNotIn("run number 0", newest)  # earlier runs' output isn't repeated
        for bad in ("../../.repodock.json", "x.txt"):
            with self.assertRaises(DockError):
                self.dock.log_file(self.key, bad)

    # Releases ----------------------------------------------------------------

    def test_release_zip_for_windows(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("App 1.0/app.exe", b"MZ")
            zf.writestr("App 1.0/unins000.exe", b"MZ")
            zf.writestr("App 1.0/readme.txt", "hi")
        self.gh.add_release("octo/app", "v1.0", {"app-1.0-windows-x64.zip": buf.getvalue(), "app-1.0-linux.tar.gz": b"x", "app.dmg": b"x"})
        dock = self.make_dock(platform="win32")
        rel = dock.releases(self.key)[0]
        self.assertEqual(rel["tag"], "v1.0")
        self.assertEqual([a["name"] for a in rel["assets"] if a["fit"]], ["app-1.0-windows-x64.zip"])
        dock.download_release(self.key, "v1.0", "app-1.0-windows-x64.zip")
        wait_for(lambda: not dock.runner.busy(self.key), 30)
        job = dock.runner.job(self.key)
        self.assertIsNone(job.error, job.own_output())
        v = next(r for r in dock.state()["repos"] if r["key"] == self.key)
        self.assertIn("app.exe", v["command"])
        self.assertTrue(v["command"].startswith("cd /d "))
        self.assertIn("Release v1.0: app.exe", [c["label"] for c in v["candidates"]])
        self.assertIn("confirm", dock.run(self.key))  # a new command is always shown first
        with self.assertRaisesRegex(DockError, "isn't in release"):
            dock.download_release(self.key, "v1.0", "other.zip")

    @unittest.skipIf(WIN, "starts a shell script")
    def test_release_program_runs(self):
        self.gh.add_release("octo/app", "v2.0", {"app-linux-x64": b"#!/bin/sh\necho released program\n"})
        dock = self.make_dock(platform="linux")
        self.assertEqual(dock.releases(self.key)[0]["assets"][0]["fit"], 0)  # no extension: not offered first
        dock.download_release(self.key, "v2.0", "app-linux-x64")
        wait_for(lambda: not dock.runner.busy(self.key), 30)
        self.assertEqual(dock.run(self.key, confirmed=True), {"started": "run"})
        job = dock.runner.job(self.key)
        wait_for(lambda: not job.running, 30)
        self.assertIn("released program", job.own_output())

    def test_release_names_are_checked(self):
        for tag, asset in (("../x", "a.zip"), ("v1", "../a.zip"), ("v1", ".env")):
            with self.assertRaisesRegex(DockError, "bad release"):
                self.dock.download_release(self.key, tag, asset)

    def test_asset_fit(self):
        self.assertGreater(asset_fit("tool-1.2-windows-x64.exe", "win32"), asset_fit("tool.zip", "win32"))
        self.assertEqual(asset_fit("tool-linux-amd64.tar.gz", "win32"), 0)
        self.assertEqual(asset_fit("tool.exe", "linux"), 0)
        self.assertGreater(asset_fit("tool.AppImage", "linux"), 0)
        self.assertGreater(asset_fit("tool-macos.dmg", "darwin"), 0)
        self.assertEqual(asset_fit("Source code.zip".replace(" ", "-"), "win32"), 0)

    # Updates, disk, search ----------------------------------------------------

    def test_update_badge_and_update_all(self):
        self.dock.check_updates(wait=True)
        self.assertEqual(self.view()["behind"], 0)
        push_change(self.remotes, "octo/app", {"a.txt": "1"})
        push_change(self.remotes, "octo/app", {"b.txt": "2"})
        self.dock.check_updates(wait=True)
        self.assertEqual(self.view()["behind"], 2)
        self.assertEqual(self.dock.update_all(), {"updating": [self.key], "skipped": []})
        wait_for(lambda: self.dock.store.get(self.key)["status"] == "ready" and not self.dock.runner.busy(self.key), 30)
        self.assertEqual(self.view()["behind"], 0)
        self.assertTrue((self.dock.store.folder(self.key) / "b.txt").exists())

    def test_zip_download_update_check(self):
        dock = self.make_dock("zipdock", use_git=False)
        self.gh.repos["octo/zipped"] = repo_json("octo/zipped", pushed_at="2020-01-01T00:00:00Z")
        from helpers import zip_bytes
        self.gh.zips["octo/zipped"] = zip_bytes("octo-zipped-abc", APP)
        key = dock.add("octo/zipped")["key"]
        wait_for(lambda: dock.store.get(key)["status"] == "ready", 30)
        dock.check_updates(wait=True)
        self.assertEqual(dock.store.get(key)["behind"], 0)
        self.gh.repos["octo/zipped"]["pushed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 60))
        dock.check_updates(wait=True)
        self.assertEqual(dock.store.get(key)["behind"], -1)
        dock.close()

    def test_clean_frees_dependencies_and_ignored_build_output(self):
        folder = self.dock.store.folder(self.key)
        for name in ("node_modules/pkg", ".venv/lib", "build", "dist"):
            (folder / name).mkdir(parents=True)
        (folder / "node_modules/pkg/index.js").write_text("x" * 5000)
        (folder / "build/out.bin").write_text("y" * 3000)
        (folder / "dist/app.js").write_text("tracked")
        (folder / ".gitignore").write_text("build/\n")
        git(folder, "add", "dist/app.js")
        names = {c["name"]: c["size"] for c in self.dock.cleanable(self.key)}
        self.assertEqual(set(names), {"node_modules", ".venv", "build"})  # dist isn't ignored, so it's kept
        self.assertEqual(names["node_modules"], 5000)
        with self.assertRaisesRegex(DockError, "can't be cleaned"):
            self.dock.clean(self.key, ["dist"])
        self.dock.store.put(self.key, deps_installed=True)
        res = self.dock.clean(self.key, ["node_modules", "build"])
        self.assertEqual(res["freed"], 8000)
        self.assertFalse((folder / "node_modules").exists())
        self.assertTrue((folder / "dist").exists())
        self.assertFalse(self.dock.store.get(self.key)["deps_installed"])
        self.assertEqual(self.dock.store.get(self.key)["size"], size_of(folder))

    def test_search(self):
        self.gh.search_results = [repo_json("octo/app"), repo_json("other/tool", fork=True)]
        res = self.dock.search("tool")
        self.assertEqual(res["total"], 2)
        self.assertEqual([(r["full_name"], r["present"], r["suggested"]) for r in res["repos"]],
                         [("octo/app", True, False), ("other/tool", False, False)])
        with self.assertRaises(DockError):
            self.dock.search("  ")

    def test_toolchain_install_needs_winget(self):
        from repodock import toolchain
        info = toolchain.install_info("Node.js")
        self.assertEqual(info["page"], "https://nodejs.org/")
        if not toolchain.has_winget():
            self.assertIsNone(info["command"])
            with self.assertRaisesRegex(DockError, "nodejs.org"):
                self.dock.install_tool("Node.js")
        with self.assertRaises(DockError):
            self.dock.install_tool("rm -rf")

    # Settings, export and import ---------------------------------------------

    def test_settings(self):
        s = self.dock.set_settings({"theme": "dark", "view": "list", "notify": 0})
        self.assertEqual((s["theme"], s["view"], s["notify"]), ("dark", "list", False))
        self.assertEqual(self.dock.state()["settings"]["theme"], "dark")
        with self.assertRaises(DockError):
            self.dock.set_settings({"unknown": 1})

    def test_export_and_import(self):
        self.dock.configure(self.key, tags=["work"], favorite=True, actions=[{"name": "Test", "command": "pytest"}])
        self.dock.set_command(self.key, "{python} main.py --fast")
        self.dock.set_env(self.key, [("SECRET", "hunter2")])
        self.dock.set_settings({"accent": "#2563eb"})
        library = self.dock.export()
        self.assertEqual(library["repos"], [{"full_name": "octo/app", "command": "{python} main.py --fast", "actions": [{"name": "Test", "command": "pytest"}],
                                             "tags": ["work"], "favorite": True}])
        self.assertNotIn("hunter2", str(library))
        other = self.make_dock("other")
        res = other.import_({**library, "repos": library["repos"] + [{"full_name": "not a repo"}]})
        self.assertEqual(res["added"], ["octo/app"])
        self.assertIn("not a repo", res["errors"])
        wait_for(lambda: other.store.get("octo/app")["status"] == "ready", 30)
        repo = other.store.get("octo/app")
        self.assertEqual((repo["tags"], repo["favorite"], repo["command"]), (["work"], True, "{python} main.py --fast"))
        self.assertEqual(other.store.settings()["accent"], "#2563eb")
        self.assertEqual(other.import_(library)["updated"], ["octo/app"])
        with self.assertRaises(DockError):
            other.import_({"hello": 1})
        other.close()


class UnitTests(unittest.TestCase):
    def test_local_url_is_found_in_output(self):
        job = Job("k", "run", "x")
        job.log("Starting...")
        self.assertIsNone(job.url)
        job.log("  ➜  Local:   http://localhost:5173/")
        self.assertEqual(job.url, "http://localhost:5173/")
        job.log("Also on http://127.0.0.1:9999")
        self.assertEqual(job.url, "http://localhost:5173/")  # the first one wins
        other = Job("k", "run", "x")
        other.log("Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)")
        self.assertEqual(other.url, "http://localhost:8000")
        install = Job("k", "install", "x")
        install.log("see http://localhost:1234")
        self.assertIsNone(install.url)

    def test_envfile_round_trip(self):
        tmp = TempDir()
        try:
            path = tmp.path / ".env"
            path.write_text("# comment\nA=1\nexport B='two words'\nC=3 # note\n", encoding="utf-8")
            self.assertEqual(envfile.read(path), [("A", "1"), ("B", "two words"), ("C", "3")])
            envfile.write(path, [("A", "1"), ("B", 'say "hi"'), ("D", "new")])
            self.assertEqual(path.read_text(encoding="utf-8"), '# comment\nA=1\nB="say \\"hi\\""\nD=new\n')
            self.assertEqual(envfile.read(path), [("A", "1"), ("B", 'say "hi"'), ("D", "new")])
        finally:
            tmp.cleanup()

    def test_cputime(self):
        self.assertEqual(parse_cputime("0:01.50"), 1.5)
        self.assertEqual(parse_cputime("01:02:03"), 3723)
        self.assertEqual(parse_cputime("2-00:00:01"), 172801)

    def test_sampler_measures_a_process(self):
        proc = subprocess.Popen([PY, "-c", "import time\nend = time.time() + 3\nwhile time.time() < end: pass"])
        try:
            sampler = Sampler()
            first = sampler.measure({"busy": proc.pid})["busy"]
            self.assertEqual(first["procs"], 1)
            time.sleep(1.2)
            second = sampler.measure({"busy": proc.pid})["busy"]
            self.assertGreater(second["cpu"], 0)
            self.assertGreater(second["rss"], 0)
            self.assertEqual(sampler.measure({}), {})
        finally:
            proc.kill()
            proc.wait()

    def test_size_of(self):
        tmp = TempDir()
        try:
            (tmp.path / "a/b").mkdir(parents=True)
            (tmp.path / "a/b/f").write_bytes(b"x" * 1234)
            (tmp.path / "g").write_bytes(b"y" * 10)
            self.assertEqual(size_of(tmp.path), 1244)
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
