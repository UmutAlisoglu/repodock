"""What the dashboard can do, independent of HTTP: add, run, stop, update, delete, and the rest."""

from __future__ import annotations

import collections
import itertools
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tarfile
import threading
import time
import webbrowser
from pathlib import Path
from typing import Callable

from . import __version__, autostart, disk, envfile, fetch, links, toolchain
from .detect import Candidate, detect, expand, free_port, is_windows, missing_tool, q
from .github import GitHub, GitHubError, NotFound, Target, parse, summarize, summarize_release
from .procstats import Sampler
from .runner import Job, Runner
from .store import Store

DEP_DIRS = (".venv", "node_modules")
KEEP_LOGS = 5
LOG_NAME = re.compile(r"^[\w.-]+\.log$")
TAG = re.compile(r"^[A-Za-z0-9_.-][A-Za-z0-9_./+-]{0,60}$")
ACTION_NAME = re.compile(r"^[\w .+-]{1,24}$")
MAX_RESTARTS = 3  # within RESTART_WINDOW seconds, then give up
RESTART_WINDOW = 300
# Repo fields that describe how you use a project, carried over by export/import.
PORTABLE = ("branch", "command", "actions", "port", "tags", "favorite", "auto_restart", "terminal")
# What programs print when they need a real terminal, which repodock's log isn't.
NEEDS_TTY = re.compile(r"(?i)(open /dev/tty|could not open (a )?(tty|terminal)|not a (tty|terminal)|inappropriate ioctl|"
                       r"the handle is invalid|input is not a terminal|stdin is not a tty)")


class DockError(Exception):
    pass


