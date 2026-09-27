"""Download repositories: git clone when git is installed, otherwise the zip archive."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Callable

from .github import GitHub, GitHubError
from .runner import NO_WINDOW

Log = Callable[[str], None]


class FetchError(Exception):
    pass


def has_git() -> bool:
    return shutil.which("git") is not None


def _run(cmd: list[str], cwd: Path | None, log: Log) -> None:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    try:
        proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **NO_WINDOW)
    except OSError as exc:
        raise FetchError(f"could not start {cmd[0]}: {exc}") from None
    assert proc.stdout is not None
    # Binary on purpose: git redraws progress with \r, and the log keeps only the last state.
    for raw in iter(proc.stdout.readline, b""):
        log(raw.decode("utf-8", "replace").rstrip("\r\n"))
    proc.stdout.close()
    if proc.wait() != 0:
        raise FetchError(f"{' '.join(cmd[:2])} failed (exit code {proc.returncode})")


def clone(url: str, dest: Path, branch: str | None, log: Log) -> None:
    cmd = ["git", "clone", "--progress"]
    if branch:
        cmd += ["--branch", branch]
    cmd += [url, str(dest)]
    log("$ " + " ".join(cmd))
    try:
        _run(cmd, None, log)
    except FetchError:
        remove_tree(dest)
        raise


def pull(dest: Path, log: Log) -> None:
    log("$ git pull --ff-only")
    _run(["git", "pull", "--ff-only"], dest, log)


def git_output(args: list[str], cwd: Path, timeout: float = 120) -> str:
    """Run a quiet git command and return its output (raises FetchError)."""
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    try:
        res = subprocess.run(["git", *args], cwd=cwd, env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                             timeout=timeout, **NO_WINDOW)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise FetchError(f"git {args[0]} failed: {exc}") from None
    if res.returncode != 0:
        raise FetchError((res.stderr or res.stdout).strip().splitlines()[-1] if (res.stderr or res.stdout).strip() else f"git {args[0]} failed")
    return res.stdout


def commits_behind(dest: Path) -> int:
    """Fetch and count the commits the local branch is missing from its upstream."""
    git_output(["fetch", "--quiet"], dest)
    return int(git_output(["rev-list", "--count", "HEAD..@{u}"], dest).strip() or 0)


def download_file(gh: GitHub, url: str, dest: Path, log: Log) -> int:
    """Download one file with progress in the log; returns its size."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    try:
        with gh.open(url, _accept="application/octet-stream") as resp, open(part, "wb") as fh:
            size = int(resp.headers.get("Content-Length") or 0)
            total, shown = 0, -1
            while True:
                chunk = resp.read(1 << 16)
                if not chunk:
                    break
                fh.write(chunk)
                total += len(chunk)
                if size and int(total * 10 / size) != shown:
                    shown = int(total * 10 / size)
                    log(f"\r{total / 1_048_576:.1f} of {size / 1_048_576:.1f} MB")
        os.replace(part, dest)
    except (GitHubError, OSError) as exc:
        try:
            part.unlink()
        except OSError:
            pass
        raise FetchError(f"download failed: {exc}") from None
    log(f"Downloaded {dest.name} ({total / 1_048_576:.1f} MB)")
    return total


def download_zip(gh: GitHub, full_name: str, ref: str, dest: Path, log: Log) -> None:
    """Download and unpack the archive of ``ref`` into ``dest`` (which must not exist)."""
    log(f"Downloading {full_name}@{ref} as a zip (git is not installed)")
    tmp = Path(tempfile.mkdtemp(prefix="repodock-"))
    try:
        archive = tmp / "repo.zip"
        with gh.open(f"/repos/{full_name}/zipball/{ref}") as resp, open(archive, "wb") as fh:
            total = 0
            while True:
                chunk = resp.read(1 << 16)
                if not chunk:
                    break
                fh.write(chunk)
                total += len(chunk)
        log(f"Downloaded {total / 1_048_576:.1f} MB, unpacking")
        extract(archive, tmp / "out")
        top = [p for p in (tmp / "out").iterdir()]
        source = top[0] if len(top) == 1 and top[0].is_dir() else tmp / "out"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(dest))
    except (GitHubError, zipfile.BadZipFile, OSError) as exc:
        raise FetchError(f"download failed: {exc}") from None
    finally:
        remove_tree(tmp)


def extract(archive: Path, out: Path) -> None:
    """Unzip, refusing entries that would land outside ``out`` (zip slip)."""
    out.mkdir(parents=True, exist_ok=True)
    base = out.resolve()
    with zipfile.ZipFile(archive) as zf:
        for info in zf.infolist():
            target = (out / info.filename).resolve()
            if target != base and base not in target.parents:
                raise FetchError(f"unsafe path in archive: {info.filename}")
        zf.extractall(out)


def remove_tree(path: Path) -> None:
    """Delete a folder, including git's read-only files on Windows."""

    def onerror(func, p, _exc):
        try:
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except OSError:
            pass

    if not Path(path).exists():
        return
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=onerror)
    else:
        shutil.rmtree(path, onerror=onerror)
