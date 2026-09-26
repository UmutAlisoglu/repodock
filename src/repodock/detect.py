"""Guess how to run a repository, and what to install first.

Commands are shell strings the user can edit. They may contain placeholders
that are filled in when the command runs (see ``expand``):

  {python}         the repo's .venv Python if it exists, else the Python running repodock
  {system_python}  the Python running repodock
  {venv_python}    the repo's .venv Python
  {venv_bin}       the repo's .venv scripts folder
  {port}           a free port on this machine
"""

from __future__ import annotations

import json
import os
import re
import shutil
import socket
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

try:
    import tomllib  # Python 3.11+
except ImportError:  # pragma: no cover - Python < 3.11
    tomllib = None  # type: ignore[assignment]


@dataclass
class Candidate:
    label: str
    command: str
    kind: str
    tool: str | None = None  # program that must be installed, e.g. "node"
    deps: str | None = None  # command that installs dependencies
    deps_marker: str | None = None  # path that exists once dependencies are installed
    url: str | None = None  # page to open once it runs
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


TOOL_NAMES = {
    "node": "Node.js", "npm": "Node.js", "pnpm": "pnpm", "yarn": "Yarn", "bun": "Bun", "deno": "Deno",
    "go": "Go", "cargo": "Rust (cargo)", "dotnet": ".NET SDK", "mvn": "Maven", "gradle": "Gradle",
    "java": "Java", "docker": "Docker", "make": "make", "powershell": "PowerShell", "sh": "a POSIX shell",
}


def is_windows(platform: str | None = None) -> bool:
    return (platform or sys.platform).startswith("win")


def q(path: str) -> str:
    """Quote a path for the shell if it needs it (spaces are common on Windows)."""
    return f'"{path}"' if re.search(r"[\s&()^%!;,]", path) else path


def _read(path: Path, limit: int = 400_000) -> str:
    try:
        with open(path, "rb") as fh:
            return fh.read(limit).decode("utf-8", "replace")
    except OSError:
        return ""


def _toml(path: Path) -> dict:
    if tomllib is None:
        return {}
    try:
        return tomllib.loads(_read(path))
    except (ValueError, tomllib.TOMLDecodeError):  # type: ignore[union-attr]
        return {}


def _find(root: Path, pattern: str, depth: int = 2) -> list[Path]:
    found = []
    for path in sorted(root.glob(pattern)):
        found.append(path)
    if depth > 1:
        for sub in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith(".") and p.name not in SKIP):
            found += _find(sub, pattern, depth - 1)
    return found


SKIP = {"node_modules", ".venv", "venv", "target", "bin", "obj", "dist", "build", "vendor", "__pycache__"}


def detect(root: Path, platform: str | None = None) -> list[Candidate]:
    """Ways to run the repository at ``root``, best guess first."""
    root = Path(root)
    win = is_windows(platform)
    found: list[Candidate] = []
    for finder in (_executables, _node, _deno, _python, _go, _rust, _dotnet, _java, _make, _procfile, _compose, _dockerfile, _scripts, _static):
        try:
            found += finder(root, win)
        except OSError:
            continue
    seen, unique = set(), []
    for c in found:
        if c.command not in seen:
            seen.add(c.command)
            unique.append(c)
    return unique


# Finders -----------------------------------------------------------------

def _executables(root: Path, win: bool) -> list[Candidate]:
    """Prebuilt programs checked into the repository (Windows)."""
    if not win:
        return []
    exes = [p for p in _find(root, "*.exe", depth=2) if not re.search(r"(?i)(unins|setup|install|vc_?redist|dotnet|uninstall)", p.name)]
    return [Candidate(f"Run {p.name}", q(str(p.relative_to(root))), "exe") for p in exes[:3]]


def _node(root: Path, win: bool) -> list[Candidate]:
    pkg_path = root / "package.json"
    if not pkg_path.is_file():
        return []
    try:
        pkg = json.loads(_read(pkg_path))
    except ValueError:
        pkg = {}
    scripts = pkg.get("scripts") or {}
    if (root / "pnpm-lock.yaml").exists():
        pm, install = "pnpm", "pnpm install"
    elif (root / "yarn.lock").exists():
        pm, install = "yarn", "yarn install"
    elif (root / "bun.lockb").exists() or (root / "bun.lock").exists():
        pm, install = "bun", "bun install"
    else:
        pm, install = "npm", "npm ci" if (root / "package-lock.json").exists() else "npm install"
    has_deps = bool(pkg.get("dependencies") or pkg.get("devDependencies"))
    common = dict(kind="node", tool=pm, deps=install if has_deps else None, deps_marker="node_modules" if has_deps else None)
    out = []
    for name in ("dev", "start", "serve", "preview", "develop"):
        if name in scripts:
            cmd = f"{pm} start" if name == "start" and pm in ("npm", "yarn") else f"{pm} run {name}"
            out.append(Candidate(f"{pm} {'start' if name == 'start' else 'run ' + name}", cmd, notes=[f"runs: {scripts[name]}"], **common))
    if not out:
        main = pkg.get("main")
        for entry in ([main] if main else []) + ["index.js", "server.js", "app.js", "main.js"]:
            if entry and (root / entry).is_file():
                out.append(Candidate(f"node {entry}", f"node {q(entry)}", **{**common, "tool": "node"}))
                break
    for c in out:
        if pm != "npm" and c.tool == pm and not shutil.which(pm):
            c.notes.append(f"{pm} not found; `npm install -g {pm}` or change the command to npm")
    return out


