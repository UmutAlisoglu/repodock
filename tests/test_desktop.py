"""The app window, with a stand-in for pywebview (the real one needs a desktop)."""

import sys
import types
import unittest

from repodock import desktop
from repodock.app import Dock
from repodock.github import GitHub
from repodock.store import Store

from helpers import TempDir


class FakeEvent(list):
    def __iadd__(self, handler):
        self.append(handler)
        return self


class FakeWindow:
    def __init__(self, title, url, **kw):
        self.title, self.url, self.kw = title, url, kw
        self.events = types.SimpleNamespace(closing=FakeEvent())
        self.hidden = kw.get("hidden", False)
        self.destroyed = False

    def show(self):
        self.hidden = False

    def hide(self):
        self.hidden = True

    def restore(self):
        pass

    def destroy(self):
        self.destroyed = True


class DesktopTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TempDir()
        self.dock = Dock(Store(self.tmp.path), GitHub(None, "http://127.0.0.1:9"))
        self.windows = []
        fake = types.ModuleType("webview")
        fake.settings = {}
        fake.create_window = lambda *a, **kw: self.windows.append(FakeWindow(*a, **kw)) or self.windows[-1]
        fake.start = self.start
        self.old = sys.modules.get("webview")
        sys.modules["webview"] = fake
        self.during = None

    def tearDown(self):
        if self.old is None:
            sys.modules.pop("webview", None)
        else:
            sys.modules["webview"] = self.old
        self.dock.close()
        self.tmp.cleanup()

    def start(self, gui=None):
        window = self.windows[-1]
        self.during = dict(self.dock.app)
        self.dock.show_window()
        self.assertFalse(window.hidden)
        # The user closes the window.
        results = [handler() for handler in window.events.closing]
        self.closed = results

    def test_window_runs_and_closes(self):
        self.dock.store.set_settings(close_to_tray=True)
        desktop.run(self.dock, "http://localhost:1/", minimized=True)
        window = self.windows[0]
        self.assertTrue(window.kw["hidden"])
        self.assertEqual(self.during["mode"], "window")
        if desktop.make_tray(self.dock, lambda: None, lambda: None) is None:
            self.assertEqual(self.closed, [True])  # without a tray icon, closing quits
        self.assertEqual(self.dock.app["mode"], "browser")
        self.assertIsNone(self.dock.quit)

    def test_failure_is_raised_for_the_fallback(self):
        def broken(gui=None):
            raise OSError("no display")

        sys.modules["webview"].start = broken
        with self.assertRaisesRegex(OSError, "no display"):
            desktop.run(self.dock, "http://localhost:1/")

    def test_unavailable_without_pywebview(self):
        sys.modules.pop("webview")
        import importlib.util
        if importlib.util.find_spec("webview") is None:
            self.assertIn("pywebview", desktop.unavailable())


if __name__ == "__main__":
    unittest.main()
