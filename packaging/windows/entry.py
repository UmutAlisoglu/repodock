"""Entry point for the standalone Windows build (PyInstaller)."""

import sys

from repodock.cli import main

if __name__ == "__main__":
    sys.exit(main())