class Dock:
    def __init__(self, store: Store, gh: GitHub, runner: Runner | None = None, git_base: str = "https://github.com",
                 me: str | None = None, use_git: bool | None = None, platform: str | None = None):
        self.store = store
        self.gh = gh
        self.runner = runner or Runner()
        self.runner.on_finish = self._job_finished
        self.git_base = git_base.rstrip("/")
        self.me = me
        self.use_git = fetch.has_git() if use_git is None else use_git
        self.platform = platform
        self.sampler = Sampler()
        # How repodock is shown: "browser", or "window" with a tray icon. Set by the desktop app.
        self.app = {"mode": "browser", "tray": False}
        self.show_window: Callable[[], None] | None = None
        self.quit: Callable[[], None] | None = None  # set by the desktop app
        self.listeners: list[Callable[[dict], None]] = []  # told about crashes (tray notifications)
        self.events: collections.deque = collections.deque(maxlen=50)
        self.link_request: dict | None = None  # a repodock:// link waiting for an answer on the page
        self._event_ids = itertools.count(1)
        self._restarts: dict[str, list[float]] = {}
        self._detected: dict[str, list[Candidate]] = {}
        self._lock = threading.Lock()
        self._checking: set[str] = set()
        self._sizing: set[str] = set()
        self._stop = threading.Event()
        self.store.scan()
        # Downloads that were interrupted when repodock last stopped.
        for key, repo in self.store.repos().items():
            if repo.get("status") in ("downloading", "updating"):
                ok = self.store.folder(key).is_dir()
                self.store.put(key, status="ready" if ok else "failed", error=None if ok else "download was interrupted")

    # Background work --------------------------------------------------------

    def start_background(self, interval: float = 1800) -> None:
        """Measure disk use now, and look for updates now and every ``interval`` seconds."""

        def loop() -> None:
            self.refresh_sizes()
            while not self._stop.is_set():
                if self.store.settings().get("check_updates"):
                    self.check_updates(wait=True)
                self._stop.wait(interval)

        threading.Thread(target=loop, name="repodock-background", daemon=True).start()

    def close(self) -> None:
        self._stop.set()
        self.runner.stop_all()

    # Queries -------------------------------------------------------------

    def candidates(self, key: str, refresh: bool = False) -> list[Candidate]:
        with self._lock:
            if refresh or key not in self._detected:
                folder = self.store.folder(key)
                self._detected[key] = detect(folder, self.platform) if folder.is_dir() else []
            found = list(self._detected[key])
        repo = self.store.get(key) or {}
        for item in repo.get("releases") or []:
            found.append(Candidate(item["label"], item["command"], "release"))
        return found

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

    def repo_view(self, key: str, repo: dict, stats: dict | None = None) -> dict:
        folder = self.store.folder(key)
        view = dict(repo)
        view["key"] = key
        view["path"] = str(folder)
        view["exists"] = folder.is_dir()
        view["owned"] = self.owned(key)
        view["git"] = (folder / ".git").is_dir()
        view["tags"] = repo.get("tags") or []
        view["actions"] = repo.get("actions") or []
        view["checking"] = key in self._checking
        job = self.runner.job(key)
        view["job"] = job.to_dict() if job else None
        view["stats"] = (stats or {}).get(key)
        if repo.get("status") == "ready" and folder.is_dir():
            command, cand = self._chosen(key, repo)
            view["candidates"] = [{**c.to_dict(), "preview": self.preview(c.command, folder, repo)} for c in self.candidates(key)]
            view["command"] = command
            view["command_preview"] = self.preview(command, folder, repo) if command else None
            view["custom"] = bool(repo.get("command")) and cand is None
            view["deps"] = self.preview(cand.deps, folder, repo) if cand and cand.deps else None
            view["needs_deps"] = self.needs_deps(key, cand, repo)
            tool = missing_tool(cand) if cand else None
            view["missing_tool"] = tool
            view["tool_install"] = toolchain.install_info(tool)
            view["notes"] = cand.notes if cand else []
            view["env_file"] = (folder / ".env").is_file()
            view["env_example"] = next((n for n in (".env.example", ".env.sample", ".env.template") if (folder / n).is_file()), None)
        else:
            view["candidates"] = []
        return view

    def preview(self, command: str, folder: Path, repo: dict | None = None) -> str:
        """The command as it will run, with a placeholder for the port unless one is set."""
        return expand(command, folder, (repo or {}).get("port") or "PORT", self.platform)

    def state(self) -> dict:
        repos = self.store.repos()
        busy = {j.key: j.proc.pid for j in self.runner.running() if j.proc and j.key in repos}
        stats = self.sampler.measure(busy) if busy else {}
        tools = {j.key[5:]: j.to_dict() for j in self.runner.jobs.copy().values() if j.key.startswith("tool:")}
        return {
            "version": __version__,
            "root": str(self.store.root),
            "me": self.me,
            "git": self.use_git,
            "platform": sys.platform,
            "app": {**self.app, "can_quit": self.quit is not None, "autostart_supported": autostart.supported(), "autostart": autostart.enabled(),
                    "links_supported": links.supported(), "links": links.registered()},
            "link_request": self.link_request,
            "settings": self.store.settings(),
            "events": list(self.events),
            "tools": tools,
            "repos": sorted((self.repo_view(k, r, stats) for k, r in repos.items()), key=lambda r: (r["key"].split("/")[0].lower(), r["key"].lower())),
        }

    # repodock:// links ------------------------------------------------------

    def open_link(self, link: str) -> dict:
        """A "Run with repodock" link was opened: ask on the page whether to add that project."""
        try:
            key = links.parse_link(link) if links.is_link(link) else parse(link).full_name
        except ValueError as exc:
            raise DockError(str(exc)) from None
        if "/" not in key:
            raise DockError("a link has to name a repository")
        with self._lock:
            self.link_request = {"id": next(self._event_ids), "repo": key}
        show = self.show_window
        if show:
            # Not on this thread: the window can be busy, and whoever sent the link shouldn't wait for it.
            threading.Thread(target=show, daemon=True).start()
        return self.link_request

    def link_done(self, request_id: int) -> None:
        with self._lock:
            if self.link_request and self.link_request["id"] == request_id:
                self.link_request = None

    def lookup(self, key: str) -> dict:
        """What GitHub says about a repository, to show before adding it."""
        try:
            return summarize(self.gh.repo(key))
        except NotFound:
            raise DockError(f"{key} isn't on GitHub (or it's private)") from None
        except GitHubError as exc:
            raise DockError(str(exc)) from None

    # Adding ---------------------------------------------------------------

    def add(self, text: str) -> dict:
        try:
            target = parse(text)
        except ValueError as exc:
            raise DockError(str(exc)) from None
        if target.repo:
            return {"kind": "repo", "key": self.add_repo(target)}
        return {"kind": "user", "owner": target.owner, "repos": self.list_user(target.owner)}

    def _mark_present(self, repos: list[dict]) -> list[dict]:
        have = {k.lower() for k in self.store.repos()}
        for r in repos:
            r["present"] = r["full_name"].lower() in have
            r["suggested"] = not (r["fork"] or r["archived"] or r["present"])
        return repos

    def list_user(self, owner: str) -> list[dict]:
        try:
            repos = [summarize(r) for r in self.gh.user_repos(owner)]
        except NotFound:
            raise DockError(f"GitHub user {owner} not found") from None
        except GitHubError as exc:
            raise DockError(str(exc)) from None
        return self._mark_present(repos)

    def search(self, query: str) -> dict:
        query = query.strip()
        if not query:
            raise DockError("type something to search for")
        try:
            found = self.gh.search(query)
        except GitHubError as exc:
            raise DockError(str(exc)) from None
        return {"total": found.get("total_count", 0), "repos": self._mark_present([summarize(r) for r in found.get("items") or []])}

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

        found: dict = {}

        def work(log) -> None:
            if self.use_git:
                fetch.clone(f"{self.git_base}/{key}.git", folder, branch, log)
            else:
                fetch.download_zip(self.gh, key, branch or meta.get("default_branch") or "HEAD", folder, log)
            found["ready_made"] = self.ready_made(key)

        def done(job: Job) -> None:
            self.forget_detection(key)
            if job.error:
                self.store.put(key, status="failed", error=job.error)
            else:
                self.store.put(key, status="ready", error=None, downloaded=time.time(), behind=0, ready_made=found.get("ready_made"))
                self.refresh_size(key)

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

    # Per-project settings -------------------------------------------------

    def _repo(self, key: str) -> dict:
        repo = self.store.get(key)
        if not repo:
            raise DockError(f"{key} is not in repodock")
        return repo

    def set_command(self, key: str, command: str | None) -> None:
        self._repo(key)
        command = (command or "").strip() or None
        self.store.put(key, command=command)

    def configure(self, key: str, **fields) -> dict:
        """Change a project's favourite flag, tags, port, extra command buttons or auto-restart."""
        self._repo(key)
        clean: dict = {}
        for name, value in fields.items():
            if name == "favorite":
                clean[name] = bool(value)
            elif name in ("auto_restart", "terminal"):
                clean[name] = bool(value)
                if name == "terminal" and value:
                    clean["needs_terminal"] = False
            elif name == "tags":
                tags = []
                for tag in value or []:
                    tag = str(tag).strip().lower()[:24]
                    if tag and tag not in tags:
                        tags.append(tag)
                clean[name] = tags[:10]
            elif name == "port":
                if value in (None, "", 0):
                    clean[name] = None
                else:
                    port = int(value)
                    if not 1 <= port <= 65535:
                        raise DockError("the port must be between 1 and 65535")
                    clean[name] = port
            elif name == "actions":
                actions = []
                for item in value or []:
                    label, command = str(item.get("name", "")).strip(), str(item.get("command", "")).strip()
                    if not label and not command:
                        continue
                    if not ACTION_NAME.match(label):
                        raise DockError(f"button names are up to 24 letters, digits and spaces: {label!r}")
                    if not command:
                        raise DockError(f"the {label} button needs a command")
                    actions.append({"name": label, "command": command})
                clean[name] = actions[:8]
            else:
                raise DockError(f"unknown setting: {name}")
        return self.store.put(key, **clean)

    def env(self, key: str) -> dict:
        self._repo(key)
        folder = self.store.folder(key)
        example = next((folder / n for n in (".env.example", ".env.sample", ".env.template") if (folder / n).is_file()), None)
        return {"exists": (folder / ".env").is_file(), "vars": envfile.read(folder / ".env"),
                "example": envfile.read(example) if example else [], "example_name": example.name if example else None}

    def set_env(self, key: str, values: list) -> None:
        self._repo(key)
        pairs = [(str(k).strip(), str(v)) for k, v in values if str(k).strip()]
        try:
            envfile.write(self.store.folder(key) / ".env", pairs)
        except ValueError as exc:
            raise DockError(str(exc)) from None

    # Running --------------------------------------------------------------

    def run(self, key: str, command: str | None = None, confirmed: bool = False, install: bool | None = None,
            action: str | None = None) -> dict:
        repo = self._repo(key)
        if repo.get("status") != "ready":
            raise DockError(f"{key} isn't ready yet")
        if self.runner.busy(key):
            raise DockError(f"{key} is already running")
        folder = self.store.folder(key)
        if action is not None:
            # One of the project's own buttons (Build, Test, ...): runs as typed, no dependency step.
            match = next((a for a in repo.get("actions") or [] if a["name"] == action), None)
            if not match:
                raise DockError(f"no {action} button")
            command, cand, needs = match["command"], None, False
        else:
            if command is not None:
                self.set_command(key, command)
                repo = self._repo(key)
            command, cand = self._chosen(key, repo)
            if not command:
                raise DockError("no run command found; type one in and try again")
            needs = self.needs_deps(key, cand, repo)
        port = repo.get("port") or free_port()
        preview = expand(command, folder, port, self.platform, assume_venv=needs and bool(cand and cand.deps and ".venv" in cand.deps))
        approved = set(repo.get("approved") or []) | ({repo["approved_command"]} if repo.get("approved_command") else set())
        if not confirmed and command not in approved:
            # First run, or the command changed: show exactly what will run.
            return {"confirm": {
                "command": preview, "owned": self.owned(key), "owner": key.split("/")[0], "action": action,
                "deps": expand(cand.deps, folder, None, self.platform) if needs and cand and cand.deps else None,
                "missing_tool": missing_tool(cand) if cand else None,
            }}
        if needs and install is None:
            return {"install": {"command": expand(cand.deps, folder, None, self.platform)}}  # type: ignore[union-attr]
        self.store.put(key, approved=sorted(approved | {command})[-20:], approved_command=None, last_run=time.time())
        url = cand.url.replace("{port}", str(port)) if cand and cand.url else None
        env = dict(envfile.read(folder / ".env"))
        if repo.get("port"):
            env["PORT"] = str(port)

        def start_run() -> Job:
            # Expand again: {python} points at .venv once dependencies are installed.
            self._restarts.pop(key, None)
            return self.runner.start(key, "run", expand(command, folder, port, self.platform), folder, url=url, env=env, label=action,
                                     terminal=bool(repo.get("terminal")) and action is None)

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
            self.refresh_size(key)

        self.runner.start(key, "install", expand(cand.deps, folder, None, self.platform), folder, on_done=done)
        return {"started": "install"}

    def stop(self, key: str) -> bool:
        return self.runner.stop(key)

    def stop_all(self) -> int:
        jobs = self.runner.running()
        for job in jobs:
            self.runner.stop(job.key)
        return len(jobs)

    def running_apps(self) -> list[str]:
        return sorted(j.key for j in self.runner.running() if j.kind == "run")

    # When a job ends: keep its log, report crashes, restart if asked ----------

    def _job_finished(self, job: Job) -> None:
        if job.kind in ("run", "install") and not job.key.startswith("tool:"):
            self._save_log(job)
        if job.kind != "run" or job.stopping or not job.exit_code:
            return
        repo = self.store.get(job.key) or {}
        if not repo.get("terminal") and NEEDS_TTY.search("\n".join(job.own_output()[-40:])):
            self.store.put(job.key, needs_terminal=True)
        name = job.label or "It"
        self.event("crash", job.key, f"{job.key} stopped with an error (exit code {job.exit_code}). {name} ran for {_duration(job.ended - job.started)}.")
        if not repo.get("auto_restart"):
            return
        now = time.time()
        recent = [t for t in self._restarts.get(job.key, []) if now - t < RESTART_WINDOW]
        if len(recent) >= MAX_RESTARTS:
            self.event("gave-up", job.key, f"{job.key} keeps crashing, so repodock stopped restarting it.")
            return
        self._restarts[job.key] = recent + [now]

        def again() -> None:
            time.sleep(2)
            if self.runner.busy(job.key) or not self.store.get(job.key):
                return
            try:
                restarts = self._restarts.get(job.key, [])
                new = self.runner.start(job.key, "run", job.command, self.store.folder(job.key), url=job.url, env=None, label=job.label,
                                        terminal=bool(repo.get("terminal")) and not job.label)
                new.log(f"repodock: restarted after a crash ({len(restarts)} of {MAX_RESTARTS})")
                self._restarts[job.key] = restarts
            except RuntimeError:
                pass

        threading.Thread(target=again, daemon=True).start()

    def event(self, kind: str, key: str, message: str) -> dict:
        item = {"id": next(self._event_ids), "time": time.time(), "type": kind, "key": key, "message": message}
        self.events.append(item)
        if self.store.settings().get("notify"):
            for fn in list(self.listeners):
                try:
                    fn(item)
                except Exception:
                    pass
        return item

    # Saved logs -------------------------------------------------------------

    def _log_dir(self, key: str) -> Path:
        return self.store.data_dir / "logs" / key

    def _save_log(self, job: Job) -> None:
        folder = self._log_dir(job.key)
        folder.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(job.started))
        kind = re.sub(r"[^\w-]", "", (job.label or job.kind).lower().replace(" ", "-")) or job.kind
        path = folder / f"{stamp}-{kind}.log"
        header = f"# {job.command}\n# started {time.ctime(job.started)}, exit code {job.exit_code}\n"
        path.write_text(header + "\n".join(job.own_output()) + "\n", encoding="utf-8")
        for old in sorted(folder.glob("*.log"))[:-KEEP_LOGS]:
            try:
                old.unlink()
            except OSError:
                pass

    def logs(self, key: str) -> list[dict]:
        self._repo(key)
        folder = self._log_dir(key)
        found = []
        for path in sorted(folder.glob("*.log"), reverse=True) if folder.is_dir() else []:
            st = path.stat()
            found.append({"name": path.name, "size": st.st_size, "time": st.st_mtime})
        return found

    def log_file(self, key: str, name: str) -> str:
        self._repo(key)
        if not LOG_NAME.match(name):
            raise DockError("no such log")
        path = self._log_dir(key) / name
        if not path.is_file():
            raise DockError("no such log")
        return path.read_text(encoding="utf-8", errors="replace")[-2_000_000:]

    # Releases -----------------------------------------------------------------

    def releases(self, key: str) -> list[dict]:
        self._repo(key)
        try:
            found = self.gh.releases(key)
        except NotFound:
            return []
        except GitHubError as exc:
            raise DockError(str(exc)) from None
        return [summarize_release(r, self.platform) for r in found if not r.get("draft")]

    def ready_made(self, key: str) -> dict | None:
        """A program for this computer in the latest release, if there is one (often easier than building)."""
        try:
            found = self.gh.releases(key, limit=5)
        except (GitHubError, OSError, ValueError):
            return None
        for rel in found:
            if rel.get("draft") or rel.get("prerelease"):
                continue
            summary = summarize_release(rel, self.platform)
            best = summary["assets"][0] if summary["assets"] else None
            # Installers, programs and zips named for this system; not any zip.
            if best and best["fit"] >= 9:
                return {"tag": summary["tag"], "asset": best["name"], "size": best["size"]}
            return None
        return None

    def download_release(self, key: str, tag: str, asset: str) -> dict:
        self._repo(key)
        if self.runner.busy(key):
            raise DockError("stop it first")
        if not TAG.match(tag) or ".." in tag or "/" in asset or "\\" in asset or asset.startswith("."):
            raise DockError("bad release name")
        release = next((r for r in self.releases(key) if r["tag"] == tag), None)
        item = next((a for a in (release or {}).get("assets", []) if a["name"] == asset), None)
        if not item or not item.get("url"):
            raise DockError(f"{asset} isn't in release {tag}")
        folder = self.store.data_dir / "releases" / key / tag.replace("/", "_")
        target = folder / asset

        def work(log) -> None:
            log(f"Downloading {asset} from release {tag}")
            fetch.remove_tree(folder)
            fetch.download_file(self.gh, item["url"], target, log)
            label, command = self._release_command(target, key, log)
            items = [r for r in (self.store.get(key) or {}).get("releases") or [] if r.get("tag") != tag]
            items.insert(0, {"tag": tag, "asset": asset, "label": label, "command": command, "path": str(target)})
            # The new command is chosen, but runs only after it's confirmed on Run.
            self.store.put(key, releases=items[:3], command=command)
            log(f"Ready: press Run to start {label}")

        def done(job: Job) -> None:
            self.forget_detection(key)

        self.runner.task(key, "release", f"Downloading {asset}", work, done)
        return {"started": "release"}

    def _release_command(self, path: Path, key: str, log) -> tuple[str, str]:
        """Unpack a release file if needed and work out how to start it."""
        win = is_windows(self.platform)
        name = path.name.lower()
        label = f"Release {path.parent.name}: {path.name}"
        if name.endswith(".zip") or name.endswith((".tar.gz", ".tgz")):
            out = path.parent / "unpacked"
            log(f"Unpacking {path.name}")
            if name.endswith(".zip"):
                fetch.extract(path, out)
            else:
                _extract_tar(path, out)
            program = _find_program(out, key.split("/")[1], win)
            if not program:
                raise DockError(f"{path.name} doesn't contain a program repodock can start; open the folder instead")
            return f"Release {path.parent.name}: {program.name}", self._start_command(program, win)
        if name.endswith(".msi"):
            return label, f"msiexec /i {q(str(path))}"
        if name.endswith((".dmg", ".pkg")):
            return label, f"open {shlex.quote(str(path))}"
        if name.endswith((".deb", ".rpm")):
            return label, f"xdg-open {shlex.quote(str(path))}"
        if not win:
            path.chmod(path.stat().st_mode | stat.S_IXUSR)
        return label, self._start_command(path, win)

    @staticmethod
    def _start_command(program: Path, win: bool) -> str:
        if win:
            return f"cd /d {q(str(program.parent))} && {q(program.name)}"
        program.chmod(program.stat().st_mode | stat.S_IXUSR)
        return f"cd {shlex.quote(str(program.parent))} && ./{shlex.quote(program.name)}"

    # Toolchains -----------------------------------------------------------------

    def install_tool(self, tool: str) -> dict:
        info = toolchain.install_info(tool)
        if not info or not info["command"]:
            raise DockError(f"repodock can't install {tool} here; download it from {info['page'] if info else 'its website'}")
        key = f"tool:{tool}"

        def done(job: Job) -> None:
            toolchain.refresh_path()
            with self._lock:
                self._detected.clear()
            if job.exit_code == 0:
                self.event("tool", key, f"{tool} is installed.")

        self.runner.start(key, "tool", info["command"], self.store.root, on_done=done)
        return {"started": "tool", "key": key}

    # Updates --------------------------------------------------------------------

    def check_updates(self, keys: list[str] | None = None, wait: bool = False) -> dict:
        """Look for new commits upstream (git fetch), or a newer push for zip downloads."""
        repos = self.store.repos()
        todo = [k for k in (keys or list(repos)) if k in repos and repos[k].get("status") == "ready" and k not in self._checking]
        self._checking.update(todo)

        def one(key: str) -> None:
            try:
                folder = self.store.folder(key)
                if (folder / ".git").is_dir() and self.use_git:
                    behind = fetch.commits_behind(folder)
                else:
                    meta = summarize(self.gh.repo(key))
                    pushed = _parse_time(meta.get("pushed_at"))
                    since = repos[key].get("updated") or repos[key].get("downloaded") or 0
                    behind = -1 if pushed and pushed > since else 0
                if self.store.get(key):
                    self.store.put(key, behind=behind, checked=time.time(), check_error=None)
            except (fetch.FetchError, GitHubError, ValueError, OSError) as exc:
                if self.store.get(key):
                    self.store.put(key, checked=time.time(), check_error=str(exc)[:200])
            finally:
                self._checking.discard(key)

        def all_() -> None:
            for key in todo:
                if self._stop.is_set():
                    self._checking.difference_update(todo)
                    return
                one(key)

        if wait:
            all_()
        else:
            threading.Thread(target=all_, name="repodock-check", daemon=True).start()
        return {"checking": todo}

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
            if (folder / ".env").exists() and not (fresh / ".env").exists():
                shutil.copy2(folder / ".env", fresh / ".env")
            old = folder.with_name(folder.name + ".repodock-old")
            os.replace(folder, old)
            os.replace(fresh, folder)
            fetch.remove_tree(old)

        def done(job: Job) -> None:
            self.forget_detection(key)
            if job.error:
                self.store.put(key, status="ready", error=job.error)
            else:
                self.store.put(key, status="ready", error=None, updated=time.time(), behind=0)
                self.refresh_size(key)

        self.runner.task(key, "update", f"Updating {key}", work, done)

    def update_all(self) -> dict:
        started, skipped = [], []
        for key, repo in self.store.repos().items():
            if repo.get("status") == "ready" and repo.get("behind"):
                if self.runner.busy(key):
                    skipped.append(key)
                else:
                    self.update(key)
                    started.append(key)
        return {"updating": started, "skipped": skipped}

    # Disk use -------------------------------------------------------------------

    def refresh_size(self, key: str) -> None:
        if key in self._sizing:
            return
        self._sizing.add(key)

        def work() -> None:
            try:
                folder = self.store.folder(key)
                if folder.is_dir() and self.store.get(key):
                    self.store.put(key, size=disk.size_of(folder), size_checked=time.time())
            finally:
                self._sizing.discard(key)

        threading.Thread(target=work, daemon=True).start()

    def refresh_sizes(self) -> None:
        for key in self.store.repos():
            folder = self.store.folder(key)
            if folder.is_dir() and self.store.get(key):
                self.store.put(key, size=disk.size_of(folder), size_checked=time.time())

    def cleanable(self, key: str) -> list[dict]:
        self._repo(key)
        return disk.cleanable(self.store.folder(key))

    def clean(self, key: str, names: list[str]) -> dict:
        self._repo(key)
        if self.runner.busy(key):
            raise DockError("stop it first")
        folder = self.store.folder(key)
        allowed = {c["name"] for c in disk.cleanable(folder)}
        freed = 0
        for name in names:
            if name not in allowed:
                raise DockError(f"{name} can't be cleaned")
            freed += disk.size_of(folder / name)
            fetch.remove_tree(folder / name)
        if any(n in DEP_DIRS or n == "venv" for n in names):
            self.store.put(key, deps_installed=False)
        self.forget_detection(key)
        self.store.put(key, size=disk.size_of(folder), size_checked=time.time())
        return {"freed": freed}

    # Removing and opening --------------------------------------------------------

    def delete(self, key: str, files: bool = True) -> None:
        self._repo(key)
        self.runner.stop(key)
        job = self.runner.job(key)
        if job and job.running and job.kind in ("clone", "update", "release"):
            raise DockError("wait for the download to finish")
        if files:
            folder = self.store.folder(key)
            fetch.remove_tree(folder)
            owner = folder.parent
            if owner.is_dir() and owner != self.store.root and not any(owner.iterdir()):
                owner.rmdir()
            fetch.remove_tree(self.store.data_dir / "releases" / key)
            fetch.remove_tree(self._log_dir(key))
        self.store.remove(key)
        self.forget_detection(key)
        with self.runner.lock:
            self.runner.jobs.pop(key, None)

    def open_folder(self, key: str, which: str = "project") -> None:
        self._repo(key)
        folder = self.store.folder(key)
        if which == "releases":
            folder = self.store.data_dir / "releases" / key
        elif which == "logs":
            folder = self._log_dir(key)
        folder.mkdir(parents=True, exist_ok=True)
        _open_path(str(folder))

    @staticmethod
    def open_url(url: str) -> None:
        if not re.match(r"^https?://[^\s]+$", url or ""):
            raise DockError("only web addresses can be opened")
        webbrowser.open(url)

    # Settings, export and import ----------------------------------------------------

    def set_settings(self, changes: dict) -> dict:
        changes = dict(changes)
        if "open_links" in changes:
            try:
                links.register(bool(changes.pop("open_links")))
            except OSError as exc:
                raise DockError(str(exc)) from None
        if "start_with_windows" in changes:
            try:
                autostart.set_enabled(bool(changes.pop("start_with_windows")))
            except OSError as exc:
                raise DockError(str(exc)) from None
        try:
            return self.store.set_settings(**changes)
        except (KeyError, ValueError) as exc:
            raise DockError(f"unknown or invalid setting: {exc}") from None

    def export(self) -> dict:
        repos = []
        for key, repo in sorted(self.store.repos().items()):
            item = {"full_name": key}
            item.update({f: repo[f] for f in PORTABLE if repo.get(f) not in (None, [], False, "")})
            repos.append(item)
        return {"repodock": __version__, "exported": time.strftime("%Y-%m-%dT%H:%M:%S"), "settings": self.store.settings(), "repos": repos}

    def import_(self, data: dict) -> dict:
        if not isinstance(data, dict) or not isinstance(data.get("repos"), list):
            raise DockError("that isn't a repodock library file")
        settings = {k: v for k, v in (data.get("settings") or {}).items() if k in self.store.settings()}
        if settings:
            self.store.set_settings(**settings)
        added, updated, errors = [], [], {}
        for item in data["repos"]:
            try:
                name = str(item.get("full_name", ""))
                target = parse(name)
                if not target.repo:
                    raise DockError("not a repository")
                target.branch = item.get("branch") or None
                fields = {f: item[f] for f in PORTABLE if f in item and f != "branch"}
                existing = next((k for k in self.store.repos() if k.lower() == name.lower()), None)
                if existing:
                    key = existing
                    updated.append(key)
                else:
                    key = self.add_repo(target)
                    added.append(key)
                if "command" in fields:
                    self.set_command(key, fields.pop("command"))
                if fields:
                    self.configure(key, **fields)
            except (DockError, ValueError, TypeError, AttributeError) as exc:
                errors[str(item.get("full_name", "?") if isinstance(item, dict) else item)] = str(exc)
        return {"added": added, "updated": updated, "errors": errors}


