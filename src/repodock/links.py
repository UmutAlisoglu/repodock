"""repodock:// links: a "Run with repodock" button on a web page opens a repository in repodock.

A link like ``repodock://owner/project`` starts repodock (or brings the running one
to the front) and asks whether to add that project. It never runs anything by
itself. The operating system passes the link to repodock as its only argument,
once the link type is registered: the Windows installer does that, and so does
Settings > "Open repodock:// links" (Windows and Linux).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import urllib.parse
from pathlib import Path

from .github import parse

SCHEME = "repodock"
CLASSES_KEY = r"Software\Classes\repodock"
DESKTOP_FILE = "repodock-link.desktop"


def is_link(text: str) -> bool:
    return text.lower().startswith(SCHEME + ":")


def parse_link(text: str) -> str:
    """The owner/project a repodock:// link points to. Raises ValueError for anything else."""
    if not is_link(text):
        raise ValueError("not a repodock:// link")
    rest = text[len(SCHEME) + 1:].lstrip("/")
    rest = urllib.parse.unquote(rest.split("?", 1)[0].split("#", 1)[0]).strip().strip("/")
    for prefix in ("open/", "add/", "run/"):
        if rest.lower().startswith(prefix):
            rest = rest[len(prefix):]
            break
    if rest.lower().startswith(("github.com/", "www.github.com/")):
        rest = "https://" + rest
    target = parse(rest)
    if not target.repo:
        raise ValueError("a repodock:// link has to name a repository, like repodock://owner/project")
    return target.full_name


# Registering the link type ------------------------------------------------------------------

def supported() -> bool:
    return sys.platform.startswith("win") or (sys.platform.startswith("linux") and shutil.which("xdg-mime") is not None)


def command() -> list[str]:
    """What the system starts for a link (the link itself is added as the last argument)."""
    exe = Path(sys.executable)
    if getattr(sys, "frozen", False):
        gui = exe.with_name("repodock.exe")  # the windowed one, not repodock-cli.exe
        return [str(gui if gui.exists() else exe)]
    if sys.platform.startswith("win"):
        pythonw = exe.with_name("pythonw.exe")
        exe = pythonw if pythonw.exists() else exe
    return [str(exe), "-m", "repodock"]


def _desktop_path() -> Path:
    base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / "applications" / DESKTOP_FILE


def registered() -> bool:
    if sys.platform.startswith("win"):
        import winreg  # type: ignore[import-not-found]

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CLASSES_KEY + r"\shell\open\command") as key:
                return bool(winreg.QueryValueEx(key, "")[0])
        except OSError:
            return False
    return _desktop_path().is_file()


def register(on: bool) -> None:
    if not supported():
        raise OSError("opening repodock:// links is available on Windows and Linux")
    if sys.platform.startswith("win"):
        _register_windows(on)
    else:
        _register_linux(on)


def _register_windows(on: bool) -> None:
    import winreg  # type: ignore[import-not-found]

    if not on:
        for sub in (r"\shell\open\command", r"\shell\open", r"\shell", ""):
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, CLASSES_KEY + sub)
            except OSError:
                pass
        return
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, CLASSES_KEY) as key:
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "URL:repodock link")
        winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, CLASSES_KEY + r"\shell\open\command") as key:
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, subprocess.list2cmdline(command()) + ' "%1"')


def _register_linux(on: bool) -> None:
    path = _desktop_path()
    if not on:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    exec_line = " ".join('"' + part.replace('"', '\\"') + '"' for part in command()) + " %u"
    path.write_text("[Desktop Entry]\nType=Application\nName=repodock\nNoDisplay=true\n"
                    f"Exec={exec_line}\nMimeType=x-scheme-handler/{SCHEME};\n", encoding="utf-8")
    subprocess.run(["xdg-mime", "default", DESKTOP_FILE, f"x-scheme-handler/{SCHEME}"], capture_output=True)
