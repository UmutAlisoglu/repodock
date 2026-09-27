"""Understand what the user pasted, and ask GitHub about repositories and users."""

from __future__ import annotations

import json
import os
import platform as platform_mod
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from . import __version__

API = "https://api.github.com"
NAME = r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})"
REPO = r"[A-Za-z0-9._-]{1,100}"


class GitHubError(Exception):
    pass


class NotFound(GitHubError):
    pass


@dataclass
class Target:
    """What the user pasted: one repository, or every repository of a user."""

    owner: str
    repo: str | None = None
    branch: str | None = None

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.repo}" if self.repo else self.owner


def parse(text: str) -> Target:
    """Accepts github.com URLs (repo, tree/branch, .git, user page), git@ URLs, owner/repo and @user."""
    s = text.strip().strip("<>").strip()
    if not s:
        raise ValueError("paste a GitHub link, owner/repo or a username")
    m = re.fullmatch(rf"git@github\.com:({NAME})/({REPO}?)(?:\.git)?/?", s)
    if m:
        return Target(m.group(1), _strip_git(m.group(2)))
    if "://" in s and "github.com" not in s.lower():
        raise ValueError("only github.com links are supported")
    if "github.com" in s.lower():
        if "://" not in s:
            s = "https://" + s
        url = urllib.parse.urlsplit(s)
        if url.hostname not in ("github.com", "www.github.com"):
            raise ValueError("only github.com links are supported")
        parts = [p for p in url.path.split("/") if p]
        if not parts or not re.fullmatch(NAME, parts[0]):
            raise ValueError("that link doesn't point to a GitHub user or repository")
        if len(parts) == 1:
            return Target(parts[0])
        if not re.fullmatch(REPO, _strip_git(parts[1])):
            raise ValueError("that link doesn't point to a GitHub repository")
        branch = "/".join(parts[3:]) if len(parts) > 3 and parts[2] == "tree" else None
        return Target(parts[0], _strip_git(parts[1]), branch)
    if s.startswith("@") and re.fullmatch(NAME, s[1:]):
        return Target(s[1:])
    m = re.fullmatch(rf"({NAME})/({REPO})", s)
    if m:
        return Target(m.group(1), _strip_git(m.group(2)))
    if re.fullmatch(NAME, s):
        return Target(s)
    raise ValueError(f"not a GitHub link, owner/repo or username: {text.strip()}")


def _strip_git(name: str) -> str:
    return name[:-4] if name.endswith(".git") else name


def find_token() -> str | None:
    for name in ("GITHUB_TOKEN", "GH_TOKEN"):
        if os.environ.get(name):
            return os.environ[name]
    if shutil.which("gh"):
        try:
            proc = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=10,
                                  creationflags=0x08000000 if sys.platform.startswith("win") else 0)
        except (OSError, subprocess.TimeoutExpired):
            return None
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip()
    return None


class GitHub:
    def __init__(self, token: str | None = None, base: str = API, timeout: float = 20):
        self.token = token
        self.base = base.rstrip("/")
        self.timeout = timeout

    def request(self, path: str, _accept: str = "application/vnd.github+json", **params: Any) -> urllib.request.Request:
        url = path if path.startswith("http") else self.base + path
        if params:
            url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
        headers = {"Accept": _accept, "User-Agent": f"repodock/{__version__}", "X-GitHub-Api-Version": "2022-11-28"}
        req = urllib.request.Request(url, headers=headers)
        if self.token and (not path.startswith("http") or url.startswith(self.base)):
            # Not forwarded on redirects: release downloads redirect to a signed storage URL.
            req.add_unredirected_header("Authorization", f"Bearer {self.token}")
        return req

    def open(self, path: str, _accept: str = "application/vnd.github+json", **params: Any):
        try:
            return urllib.request.urlopen(self.request(path, _accept, **params), timeout=self.timeout)
        except urllib.error.HTTPError as exc:
            message = ""
            try:
                message = json.loads(exc.read()).get("message", "")
            except (ValueError, AttributeError):
                pass
            if exc.code == 404:
                raise NotFound(f"not found on GitHub: {path.split('?')[0]}") from None
            if exc.code == 403 and "rate limit" in message.lower():
                raise GitHubError("GitHub rate limit reached. Set GITHUB_TOKEN (or log in with `gh auth login`) for a higher limit.") from None
            if exc.code == 401:
                raise GitHubError("GitHub rejected the token (401).") from None
            raise GitHubError(f"GitHub API {exc.code}: {message or exc.reason}") from None
        except (urllib.error.URLError, OSError) as exc:
            raise GitHubError(f"could not reach GitHub: {getattr(exc, 'reason', exc)}") from None

    def get(self, path: str, **params: Any) -> Any:
        with self.open(path, **params) as resp:
            try:
                return json.load(resp)
            except ValueError:
                raise GitHubError("GitHub returned invalid JSON") from None

    def repo(self, full_name: str) -> dict:
        return self.get(f"/repos/{full_name}")

    def user_repos(self, login: str) -> list[dict]:
        found: list[dict] = []
        page = 1
        while page <= 10:  # 1000 repositories is plenty
            batch = self.get(f"/users/{login}/repos", type="owner", sort="pushed", per_page=100, page=page)
            found += batch
            if len(batch) < 100:
                break
            page += 1
        return found

    def releases(self, full_name: str, limit: int = 10) -> list[dict]:
        return self.get(f"/repos/{full_name}/releases", per_page=limit)

    def search(self, query: str, limit: int = 20) -> dict:
        return self.get("/search/repositories", q=query, per_page=limit)

    def viewer(self) -> str | None:
        if not self.token:
            return None
        try:
            return self.get("/user").get("login")
        except GitHubError:
            return None


