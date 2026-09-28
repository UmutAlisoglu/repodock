import contextlib
import io
import json
import os
import unittest

from repodock.cli import EXIT_ERROR, EXIT_OK, main

from helpers import FakeGitHub, TempDir, make_remote, repo_json, write_files


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TempDir()
        self.gh = FakeGitHub()
        self.env = dict(os.environ)
        os.environ.update({"REPODOCK_API": self.gh.url, "REPODOCK_GIT_BASE": str(self.tmp.path / "remotes"),
                           "REPODOCK_ME": "me", "GITHUB_TOKEN": "", "GH_TOKEN": ""})
        os.environ.pop("GITHUB_TOKEN")
        os.environ.pop("GH_TOKEN")
        os.environ["PATH"] = os.environ.get("PATH", "")  # gh may be on PATH; REPODOCK_ME avoids asking it

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.env)
        self.gh.close()
        self.tmp.cleanup()

    def test_detect(self):
        write_files(self.tmp.path / "proj", {"package.json": json.dumps({"scripts": {"dev": "vite"}, "dependencies": {"a": "1"}})})
        code, out, _ = run("detect", str(self.tmp.path / "proj"))
        self.assertEqual(code, EXIT_OK)
        self.assertIn("* npm run dev", out)
        self.assertIn("install: npm install", out)

    def test_add_and_list(self):
        self.gh.repos["octo/app"] = repo_json("octo/app")
        make_remote(self.tmp.path / "remotes", "octo/app", {"main.py": "print(1)"})
        dock = str(self.tmp.path / "dock")
        code, out, err = run("--dir", dock, "add", "octo/app")
        self.assertEqual(code, EXIT_OK, err)
        self.assertIn("Done.", out)
        code, out, _ = run("list", "--dir", dock)
        self.assertIn("octo/app", out)
        self.assertIn("{python} main.py", out)

    def test_add_user_lists_first(self):
        self.gh.user_lists["octo"] = [repo_json("octo/a"), repo_json("octo/b", fork=True)]
        code, out, _ = run("--dir", str(self.tmp.path / "dock"), "add", "@octo")
        self.assertEqual(code, EXIT_OK)
        self.assertIn("octo/a", out)
        self.assertIn("fork", out)
        self.assertIn("--all", out)

    def test_bad_link(self):
        code, _, err = run("--dir", str(self.tmp.path / "dock"), "add", "https://gitlab.com/a/b")
        self.assertEqual(code, EXIT_ERROR)
        self.assertIn("github.com", err)

    def test_second_launch_uses_the_running_one(self):
        import threading

        from repodock.app import Dock
        from repodock.github import GitHub
        from repodock.server import make_server
        from repodock.store import Store

        root = self.tmp.path / "dock"
        dock = Dock(Store(root), GitHub(None, self.gh.url))
        server = make_server(dock, 0)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            dock.store.data_dir.mkdir(parents=True, exist_ok=True)
            (dock.store.data_dir / "instance.json").write_text(json.dumps({"port": server.server_address[1], "pid": 1}))
            code, _, err = run("--dir", str(root), "--no-open")
            self.assertEqual(code, EXIT_OK)
            self.assertIn("already running", err)
            # A repodock:// link goes to the running one, which asks about it on the page.
            os.environ["REPODOCK_DIR"] = str(root)
            from unittest import mock
            with mock.patch("webbrowser.open") as browser:  # no app window here, so it opens the browser tab
                code, _, err = run("repodock://octo/app", "--dir", "/somewhere/else")  # options next to a link are ignored
            browser.assert_called_once()
            self.assertEqual(code, EXIT_OK)
            self.assertEqual(dock.state()["link_request"]["repo"], "octo/app")
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
