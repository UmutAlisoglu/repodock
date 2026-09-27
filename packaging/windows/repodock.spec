# PyInstaller build for Windows: one folder with two programs that share the same files.
#   repodock.exe      the app (window and tray icon, no console)
#   repodock-cli.exe  the same with a console, for the command line and for serving static sites
# Built by .github/workflows/windows.yml:  pyinstaller packaging/windows/repodock.spec
import os

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

here = os.path.abspath(SPECPATH)
icon = os.path.join(here, "repodock.ico")

a = Analysis(
    [os.path.join(here, "entry.py")],
    datas=collect_data_files("repodock") + collect_data_files("webview"),
    hiddenimports=collect_submodules("repodock") + collect_submodules("webview") + ["pystray._win32", "PIL.Image"],
    excludes=["tkinter", "unittest", "pydoc", "test"],
)
pyz = PYZ(a.pure)
app = EXE(pyz, a.scripts, [], exclude_binaries=True, name="repodock", icon=icon, console=False)
cli = EXE(pyz, a.scripts, [], exclude_binaries=True, name="repodock-cli", icon=icon, console=True)
COLLECT(app, cli, a.binaries, a.datas, name="repodock")
