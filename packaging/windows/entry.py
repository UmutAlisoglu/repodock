"""Entry point for the Windows build (repodock.exe and repodock-cli.exe)."""

import os
import sys

if sys.stdout is None or sys.stderr is None:
    # repodock.exe is a windowed program: keep messages in a log file instead of losing them.
    folder = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "repodock")
    os.makedirs(folder, exist_ok=True)
    log = open(os.path.join(folder, "repodock.log"), "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stdout or log
    sys.stderr = sys.stderr or log

from repodock.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
