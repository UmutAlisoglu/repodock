import json
import os
import unittest
from unittest import mock

from repodock import links
from repodock.app import Dock, DockError
from repodock.github import GitHub
from repodock.store import Store

from helpers import FakeGitHub, TempDir, repo_json


class LinkTests(unittest.TestCase):
    def test_parse(self):
        for link in ("repodock://octo/app", "repodock://octo/app/", "REPODOCK://octo/app", "repodock:octo/app",
                     "repodock://open/octo/app", "repodock://github.com/octo/app", "repodock://octo/app?from=badge",
                     "repodock://octo%2Fapp", "repodock://https://github.com/octo/app"):
            self.assertEqual(links.parse_link(link), "octo/app", link)
        for bad in ("repodock://", "repodock://octo", "repodock://gitlab.com/a/b", "https://github.com/octo/app",
                    "repodock://octo/app;rm -rf", "repodock://../../etc"):
            with self.assertRaises(ValueError, msg=bad):
                links.parse_link(bad)

    def test_linux_desktop_file(self):
        tmp = TempDir()
        try:
            with mock.patch.dict(os.environ, {"XDG_DATA_HOME": str(tmp.path)}), mock.patch("subprocess.run") as run:
                links._register_linux(True)
                desktop = (tmp.path / "applications" / links.DESKTOP_FILE).read_text()
                self.assertIn("MimeType=x-scheme-handler/repodock;", desktop)
                self.assertIn("-m\" \"repodock\" %u", desktop)
                run.assert_called_once()
                self.assertTrue(links.registered() or os.name == "nt")
                links._register_linux(False)
                self.assertFalse((tmp.path / "applications" / links.DESKTOP_FILE).exists())
        finally:
            tmp.cleanup()


class DockLinkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TempDir()
        self.gh = FakeGitHub()
        self.gh.repos["octo/app"] = repo_json("octo/app", description="An app")
        self.dock = Dock(Store(self.tmp.path / "dock"), GitHub(None, self.gh.url))

    def tearDown(self):
        self.dock.close()
        self.gh.close()
        self.tmp.cleanup()

    def test_link_request_waits_for_the_page(self):
        shown = []
        self.dock.show_window = lambda: shown.append(True)
        req = self.dock.open_link("repodock://octo/app")
        self.assertEqual(self.dock.state()["link_request"], req)
        self.assertEqual(shown, [True])
        self.assertEqual(self.dock.lookup("octo/app")["description"], "An app")
        self.dock.link_done(req["id"] + 1)  # an older answer doesn't clear a newer link
        self.assertIsNotNone(self.dock.state()["link_request"])
        self.dock.link_done(req["id"])
        self.assertIsNone(self.dock.state()["link_request"])
        # Nothing was added or run by the link itself.
        self.assertEqual(self.dock.store.repos(), {})
        with self.assertRaises(DockError):
            self.dock.open_link("repodock://octo")
        with self.assertRaises(DockError):
            self.dock.lookup("octo/missing")


if __name__ == "__main__":
    unittest.main()
