"""repodock in its own window (Edge WebView2 through pywebview) with a tray icon.

This is optional: without pywebview (``pip install "repodock[app]"``), or
without WebView2, repodock opens in the browser as before. The tray icon
needs pystray and Pillow, which the Windows download includes.
"""

from __future__ import annotations

import importlib.util
import sys
import threading
import time
from pathlib import Path
from typing import Callable

from .app import Dock

WEBVIEW2_KEYS = (
    r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",
    r"SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",
)
ICON = Path(__file__).with_name("assets") / "icon.png"


def unavailable() -> str | None:
    """Why the app window can't be used here, or None if it can."""
    if importlib.util.find_spec("webview") is None:
        return 'the app window needs pywebview (pip install "repodock[app]")'
    if sys.platform.startswith("win") and not _has_webview2():
        return "Microsoft Edge WebView2 isn't installed (https://go.microsoft.com/fwlink/p/?LinkId=2124703)"
    return None


def _has_webview2() -> bool:
    import winreg  # type: ignore[import-not-found]

    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for sub in WEBVIEW2_KEYS:
            try:
                with winreg.OpenKey(hive, sub) as key:
                    version, _ = winreg.QueryValueEx(key, "pv")
                    if version and version != "0.0.0.0":
                        return True
            except OSError:
                continue
    return False


def ask_yes_no(title: str, text: str) -> bool:
    """A native yes/no box (Windows); elsewhere the answer is yes."""
    if not sys.platform.startswith("win"):
        return True
    import ctypes

    MB_YESNO, MB_ICONQUESTION, MB_TOPMOST, IDYES = 0x4, 0x20, 0x40000, 6
    return ctypes.windll.user32.MessageBoxW(None, text, title, MB_YESNO | MB_ICONQUESTION | MB_TOPMOST) == IDYES


class Tray:
    """The icon next to the clock: open the window, stop running apps, quit."""

    def __init__(self, dock: Dock, show: Callable[[], None], quit_: Callable[[], None]):
        import pystray
        from PIL import Image

        self.dock = dock
        self.pystray = pystray
        self.show = show
        self.quit = quit_
        self.shown: tuple[str, ...] = ()
        self.icon = pystray.Icon("repodock", Image.open(ICON), "repodock", menu=pystray.Menu(self._items))
        self.alive = True

    def _items(self):
        Item, Menu = self.pystray.MenuItem, self.pystray.Menu
        yield Item("Open repodock", lambda *_: self.show(), default=True)
        running = self.dock.running_apps()
        if running:
            yield Menu.SEPARATOR
            for key in running:
                yield Item(f"Stop {key}", self._stopper(key))
            yield Item("Stop all", lambda *_: self.dock.stop_all())
        yield Menu.SEPARATOR
        yield Item("Quit repodock", lambda *_: self.quit())

    def _stopper(self, key: str):
        return lambda *_: self.dock.stop(key)

    def start(self) -> None:
        self.icon.run_detached()
        threading.Thread(target=self._watch, name="repodock-tray", daemon=True).start()

    def _watch(self) -> None:
        # Rebuild the menu when apps start or stop, and keep the tooltip current.
        while self.alive:
            running = tuple(self.dock.running_apps())
            if running != self.shown:
                self.shown = running
                n = len(running)
                self.icon.title = f"repodock: {n} app{'s' if n != 1 else ''} running" if n else "repodock"
                try:
                    self.icon.update_menu()
                except Exception:
                    pass
            time.sleep(1.5)

    def notify(self, text: str) -> None:
        try:
            self.icon.notify(text, "repodock")
        except Exception:
            pass

    def stop(self) -> None:
        self.alive = False
        try:
            self.icon.stop()
        except Exception:
            pass


def make_tray(dock: Dock, show: Callable[[], None], quit_: Callable[[], None]) -> Tray | None:
    if not sys.platform.startswith("win"):
        return None  # tray icons from a second thread are only reliable on Windows
    try:
        return Tray(dock, show, quit_)
    except Exception:  # pystray or Pillow missing: closing the window quits instead
        return None


def run(dock: Dock, url: str, minimized: bool = False) -> None:
    """Show the dashboard (already being served at ``url``) in a window until the user quits. Blocks.

    Raises if the window can't be created, so the caller can fall back to the browser.
    """
    import webview

    try:
        webview.settings["ALLOW_DOWNLOADS"] = True  # "Export library" saves a file
        webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True
    except (AttributeError, TypeError):
        pass
    state = {"quitting": False, "hinted": False}
    window = webview.create_window("repodock", url, width=1320, height=860, min_size=(760, 520), hidden=minimized,
                                   background_color="#f5f7f8", text_select=True)

    def show() -> None:
        window.show()
        try:
            window.restore()
            window.on_top = True  # bring it in front of other windows, then behave normally
            window.on_top = False
        except Exception:
            pass

    def quit_(ask: bool = True) -> None:
        running = dock.running_apps()
        if ask and running and not ask_yes_no("Quit repodock?", f"Quitting stops {len(running)} running app{'s' if len(running) != 1 else ''}:\n\n"
                                               + "\n".join(running) + "\n\nQuit anyway?"):
            return
        state["quitting"] = True
        dock.stop_all()
        window.destroy()

    tray = make_tray(dock, show, quit_)

    def on_closing():
        if state["quitting"]:
            return True
        if not tray or not dock.store.settings().get("close_to_tray", True):
            running = dock.running_apps()
            if running and not ask_yes_no("Quit repodock?", f"Closing repodock stops {len(running)} running app{'s' if len(running) != 1 else ''}. Close anyway?"):
                return False
            state["quitting"] = True
            return True
        window.hide()
        if not state["hinted"]:
            state["hinted"] = True
            tray.notify("repodock is still running here. Right-click the icon to stop apps or quit.")
        return False  # keep running in the tray

    window.events.closing += on_closing
    dock.app = {"mode": "window", "tray": bool(tray)}
    dock.show_window = show
    dock.quit = lambda: threading.Thread(target=quit_, daemon=True).start()
    if tray:
        dock.listeners.append(lambda event: tray.notify(event["message"]))
        tray.start()
    try:
        webview.start(gui="edgechromium" if sys.platform.startswith("win") else None)
    finally:
        if tray:
            tray.stop()
        dock.listeners.clear()
        dock.show_window = dock.quit = None
        dock.app = {"mode": "browser", "tray": False}
    if not state["quitting"]:
        raise RuntimeError("the window closed unexpectedly")
