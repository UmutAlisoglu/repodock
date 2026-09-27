"""Start repodock when you sign in to Windows (minimised to the tray)."""

from __future__ import annotations

import sys
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
NAME = "repodock"


def supported() -> bool:
    return sys.platform.startswith("win")


def command() -> str:
    """What Windows runs at sign-in."""
    exe = Path(sys.executable)
    if getattr(sys, "frozen", False):
        gui = exe.with_name("repodock.exe")  # not repodock-cli.exe, which opens a console
        return f'"{gui if gui.exists() else exe}" --minimized'
    pythonw = exe.with_name("pythonw.exe")
    return f'"{pythonw if pythonw.exists() else exe}" -m repodock --minimized'


def enabled() -> bool:
    if not supported():
        return False
    import winreg  # type: ignore[import-not-found]

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, NAME)
            return True
    except OSError:
        return False


def set_enabled(on: bool) -> None:
    if not supported():
        raise OSError("starting with the computer is only available on Windows")
    import winreg  # type: ignore[import-not-found]

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        if on:
            winreg.SetValueEx(key, NAME, 0, winreg.REG_SZ, command())
        else:
            try:
                winreg.DeleteValue(key, NAME)
            except FileNotFoundError:
                pass
