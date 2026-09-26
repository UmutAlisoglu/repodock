import unittest

from repodock.app import Dock, DockError
from repodock.github import GitHub, Target
from repodock.store import STATE_FILE, Store

from helpers import FakeGitHub, TempDir, make_remote, push_change, repo_json, wait_for, zip_bytes

APP = {"main.py": "import sys\nprint('hello from app', sys.executable)\n"}


class DockTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TempDir()
        self.remotes = self.tmp.path / "remotes"
        self.gh = FakeGitHub()
        self.gh.repos["octo/app"] = repo_json("octo/app")
        make_remote(self.remotes, "octo/app", APP)
        self.dock = self.make_dock()

    def tearDown(self):
        self.dock.runner.stop_all()
        self.gh.close()
        self.tmp.cleanup()

    def make_dock(self, **kw):
        return Dock(Store(self.tmp.path / "dock"), GitHub(None, self.gh.url), git_base=str(self.remotes), me="me", **kw)

    def added(self, text="octo/app"):
        key = self.dock.add(text)["key"]
        wait_for(lambda: self.dock.store.get(key)["status"] != "downloading")
        return key

    def view(self, key):
        return next(r for r in self.dock.state()["repos"] if r["key"] == key)

    def test_add_clones_and_detects(self):
        key = self.added("https://github.com/octo/app")
        self.assertEqual(key, "octo/app")
        v = self.view(key)
        self.assertEqual(v["status"], "ready")
        self.assertTrue(v["git"])
        self.assertEqual(v["command"], "{python} main.py")
        self.assertIn("main.py", v["command_preview"])
        self.assertFalse(v["owned"])
        self.assertEqual(v["stars"], 3)
        self.assertTrue((self.dock.store.root / "octo/app/main.py").exists())
        with self.assertRaisesRegex(DockError, "already"):
            self.dock.add("octo/app")

    def test_unknown_repo(self):
        with self.assertRaisesRegex(DockError, "not found"):
            self.dock.add("octo/missing")

    def test_first_run_asks_then_runs(self):
        key = self.added()
        res = self.dock.run(key)
        self.assertIn("main.py", res["confirm"]["command"])
        self.assertFalse(res["confirm"]["owned"])
        self.assertIsNone(res["confirm"]["deps"])
        self.assertEqual(self.dock.run(key, confirmed=True), {"started": "run"})
        job = self.dock.runner.job(key)
        wait_for(lambda: not job.running)
        self.assertTrue(any("hello from app" in line for _, line in job.output()))
        # Approved once: the next run starts straight away.
        self.assertEqual(self.dock.run(key), {"started": "run"})
        wait_for(lambda: not self.dock.runner.job(key).running)
        # A changed command needs a new confirmation.
        self.assertIn("confirm", self.dock.run(key, command="{python} -c \"print(2)\""))

    def test_dependencies_are_offered_not_installed(self):
        self.gh.repos["octo/deps"] = repo_json("octo/deps")
        make_remote(self.remotes, "octo/deps", {**APP, "requirements.txt": "\n"})
        key = self.added("octo/deps")
        v = self.view(key)
        self.assertTrue(v["needs_deps"])
        self.assertIn("pip install -r requirements.txt", v["deps"])
        res = self.dock.run(key)
        self.assertIn("pip install -r requirements.txt", res["confirm"]["deps"])
        self.assertIn("install", self.dock.run(key, confirmed=True))
        self.assertFalse((self.dock.store.folder(key) / ".venv").exists())
        # Install and run: dependencies go into .venv, then the app runs with that Python.
        self.assertEqual(self.dock.run(key, confirmed=True, install=True), {"started": "install"})
        wait_for(lambda: self.dock.runner.job(key).kind == "run" and not self.dock.runner.job(key).running, 180)
        output = [line for _, line in self.dock.runner.job(key).output()]
        self.assertTrue(any("hello from app" in line and ".venv" in line for line in output), output[-5:])
        self.assertFalse(self.view(key)["needs_deps"])

    def test_skipping_dependencies_is_remembered(self):
        self.gh.repos["octo/deps"] = repo_json("octo/deps")
        make_remote(self.remotes, "octo/deps", {**APP, "requirements.txt": "\n"})
        key = self.added("octo/deps")
        self.assertEqual(self.dock.run(key, confirmed=True, install=False), {"started": "run"})
        wait_for(lambda: not self.dock.runner.job(key).running)
        self.assertFalse(self.view(key)["needs_deps"])
        self.assertFalse((self.dock.store.folder(key) / ".venv").exists())

    def test_custom_command(self):
        key = self.added()
        self.dock.set_command(key, "echo custom")
        v = self.view(key)
        self.assertEqual(v["command"], "echo custom")
        self.assertTrue(v["custom"])
        self.dock.set_command(key, "")
        self.assertEqual(self.view(key)["command"], "{python} main.py")

    def test_update_pulls_new_commits(self):
        key = self.added()
        push_change(self.remotes, "octo/app", {"NEW.md": "new"})
        self.dock.update(key)
        wait_for(lambda: self.dock.store.get(key)["status"] == "ready")
        self.assertTrue((self.dock.store.folder(key) / "NEW.md").exists())

    def test_zip_download_when_git_is_missing(self):
        self.dock = self.make_dock(use_git=False)
        self.gh.repos["octo/zipped"] = repo_json("octo/zipped")
        self.gh.zips["octo/zipped"] = zip_bytes("octo-zipped-abc123", {"main.py": "print(1)", "sub/x.txt": "x"})
        key = self.added("octo/zipped")
        v = self.view(key)
        self.assertEqual(v["status"], "ready", v.get("error"))
        folder = self.dock.store.folder(key)
        self.assertTrue((folder / "main.py").exists() and (folder / "sub/x.txt").exists())
        self.assertFalse(v["git"])
        # Updating a zip download keeps installed dependencies.
        (folder / ".venv").mkdir()
        (folder / ".venv/marker").write_text("keep")
        self.gh.zips["octo/zipped"] = zip_bytes("octo-zipped-def456", {"main.py": "print(2)"})
        self.dock.update(key)
        wait_for(lambda: self.dock.store.get(key)["status"] == "ready")
        self.assertEqual((folder / "main.py").read_text(), "print(2)")
        self.assertTrue((folder / ".venv/marker").exists())
        self.assertFalse((folder / "sub").exists())

    def test_failed_download(self):
        self.gh.repos["octo/gone"] = repo_json("octo/gone")  # API knows it, git remote doesn't exist
        key = self.dock.add("octo/gone")["key"]
        wait_for(lambda: self.dock.store.get(key)["status"] != "downloading")
        v = self.view(key)
        self.assertEqual(v["status"], "failed")
        self.assertFalse(v["exists"])

    def test_user_listing_and_bulk_add(self):
        self.gh.repos["octo/tool"] = repo_json("octo/tool")
        make_remote(self.remotes, "octo/tool", APP)
        self.gh.user_lists["octo"] = [repo_json("octo/app"), repo_json("octo/tool"), repo_json("octo/forked", fork=True), repo_json("octo/old", archived=True)]
        self.added("octo/app")
        res = self.dock.add("https://github.com/octo")
        self.assertEqual(res["kind"], "user")
        flags = {r["name"]: (r["suggested"], r["present"]) for r in res["repos"]}
        self.assertEqual(flags, {"app": (False, True), "tool": (True, False), "forked": (False, False), "old": (False, False)})
        out = self.dock.add_many(["octo/tool", "octo/app"])
        self.assertEqual(out["added"], ["octo/tool"])
        self.assertIn("octo/app", out["errors"])
        with self.assertRaisesRegex(DockError, "not found"):
            self.dock.add("@nobody")

    def test_delete_removes_folder(self):
        key = self.added()
        folder = self.dock.store.folder(key)
        self.dock.delete(key)
        self.assertFalse(folder.exists())
        self.assertFalse(folder.parent.exists())
        self.assertEqual(self.dock.state()["repos"], [])

    def test_state_survives_restart_and_finds_clones(self):
        key = self.added()
        self.dock.set_command(key, "echo saved")
        dock2 = self.make_dock()
        self.assertEqual(dock2.store.get(key)["command"], "echo saved")
        self.assertTrue((self.dock.store.root / STATE_FILE).exists())
        # A clone made by hand in <dir>/<owner>/<name> shows up too.
        from helpers import git
        git(self.dock.store.root, "clone", "-q", str(self.remotes / "octo/app.git"), "someone/copy")
        dock3 = self.make_dock()
        self.assertIn("someone/copy", dock3.store.repos())

    def test_owned(self):
        self.gh.repos["me/mine"] = repo_json("me/mine")
        make_remote(self.remotes, "me/mine", APP)
        key = self.added("me/mine")
        self.assertTrue(self.view(key)["owned"])
        self.assertTrue(self.dock.run(key)["confirm"]["owned"])


if __name__ == "__main__":
    unittest.main()


class StaticSiteTests(unittest.TestCase):
    def test_serves_a_static_site(self):
        import urllib.request
        tmp = TempDir()
        gh = FakeGitHub()
        try:
            gh.repos["octo/site"] = repo_json("octo/site", language="HTML")
            make_remote(tmp.path / "remotes", "octo/site", {"public/index.html": "<h1>static ok</h1>"})
            dock = Dock(Store(tmp.path / "dock"), GitHub(None, gh.url), git_base=str(tmp.path / "remotes"))
            key = dock.add("octo/site")["key"]
            wait_for(lambda: dock.store.get(key)["status"] == "ready")
            self.assertEqual(dock.run(key, confirmed=True), {"started": "run"})
            job = dock.runner.job(key)
            self.assertRegex(job.url, r"^http://localhost:\d+/$")

            def page():
                try:
                    with urllib.request.urlopen(job.url.replace("localhost", "127.0.0.1"), timeout=2) as resp:
                        return b"static ok" in resp.read()
                except OSError:
                    return False

            wait_for(page, 30, 0.2)
            dock.runner.stop_all()
            wait_for(lambda: not job.running, 15)
        finally:
            gh.close()
            tmp.cleanup()