def _deno(root: Path, win: bool) -> list[Candidate]:
    for name in ("deno.json", "deno.jsonc"):
        if (root / name).is_file():
            text = re.sub(r"^\s*//.*$", "", _read(root / name), flags=re.M)
            try:
                tasks = (json.loads(text).get("tasks") or {})
            except ValueError:
                tasks = {}
            return [Candidate(f"deno task {t}", f"deno task {t}", "deno", tool="deno") for t in ("dev", "start") if t in tasks]
    return []


PY_ENTRIES = ("main.py", "app.py", "run.py", "server.py", "bot.py", "start.py", "gui.py", "__main__.py")


def _python(root: Path, win: bool) -> list[Candidate]:
    req = root / "requirements.txt"
    pyproject = root / "pyproject.toml"
    setup = root / "setup.py"
    entries = [e for e in PY_ENTRIES if (root / e).is_file()]
    manage = (root / "manage.py").is_file()
    if not (req.is_file() or pyproject.is_file() or setup.is_file() or entries or manage):
        return []
    reqs_text = _read(req).lower() if req.is_file() else ""
    project = _toml(pyproject) if pyproject.is_file() else {}
    proj = project.get("project") or {}
    poetry = ((project.get("tool") or {}).get("poetry") or {})
    installable = bool(proj.get("name") or poetry.get("name") or setup.is_file())
    all_text = reqs_text + " " + " ".join(proj.get("dependencies") or []).lower()

    steps = ["{system_python} -m venv .venv"]
    if req.is_file():
        steps.append("{venv_python} -m pip install -r requirements.txt")
    if installable:
        steps.append("{venv_python} -m pip install -e .")
    deps = " && ".join(steps) if len(steps) > 1 else None
    common = dict(kind="python", deps=deps, deps_marker=".venv" if deps else None)

    out = []
    scripts = proj.get("scripts") or poetry.get("scripts") or {}
    for name in list(scripts)[:2]:
        out.append(Candidate(f"{name} (installed command)", f'"{{venv_bin}}{os.sep}{name}"', **{**common, "deps": deps or "{system_python} -m venv .venv && {venv_python} -m pip install -e .", "deps_marker": ".venv"}))
    if manage:
        out.append(Candidate("Django dev server", "{python} manage.py runserver {port}", url="http://localhost:{port}/", **common))
    for entry in entries:
        src = _read(root / entry, 60_000)
        if "streamlit" in all_text and "streamlit" in src:
            out.append(Candidate(f"streamlit run {entry}", f"{{python}} -m streamlit run {entry} --server.port {{port}}", url="http://localhost:{port}/", **common))
        else:
            out.append(Candidate(f"python {entry}", f"{{python}} {entry}", **common))
    if not out:
        # A package with __main__.py: python -m package
        for main in _find(root, "__main__.py", depth=3):
            pkg = main.parent
            if pkg == root:
                continue
            module = ".".join(pkg.relative_to(root / "src" if (root / "src") in pkg.parents else root).parts)
            out.append(Candidate(f"python -m {module}", f"{{python}} -m {module}", **{**common, "deps": deps or "{system_python} -m venv .venv && {venv_python} -m pip install -e .", "deps_marker": ".venv"}))
            break
    return out


def _go(root: Path, win: bool) -> list[Candidate]:
    if not (root / "go.mod").is_file():
        return []
    out = []
    if any("package main" in _read(p, 20_000) for p in root.glob("*.go")):
        out.append(Candidate("go run .", "go run .", "go", tool="go"))
    cmd = root / "cmd"
    if cmd.is_dir():
        for sub in sorted(p for p in cmd.iterdir() if p.is_dir())[:3]:
            out.append(Candidate(f"go run ./cmd/{sub.name}", f"go run ./cmd/{sub.name}", "go", tool="go"))
    return out


def _rust(root: Path, win: bool) -> list[Candidate]:
    if not (root / "Cargo.toml").is_file():
        return []
    return [Candidate("cargo run --release", "cargo run --release", "rust", tool="cargo", notes=["the first run compiles the project, which can take a while"])]


def _dotnet(root: Path, win: bool) -> list[Candidate]:
    projects = [p for p in _find(root, "*.csproj", depth=3) + _find(root, "*.fsproj", depth=3) if not re.search(r"(?i)test", p.name)]
    if not projects:
        return []
    # Prefer executable projects.
    projects.sort(key=lambda p: "<OutputType>Exe" not in _read(p) and "<OutputType>WinExe" not in _read(p))
    return [Candidate(f"dotnet run ({p.stem})", f"dotnet run --project {q(str(p.relative_to(root)))}", "dotnet", tool="dotnet") for p in projects[:2]]


