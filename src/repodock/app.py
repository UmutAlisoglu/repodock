"""What the dashboard can do, independent of HTTP: add, run, stop, update, delete."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

from . import fetch
from .detect import Candidate, detect, expand, free_port, missing_tool
from .github import GitHub, GitHubError, NotFound, Target, parse, summarize
from .runner import Job, Runner
from .store import Store

DEP_DIRS = (".venv", "node_modules")


class DockError(Exception):
    pass


class Dock:
    def __init__(self, store: Store, gh: GitHub, runner: Runner | None = None, git_base: str = "https://github.com",
                 me: str | None = None, use_git: bool | None = None, platform: str | None = None):
        self.store = store
        self.gh = gh
        self.runner = runner or Runner()
        self.git_base = git_base.rstrip("/")
        self.me = me
        self.use_git = fetch.has_git() if use_git is None else use_git
        self.platform = platform
        self._detected: dict[str, list[Candidate]] = {}
        self._lock = threading.Lock()
        self.store.scan()
        # Downloads that were interrupted when repodock last stopped.
        for key, repo in self.store.repos().items():
            if repo.get("status") in ("downloading", "updating"):
                ok = self.store.folder(key).is_dir()
                self.store.put(key, status="ready" if ok else "failed", error=None if ok else "download was interrupted")

    # Queries -------------------------------------------------------------

    def candidates(self, key: str, refresh: bool = False) -> list[Candidate]:
        with self._lock:
            if refresh or key not in self._detected:
                folder = self.store.folder(key)
                self._detected[key] = detect(folder, self.platform) if folder.is_dir() else []
            return self._detected[key]

    def forget_detection(self, key: str) -> None:
        with self._lock:
            self._detected.pop(key, None)

    def owned(self, key: str) -> bool:
        return bool(self.me) and key.split("/")[0].lower() == self.me.lower()

    def _chosen(self, key: str, repo: dict) -> tuple[str | None, Candidate | None]:
        cands = self.candidates(key)
        command = repo.get("command") or (cands[0].command if cands else None)
        match = next((c for c in cands if c.command == command), None)
        return command, match

    def needs_deps(self, key: str, cand: Candidate | None, repo: dict) -> bool:
        if not cand or not cand.deps or repo.get("deps_skipped"):
            return False
        return not (self.store.folder(key) / (cand.deps_marker or "")).exists() if cand.deps_marker else not repo.get("deps_installed")

    def repo_view(self, key: str, repo: dict) -> dict:
        folder = self.store.folder(key)
        view = dict(repo)
        view["key"] = key
        view["path"] = str(folder)
        view["exists"] = folder.is_dir()
        view["owned"] = self.owned(key)
        view["git"] = (folder / ".git").is_dir()
        job = self.runner.job(key)
        view["job"] = job.to_dict() if job else None
        if repo.get("status") == "ready" and folder.is_dir():
            command, cand = self._chosen(key, repo)
            view["candidates"] = [{**c.to_dict(), "preview": self.preview(c.command, folder)} for c in self.candidates(key)]
            view["command"] = command
            view["command_preview"] = self.preview(command, folder) if command else None
            view["custom"] = bool(repo.get("command")) and cand is None
            view["deps"] = self.preview(cand.deps, folder) if cand and cand.deps else None
            view["needs_deps"] = self.needs_deps(key, cand, repo)
            view["missing_tool"] = missing_tool(cand) if cand else None
            view["notes"] = cand.notes if cand else []
        else:
            view["candidates"] = []
        return view

    def preview(self, command: str, folder: Path) -> str:
        """The command as it will run, with a placeholder for the port that's picked at start."""
        return expand(command, folder, "PORT", self.platform)

    def state(self) -> dict:
        repos = self.store.repos()
        return {
            "root": str(self.store.root),
            "me": self.me,
            "git": self.use_git,
            "platform": sys.platform,
            "repos": sorted((self.repo_view(k, r) for k, r in repos.items()), key=lambda r: (r["key"].split("/")[0].lower(), r["key"].lower())),
        }

    # Adding ---------------------------------------------------------------

    def add(self, text: str) -> dict:
        try:
            target = parse(text)
        except ValueError as exc:
            raise DockError(str(exc)) from None
        if target.repo:
            return {"kind": "repo", "key": self.add_repo(target)}
        return {"kind": "user", "owner": target.owner, "repos": self.list_user(target.owner)}

    def list_user(self, owner: str) -> list[dict]:
        try:
            repos = [summarize(r) for r in self.gh.user_repos(owner)]
        except NotFound:
            raise DockError(f"GitHub user {owner} not found") from None
        except GitHubError as exc:
            raise DockError(str(exc)) from None
        have = {k.lower() for k in self.store.repos()}
        for r in repos:
            r["present"] = r["full_name"].lower() in have
            r["suggested"] = not (r["fork"] or r["archived"] or r["present"])
        return repos

    def add_repo(self, target: Target, meta: dict | None = None) -> str:
        full = target.full_name
        if meta is None:
            try:
                meta = summarize(self.gh.repo(full))
            except NotFound:
                raise DockError(f"repository {full} not found (or it's private)") from None
            except GitHubError:
                meta = {"full_name": full, "owner": target.owner, "name": target.repo}  # still try to download
        key = meta["full_name"]  # GitHub's spelling of the name
        existing = self.store.get(key)
        if existing and existing.get("status") in ("ready", "downloading"):
            raise DockError(f"{key} is already in repodock")
        folder = self.store.folder(key)
        if folder.exists() and any(folder.iterdir()):
            raise DockError(f"{folder} already exists and isn't empty")
        branch = target.branch
        self.store.put(key, **meta, status="downloading", error=None, branch=branch, source="git" if self.use_git else "zip")

        def work(log) -> None:
            if self.use_git:
                fetch.clone(f"{self.git_base}/{key}.git", folder, branch, log)
            else:
                fetch.download_zip(self.gh, key, branch or meta.get("default_branch") or "HEAD", folder, log)

        def done(job: Job) -> None:
            self.forget_detection(key)
            if job.error:
                self.store.put(key, status="failed", error=job.error)
            else:
                self.store.put(key, status="ready", error=None, downloaded=time.time())

        self.runner.task(key, "clone", f"Downloading {key}", work, done)
        return key

    def add_many(self, names: list[str]) -> dict:
        added, errors = [], {}
        for name in names:
            try:
                target = parse(name)
                if not target.repo:
                    raise DockError("not a repository")
                added.append(self.add_repo(target))
            except DockError as exc:
                errors[name] = str(exc)
        return {"added": added, "errors": errors}

    # Running --------------------------------------------------------------

    def _repo(self, key: str) -> dict:
        repo = self.store.get(key)
        if not repo:
            raise DockError(f"{key} is not in repodock")
        return repo

    def set_command(self, key: str, command: str | None) -> None:
        self._repo(key)
        command = (command or "").strip() or None
        self.store.put(key, command=command)

    def run(self, key: str, command: str | None = None, confirmed: bool = False, install: bool | None = None) -> dict:
        repo = self._repo(key)
        if repo.get("status") != "ready":
            raise DockError(f"{key} isn't ready yet")
        if self.runner.busy(key):
            raise DockError(f"{key} is already running")
        folder = self.store.folder(key)
        if command is not None:
            self.set_command(key, command)
            repo = self._repo(key)
        command, cand = self._chosen(key, repo)
        if not command:
            raise DockError("no run command found; type one in and try again")
        needs = self.needs_deps(key, cand, repo)
        port = free_port()
        preview = expand(command, folder, port, self.platform, assume_venv=needs and bool(cand and cand.deps and ".venv" in cand.deps))
        if not confirmed and repo.get("approved_command") != command:
            # First run, or the command changed: show exactly what will run.
            return {"confirm": {
                "command": preview, "owned": self.owned(key), "owner": key.split("/")[0],
                "deps": expand(cand.deps, folder, None, self.platform) if needs and cand and cand.deps else None,
                "missing_tool": missing_tool(cand) if cand else None,
            }}
        if needs and install is None:
            return {"install": {"command": expand(cand.deps, folder, None, self.platform)}}  # type: ignore[union-attr]
        self.store.put(key, approved_command=command)
        url = cand.url.replace("{port}", str(port)) if cand and cand.url else None

        def start_run() -> Job:
            # Expand again: {python} points at .venv once dependencies are installed.
            return self.runner.start(key, "run", expand(command, folder, port, self.platform), folder, url=url)

        if needs and install:
            deps = expand(cand.deps, folder, None, self.platform)  # type: ignore[union-attr]

            def after_install(job: Job) -> None:
                self.forget_detection(key)
                if job.exit_code == 0 and not job.stopping:
                    self.store.put(key, deps_installed=True, deps_skipped=False)
                    job.log("")
                    time.sleep(0.2)
                    start_run()

            self.runner.start(key, "install", deps, folder, on_done=after_install)
            return {"started": "install"}
        if needs and install is False:
            self.store.put(key, deps_skipped=True)
        start_run()
        return {"started": "run"}

    def install(self, key: str) -> dict:
        """Install (or reinstall) dependencies without running."""
        repo = self._repo(key)
        _, cand = self._chosen(key, repo)
        if not cand or not cand.deps:
            raise DockError("this run command has no dependency step")
        folder = self.store.folder(key)

        def done(job: Job) -> None:
            self.forget_detection(key)
            if job.exit_code == 0:
                self.store.put(key, deps_installed=True, deps_skipped=False)

        self.runner.start(key, "install", expand(cand.deps, folder, None, self.platform), folder, on_done=done)
        return {"started": "install"}

    def stop(self, key: str) -> bool:
        return self.runner.stop(key)

    # Maintenance ------------------------------------------------------------

    def update(self, key: str) -> None:
        repo = self._repo(key)
        if self.runner.busy(key):
            raise DockError("stop it first")
        folder = self.store.folder(key)
        self.store.put(key, status="updating")

        def work(log) -> None:
            if (folder / ".git").is_dir() and self.use_git:
                fetch.pull(folder, log)
                return
            # Zip download: fetch the new version next to it and keep installed dependencies.
            fresh = folder.with_name(folder.name + ".repodock-new")
            fetch.remove_tree(fresh)
            fetch.download_zip(self.gh, key, repo.get("branch") or repo.get("default_branch") or "HEAD", fresh, log)
            for name in DEP_DIRS:
                if (folder / name).exists():
                    shutil.move(str(folder / name), str(fresh / name))
            old = folder.with_name(folder.name + ".repodock-old")
            os.replace(folder, old)
            os.replace(fresh, folder)
            fetch.remove_tree(old)

        def done(job: Job) -> None:
            self.forget_detection(key)
            self.store.put(key, status="ready", error=job.error, updated=time.time() if not job.error else repo.get("updated"))

        self.runner.task(key, "update", f"Updating {key}", work, done)

    def delete(self, key: str, files: bool = True) -> None:
        self._repo(key)
        self.runner.stop(key)
        job = self.runner.job(key)
        if job and job.running and job.kind in ("clone", "update"):
            raise DockError("wait for the download to finish")
        if files:
            folder = self.store.folder(key)
            fetch.remove_tree(folder)
            owner = folder.parent
            if owner.is_dir() and owner != self.store.root and not any(owner.iterdir()):
                owner.rmdir()
        self.store.remove(key)
        self.forget_detection(key)
        with self.runner.lock:
            self.runner.jobs.pop(key, None)

    def open_folder(self, key: str) -> None:
        self._repo(key)
        folder = str(self.store.folder(key))
        if sys.platform.startswith("win"):
            os.startfile(folder)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", folder])
        else:
            subprocess.Popen(["xdg-open", folder], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