def _duration(seconds: float) -> str:
    seconds = int(max(seconds, 0))
    if seconds < 60:
        return f"{seconds} s"
    if seconds < 3600:
        return f"{seconds // 60} min"
    return f"{seconds // 3600} h {seconds % 3600 // 60} min"


def _parse_time(value: str | None) -> float | None:
    if not value:
        return None
    import calendar

    return float(calendar.timegm(time.strptime(value.replace("Z", ""), "%Y-%m-%dT%H:%M:%S")))


def _extract_tar(archive: Path, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    base = out.resolve()
    with tarfile.open(archive) as tf:
        for member in tf.getmembers():
            target = (out / member.name).resolve()
            if (target != base and base not in target.parents) or member.issym() or member.islnk() or member.isdev():
                raise DockError(f"unsafe path in archive: {member.name}")
        if sys.version_info >= (3, 12):
            tf.extractall(out, filter="data")
        else:
            tf.extractall(out)


SKIP_PROGRAMS = re.compile(r"unins|uninstall|update|crash|helper|elevate|notification", re.I)


def _find_program(root: Path, repo_name: str, win: bool) -> Path | None:
    """The main program inside an unpacked release."""
    found: list[Path] = []
    for path in sorted(root.rglob("*")):
        if len(path.relative_to(root).parts) > 3 or not path.is_file() or SKIP_PROGRAMS.search(path.stem):
            continue
        if win:
            if path.suffix.lower() in (".exe", ".bat", ".cmd"):
                found.append(path)
        elif path.suffix.lower() == ".appimage" or (not path.suffix and os.access(path, os.X_OK)):
            found.append(path)
    if not found:
        return None
    wanted = re.sub(r"[^a-z0-9]", "", repo_name.lower())
    found.sort(key=lambda p: (re.sub(r"[^a-z0-9]", "", p.stem.lower()) != wanted, p.suffix.lower() != ".exe" if win else False,
                              len(p.relative_to(root).parts)))
    return found[0]


def _open_path(path: str) -> None:
    if sys.platform.startswith("win"):
        os.startfile(path)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