def _java(root: Path, win: bool) -> list[Candidate]:
    out = []
    if (root / "pom.xml").is_file():
        spring = "spring-boot" in _read(root / "pom.xml")
        wrapper = "mvnw.cmd" if win else "./mvnw"
        mvn = wrapper if (root / ("mvnw.cmd" if win else "mvnw")).exists() else "mvn"
        goal = "spring-boot:run" if spring else "compile exec:java"
        out.append(Candidate(f"{mvn} {goal}", f"{mvn} {goal}", "java", tool=None if mvn != "mvn" else "mvn"))
    for build in ("build.gradle", "build.gradle.kts"):
        if (root / build).is_file():
            text = _read(root / build)
            task = "bootRun" if "org.springframework.boot" in text else "run"
            has_wrapper = (root / ("gradlew.bat" if win else "gradlew")).exists()
            gradle = ("gradlew.bat" if win else "./gradlew") if has_wrapper else "gradle"
            out.append(Candidate(f"{gradle} {task}", f"{gradle} {task}", "java", tool=None if has_wrapper else "gradle"))
            break
    return out


def _make(root: Path, win: bool) -> list[Candidate]:
    for name in ("Makefile", "makefile", "GNUmakefile"):
        if (root / name).is_file():
            targets = re.findall(r"^(run|start|serve|dev|up)\s*:", _read(root / name), flags=re.M)
            return [Candidate(f"make {t}", f"make {t}", "make", tool="make") for t in dict.fromkeys(targets)]
    return []


def _procfile(root: Path, win: bool) -> list[Candidate]:
    if not (root / "Procfile").is_file():
        return []
    m = re.search(r"^web:\s*(.+)$", _read(root / "Procfile"), flags=re.M)
    return [Candidate("Procfile web", m.group(1).strip().replace("$PORT", "{port}"), "procfile", url="http://localhost:{port}/")] if m else []


def _compose(root: Path, win: bool) -> list[Candidate]:
    for name in ("compose.yaml", "compose.yml", "docker-compose.yml", "docker-compose.yaml"):
        if (root / name).is_file():
            return [Candidate("docker compose up", "docker compose up --build", "docker", tool="docker", notes=["Docker Desktop must be running"])]
    return []


def _dockerfile(root: Path, win: bool) -> list[Candidate]:
    if not (root / "Dockerfile").is_file():
        return []
    tag = "repodock-" + re.sub(r"[^a-z0-9_.-]", "-", root.name.lower())
    return [Candidate("docker build and run", f"docker build -t {tag} . && docker run --rm -P {tag}", "docker", tool="docker", notes=["Docker Desktop must be running"])]


def _scripts(root: Path, win: bool) -> list[Candidate]:
    out = []
    names = sorted(p.name for p in root.iterdir() if p.is_file())
    ranked = sorted(names, key=lambda n: not re.match(r"(?i)(start|run|launch|play)", n))
    for name in ranked:
        low = name.lower()
        if win and low.endswith((".bat", ".cmd")):
            out.append(Candidate(f"Run {name}", q(name), "script"))
        elif win and low.endswith(".ps1"):
            out.append(Candidate(f"Run {name}", f"powershell -NoProfile -ExecutionPolicy Bypass -File {q(name)}", "script", tool="powershell"))
        elif not win and low.endswith(".sh") and re.match(r"(?i)(start|run|launch|play|serve)", name):
            out.append(Candidate(f"Run {name}", f"sh {q(name)}", "script", tool="sh"))
    return out[:3]


def _static(root: Path, win: bool) -> list[Candidate]:
    for folder in ("", "public", "docs", "site", "dist", "build", "www"):
        if (root / folder / "index.html").is_file():
            target = folder or "."
            return [Candidate("Static website", f"{{system_python}} -m http.server {{port}} --bind 127.0.0.1 --directory {q(target)}", "static", url="http://localhost:{port}/")]
    return []


# Running ------------------------------------------------------------------

def venv_paths(platform: str | None = None) -> tuple[str, str]:
    """The .venv Python and scripts folder, relative to the repository (commands run there)."""
    if is_windows(platform):
        return r".venv\Scripts\python.exe", r".venv\Scripts"
    return ".venv/bin/python", ".venv/bin"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def expand(command: str, root: Path, port: int | str | None = None, platform: str | None = None, assume_venv: bool = False) -> str:
    venv_python, venv_bin = venv_paths(platform)
    system = q(sys.executable)
    values = {
        "system_python": system,
        "venv_python": venv_python,
        "venv_bin": venv_bin,
        "python": venv_python if (Path(root) / venv_python).exists() or assume_venv else system,
    }
    if "{port}" in command:
        values["port"] = str(port or free_port())
    for key, value in values.items():
        command = command.replace("{" + key + "}", value)
    return command


def missing_tool(candidate: Candidate) -> str | None:
    """Human name of a required program that isn't installed, if any."""
    if candidate.tool and not shutil.which(candidate.tool):
        return TOOL_NAMES.get(candidate.tool, candidate.tool)
    return None
