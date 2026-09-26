"""The list of downloaded repositories, kept as JSON in the repodock folder."""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from pathlib import Path

STATE_FILE = ".repodock.json"


def default_root() -> Path:
    return Path(os.environ.get("REPODOCK_DIR") or Path.home() / "repodock")


class Store:
    """Repos live in <root>/<owner>/<name>; their settings in <root>/.repodock.json."""

    def __init__(self, root: Path):
        self.root = Path(root).expanduser()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / STATE_FILE
        self.lock = threading.RLock()
        self.data = self._load()

    def _load(self) -> dict:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            data = {}
        except ValueError:
            # Keep a broken file for the user instead of silently overwriting it.
            backup = self.path.with_suffix(f".broken-{int(time.time())}.json")
            self.path.replace(backup)
            data = {}
        data.setdefault("version", 1)
        data.setdefault("repos", {})
        return data

    def save(self) -> None:
        with self.lock:
            fd, tmp = tempfile.mkstemp(dir=self.root, prefix=".repodock-", suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(self.data, fh, indent=2, sort_keys=True)
            os.replace(tmp, self.path)

    def repos(self) -> dict[str, dict]:
        with self.lock:
            return {k: dict(v) for k, v in self.data["repos"].items()}

    def get(self, key: str) -> dict | None:
        with self.lock:
            repo = self.data["repos"].get(key)
            return dict(repo) if repo else None

    def put(self, key: str, **fields) -> dict:
        with self.lock:
            repo = self.data["repos"].setdefault(key, {"added": time.time()})
            repo.update(fields)
            self.save()
            return dict(repo)

    def remove(self, key: str) -> None:
        with self.lock:
            self.data["repos"].pop(key, None)
            self.save()

    def folder(self, full_name: str) -> Path:
        owner, name = full_name.split("/", 1)
        return self.root / owner / name

    def scan(self) -> list[str]:
        """Pick up <owner>/<name> git clones that exist on disk but aren't listed yet."""
        added = []
        with self.lock:
            known = {k.lower() for k in self.data["repos"]}
            for owner in sorted(p for p in self.root.iterdir() if p.is_dir() and not p.name.startswith(".")):
                for folder in sorted(p for p in owner.iterdir() if p.is_dir() and not p.name.startswith(".")):
                    key = f"{owner.name}/{folder.name}"
                    if key.lower() not in known and (folder / ".git").exists():
                        self.data["repos"][key] = {"added": time.time(), "full_name": key, "owner": owner.name, "name": folder.name,
                                                   "status": "ready", "source": "found"}
                        added.append(key)
            if added:
                self.save()
        return added
