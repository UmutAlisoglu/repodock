"""Start, watch and stop commands, keeping their output for the dashboard."""

from __future__ import annotations

import collections
import itertools
import os
import re
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07]*\x07")
MAX_LINES = 3000
# Line numbers keep increasing across jobs, so a log view can keep appending
# when an install is followed by a run, or a project is run again.
_SEQ = itertools.count(1)
_SEQ_LOCK = threading.Lock()


@dataclass
class Job:
    """One running (or finished) command, or a background task like a clone."""

    key: str
    kind: str  # "run", "install", "clone", "update"
    command: str
    started: float = field(default_factory=time.time)
    ended: float | None = None
    exit_code: int | None = None
    error: str | None = None
    url: str | None = None
    proc: subprocess.Popen | None = field(default=None, repr=False)
    lines: collections.deque = field(default_factory=lambda: collections.deque(maxlen=MAX_LINES), repr=False)
    seq: int = 0
    stopping: bool = False
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def log(self, text: str) -> None:
        for line in ANSI.sub("", text).replace("\r\n", "\n").split("\n"):
            # Progress bars redraw with \r; keep only the last state.
            line = line.rsplit("\r", 1)[-1]
            with self.lock, _SEQ_LOCK:
                self.seq = next(_SEQ)
                self.lines.append((self.seq, line))

    @property
    def running(self) -> bool:
        return self.ended is None

    def output(self, after: int = 0) -> list[tuple[int, str]]:
        with self.lock:
            return [item for item in self.lines if item[0] > after]

    def to_dict(self) -> dict:
        return {
            "kind": self.kind, "command": self.command, "running": self.running, "started": self.started,
            "ended": self.ended, "exit_code": self.exit_code, "error": self.error, "url": self.url,
            "seq": self.seq, "stopping": self.stopping, "pid": self.proc.pid if self.proc else None,
        }


class Runner:
    def __init__(self) -> None:
        self.jobs: dict[str, Job] = {}
        self.lock = threading.Lock()

    def job(self, key: str) -> Job | None:
        with self.lock:
            return self.jobs.get(key)

    def busy(self, key: str) -> bool:
        job = self.job(key)
        return bool(job and job.running)

    def _register(self, job: Job) -> None:
        with self.lock:
            current = self.jobs.get(job.key)
            if current and current.running:
                raise RuntimeError(f"{job.key} is already busy ({current.kind})")
            if current:
                # Keep the earlier output (download, install) above the new job's.
                job.lines.extend(current.output())
                job.seq = current.seq
            self.jobs[job.key] = job

    def task(self, key: str, kind: str, label: str, fn: Callable[[Callable[[str], None]], None], on_done: Callable[[Job], None] | None = None) -> Job:
        """Run a Python function in the background, capturing what it logs."""
        job = Job(key, kind, label)
        self._register(job)

        def work() -> None:
            try:
                fn(job.log)
                job.exit_code = 0
            except Exception as exc:  # reported on the card, not raised
                job.error = str(exc)
                job.exit_code = 1
                job.log(f"Error: {exc}")
            finally:
                job.ended = time.time()
                if on_done:
                    on_done(job)

        threading.Thread(target=work, name=f"repodock-{kind}-{key}", daemon=True).start()
        return job

    def start(self, key: str, kind: str, command: str, cwd: Path, url: str | None = None, env: dict | None = None,
              on_done: Callable[[Job], None] | None = None) -> Job:
        """Run a shell command in ``cwd`` (the command string is what the user saw and approved)."""
        job = Job(key, kind, command, url=url)
        self._register(job)
        full_env = {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8", "FORCE_COLOR": "0", "NO_COLOR": "1", **(env or {})}
        full_env.pop("VIRTUAL_ENV", None)  # don't leak repodock's own venv into the repo's commands
        options: dict = {}
        if sys.platform.startswith("win"):
            options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
        else:
            options["start_new_session"] = True  # own process group, so Stop reaches child processes
        job.log(f"$ {command}")
        try:
            job.proc = subprocess.Popen(command, shell=True, cwd=str(cwd), env=full_env, stdin=subprocess.DEVNULL,
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **options)
        except OSError as exc:
            job.error = str(exc)
            job.exit_code = -1
            job.ended = time.time()
            job.log(f"Could not start: {exc}")
            if on_done:
                on_done(job)
            return job

        def pump() -> None:
            assert job.proc is not None and job.proc.stdout is not None
            for raw in iter(job.proc.stdout.readline, b""):
                job.log(_decode(raw).rstrip("\r\n"))
            job.proc.stdout.close()
            job.exit_code = job.proc.wait()
            job.ended = time.time()
            if job.stopping:
                job.log("Stopped.")
            else:
                job.log(f"Exited with code {job.exit_code}.")
            if on_done:
                on_done(job)

        threading.Thread(target=pump, name=f"repodock-{kind}-{key}", daemon=True).start()
        return job

    def stop(self, key: str, timeout: float = 5) -> bool:
        job = self.job(key)
        if not job or not job.running or not job.proc:
            return False
        job.stopping = True
        kill_tree(job.proc, timeout)
        return True

    def stop_all(self) -> None:
        for key in list(self.jobs):
            self.stop(key, timeout=3)


def _decode(raw: bytes) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        # Windows consoles often print in the local code page.
        return raw.decode(sys.getfilesystemencoding() or "latin-1", "replace")


def kill_tree(proc: subprocess.Popen, timeout: float = 5) -> None:
    """Stop a process and everything it started (npm -> node, cmd -> python, ...)."""
    if proc.poll() is not None:
        return
    if sys.platform.startswith("win"):
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
        try:
            proc.wait(timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
        return
    try:
        pgid = os.getpgid(proc.pid)
    except ProcessLookupError:
        return
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(pgid, sig)
        except ProcessLookupError:
            return
        try:
            proc.wait(timeout if sig != signal.SIGKILL else 2)
            return
        except subprocess.TimeoutExpired:
            continue
