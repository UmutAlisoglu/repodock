"""Fixtures: throwaway folders, local git "remotes" and a fake GitHub API."""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

os.environ["NO_PROXY"] = os.environ["no_proxy"] = "127.0.0.1,localhost"
GIT_ENV = {"GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "T",
           "GIT_COMMITTER_EMAIL": "t@example.com", "GIT_CONFIG_NOSYSTEM": "1"}
os.environ.update(GIT_ENV)
PY = sys.executable


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


def write_files(root: Path, files: dict[str, str]) -> Path:
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


class TempDir:
    def __init__(self):
        self.path = Path(tempfile.mkdtemp(prefix="repodock test "))  # a space, like many Windows paths

    def cleanup(self):
        from repodock.fetch import remove_tree
        remove_tree(self.path)


def make_remote(base: Path, full_name: str, files: dict[str, str]) -> Path:
    """A bare repository at base/owner/name.git with one commit."""
    work = base / "work" / full_name
    work.mkdir(parents=True)
    git(work, "init", "-q", "-b", "main")
    write_files(work, files)
    git(work, "add", "-A")
    git(work, "commit", "-qm", "first")
    bare = base / (full_name + ".git")
    bare.parent.mkdir(parents=True, exist_ok=True)
    git(base, "clone", "-q", "--bare", str(work), str(bare))
    return work


def push_change(base: Path, full_name: str, files: dict[str, str]) -> None:
    work = base / "work" / full_name
    write_files(work, files)
    git(work, "add", "-A")
    git(work, "commit", "-qm", "change")
    git(work, "push", "-q", str(base / (full_name + ".git")), "main")


def zip_bytes(prefix: str, files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, text in files.items():
            zf.writestr(f"{prefix}/{name}", text)
    return buf.getvalue()


def repo_json(full_name, **extra):
    owner, name = full_name.split("/")
    base = {"full_name": full_name, "name": name, "description": f"{name} project", "language": "Python",
            "stargazers_count": 3, "size": 2048, "pushed_at": "2026-09-01T00:00:00Z", "default_branch": "main",
            "fork": False, "archived": False, "html_url": f"https://github.com/{full_name}"}
    base.update(extra)
    return base


class FakeGitHub:
    def __init__(self):
        self.repos: dict[str, dict] = {}
        self.zips: dict[str, bytes] = {}
        self.user_lists: dict[str, list] = {}
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                path = urllib.parse.urlsplit(self.path).path
                code, body, kind = fake.route(path)
                data = body if isinstance(body, bytes) else json.dumps(body).encode()
                self.send_response(code)
                self.send_header("Content-Type", kind)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def route(self, path):
        j = "application/json"
        parts = path.strip("/").split("/")
        if parts[0] == "repos" and len(parts) >= 3:
            full = f"{parts[1]}/{parts[2]}"
            if len(parts) == 3 and full in self.repos:
                return 200, self.repos[full], j
            if len(parts) >= 4 and parts[3] == "zipball" and full in self.zips:
                return 200, self.zips[full], "application/zip"
        if parts[0] == "users" and len(parts) == 3 and parts[2] == "repos" and parts[1] in self.user_lists:
            return 200, self.user_lists[parts[1]], j
        return 404, {"message": "Not Found"}, j

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def wait_for(predicate, timeout=60.0, interval=0.05):
    end = time.time() + timeout
    while time.time() < end:
        if predicate():
            return True
        time.sleep(interval)
    raise AssertionError("timed out waiting")
