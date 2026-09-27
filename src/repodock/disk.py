"""How much space a project takes, and what can be removed to free some."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

# Folders that tools recreate: dependencies, caches and build output.
CLEANABLE = (".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache", ".next", ".nuxt",
             ".parcel-cache", ".gradle", "target", "build", "dist", "out", "bin", "obj", ".turbo", ".svelte-kit")
# Always safe to remove (never checked into git in practice).
ALWAYS = {".venv", "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache", ".next", ".nuxt", ".parcel-cache",
          ".turbo", ".svelte-kit"}


def size_of(path: Path) -> int:
    """Bytes used by a folder (symlinks aren't followed)."""
    total = 0
    stack = [str(path)]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                for entry in it:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                        else:
                            total += entry.stat(follow_symlinks=False).st_size
                    except OSError:
                        continue
        except OSError:
            continue
    return total


def _ignored(folder: Path, names: list[str]) -> set[str]:
    """Which of these top-level folders git ignores (so they're build output, not source)."""
    if not names or not (folder / ".git").exists():
        return set()
    try:
        res = subprocess.run(["git", "check-ignore", "--", *names], cwd=folder, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return set()
    return {line.strip().rstrip("/") for line in res.stdout.splitlines() if line.strip()}


def cleanable(folder: Path) -> list[dict]:
    """Top-level folders that can be deleted and recreated, with their sizes."""
    present = [name for name in CLEANABLE if (folder / name).is_dir()]
    ignored = _ignored(folder, [n for n in present if n not in ALWAYS])
    found = []
    for name in present:
        if name in ALWAYS or name in ignored:
            found.append({"name": name, "size": size_of(folder / name)})
    return found