# Release files worth offering, per platform, best first.
ASSET_KINDS = {
    "win": (".exe", ".msi", ".zip"),
    "darwin": (".dmg", ".pkg", ".zip", ".tar.gz"),
    "linux": (".appimage", ".deb", ".rpm", ".tar.gz", ".tgz", ".zip"),
}
OTHER_OS = {
    "win": ("mac", "darwin", "osx", "linux", "ubuntu", "debian", "appimage"),
    "darwin": ("win", "windows", "linux", "ubuntu", "debian", ".exe", ".msi"),
    "linux": ("win", "windows", "mac", "darwin", "osx", ".exe", ".msi", ".dmg"),
}


def platform_key(platform: str | None = None) -> str:
    p = platform or sys.platform
    return "win" if p.startswith("win") else "darwin" if p == "darwin" else "linux"


def asset_fit(name: str, platform: str | None = None) -> int:
    """How well a release file suits this computer: 0 = not at all, higher is better."""
    key = platform_key(platform)
    lower = name.lower()
    kinds = ASSET_KINDS[key]
    kind = next((i for i, ext in enumerate(kinds) if lower.endswith(ext)), None)
    if kind is None:
        return 0
    words = re.split(r"[^a-z0-9]+", lower)
    if any(w in words or (w.startswith(".") and lower.endswith(w)) for w in OTHER_OS[key]):
        return 0
    score = 10 - kind
    mine = {"win": ("win", "windows", "win64", "x64"), "darwin": ("mac", "macos", "darwin", "osx", "universal"),
            "linux": ("linux", "x86_64", "amd64", "x64")}[key]
    if any(w in words for w in mine):
        score += 5
    if any(w in words for w in ("arm64", "aarch64", "arm")) and "arm" not in platform_mod.machine().lower():
        score -= 4
    if any(w in words for w in ("src", "source", "sources")):
        return 0
    return max(score, 1)


def summarize_release(rel: dict, platform: str | None = None) -> dict:
    assets = []
    for a in rel.get("assets") or []:
        assets.append({"name": a["name"], "size": a.get("size") or 0, "downloads": a.get("download_count") or 0,
                       "url": a.get("browser_download_url"), "api_url": a.get("url"), "fit": asset_fit(a["name"], platform)})
    assets.sort(key=lambda a: -a["fit"])
    return {"tag": rel.get("tag_name"), "name": rel.get("name") or rel.get("tag_name"), "published_at": rel.get("published_at"),
            "prerelease": bool(rel.get("prerelease")), "draft": bool(rel.get("draft")), "url": rel.get("html_url"), "assets": assets}


def summarize(repo: dict) -> dict:
    """The fields repodock keeps about a repository."""
    return {
        "full_name": repo["full_name"],
        "owner": repo["full_name"].split("/")[0],
        "name": repo["name"],
        "description": (repo.get("description") or "").strip(),
        "language": repo.get("language"),
        "stars": repo.get("stargazers_count") or 0,
        "size_kb": repo.get("size") or 0,
        "pushed_at": repo.get("pushed_at"),
        "default_branch": repo.get("default_branch") or "main",
        "fork": bool(repo.get("fork")),
        "archived": bool(repo.get("archived")),
        "html_url": repo.get("html_url") or f"https://github.com/{repo['full_name']}",
    }
