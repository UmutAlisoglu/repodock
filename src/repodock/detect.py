"""Guess how to run a repository, and what to install first.

Commands are shell strings the user can edit. They may contain placeholders
that are filled in when the command runs (see ``expand``):

  {python}         the repo's .venv Python if it exists, else the Python running repodock
  {system_python}  the Python running repodock (in the Windows build: Python from PATH)
  {repodock}       repodock itself, e.g. to serve a static site
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
    "java": "Java", "docker": "Docker", "make": "make", "powershell": "PowerShell", "sh": "a POSIX shell", "bash": "bash",
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
    text = _read(path)
    if tomllib is None:
        return _mini_toml(text)
    try:
        return tomllib.loads(text)
    except (ValueError, tomllib.TOMLDecodeError):  # type: ignore[union-attr]
        return {}


def _mini_toml(text: str) -> dict:
    """Enough TOML for Python < 3.11: tables, string values and string arrays."""
    data: dict = {}
    table = data
    lines = iter(text.splitlines())
    for line in lines:
        line = line.split(" #", 1)[0].strip()
        if not line or line.startswith("#"):
            continue
        header = re.fullmatch(r"\[([A-Za-z0-9_.\-\"' ]+)\]", line)
        if header:
            table = data
            for part in (p.strip().strip("\"'") for p in header.group(1).split(".")):
                table = table.setdefault(part, {})
            continue
        m = re.fullmatch(r"([A-Za-z0-9_\-\"'.]+)\s*=\s*(.*)", line)
        if not m:
            continue
        key, value = m.group(1).strip("\"'"), m.group(2).strip()
        if value.startswith("[") and not value.endswith("]"):
            for more in lines:
                value += " " + more.split(" #", 1)[0].strip()
                if value.rstrip().endswith("]"):
                    break
        if value.startswith("["):
            table[key] = [a or b for a, b in re.findall(r"\"((?:[^\"\\]|\\.)*)\"|'([^']*)'", value)]
        elif value[:1] in "\"'":
            table[key] = value[1:].split(value[0], 1)[0]
    return data


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
    # A program or launcher script the project ships, or a Docker setup with several services, beats a guess.
    unique.sort(key=lambda c: 0 if c.kind in ("exe", "launcher") else 1 if c.kind == "docker" and "services" in " ".join(c.notes) else 2)
    for c in unique:
        if c.kind == "launcher":
            c.kind = "script"
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
    has_deps = bool(pkg.get("dependencies") or pkg.get("devDependencies") or pkg.get("workspaces") or (root / "pnpm-workspace.yaml").exists())
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


PY_ENTRIES = ("main.py", "app.py", "run.py", "server.py", "launch.py", "webui.py", "bot.py", "start.py", "gui.py", "__main__.py")
# Python files that are never the way to start a project.
PY_NOT_ENTRY = re.compile(r"(?i)^(setup|conftest|noxfile|fabfile|tasks|test.*|.*_test|download.*|update.*|build.*|install.*|config|settings)\.py$")
# Packages that ``python -m`` shouldn't pick.
PY_NOT_MODULE = {"buildconfig", "scripts", "tools", "docs", "doc", "test", "tests", "examples", "benchmarks", "setup", "build", "ci"}


def _requirements(root: Path) -> Path | None:
    """requirements.txt, or a variant like requirements_versions.txt (not dev, test or docs ones)."""
    if (root / "requirements.txt").is_file():
        return root / "requirements.txt"
    for path in sorted(root.glob("requirements*.txt")):
        if not re.search(r"(?i)(dev|test|doc|docker|lint|ci|build|extra|optional)", path.name):
            return path
    # A requirements/ folder: the file for running it locally.
    for name in ("local.txt", "dev.txt", "development.txt", "base.txt", "common.txt", "requirements.txt", "prod.txt", "production.txt"):
        if (root / "requirements" / name).is_file():
            return root / "requirements" / name
    return None


def _readme_commands(root: Path) -> list[str]:
    """Commands that the README says to run, like "python webui.py" (Python files that exist only)."""
    text = _readme_text(root)
    found = []
    for m in re.finditer(r"(?m)(?:^|[\s`$>])(?:python3?|py(?: -3)?|streamlit run)\s+((?:[\w.-]+/)*[\w.-]+\.py)\b", text):
        entry = m.group(1).lstrip("./")
        helper = re.search(r"(?i)(^|/)(dev|devscripts|scripts?|tools?|tests?|docs?|examples?|benchmarks?|ci)/", entry)
        if (root / entry).is_file() and not helper and not PY_NOT_ENTRY.match(Path(entry).name) and entry not in found:
            found.append(entry)
    return found[:3]


def _readme_text(root: Path) -> str:
    for name in ("README.md", "readme.md", "README.rst", "README.txt", "README"):
        if (root / name).is_file():
            return _read(root / name, 200_000)
    return ""


def _code_lines(text: str) -> list[str]:
    """Lines of a README that are commands: inside ``` blocks, indented blocks, or after a "$ " prompt."""
    lines, fenced = [], False
    for line in text.splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
            continue
        stripped = line.strip()
        if stripped.startswith("$ "):
            lines.append(stripped[2:])
        elif fenced or line.startswith(("    ", "\t", "  ")):
            lines.append(stripped)
    return lines


def _readme_args(root: Path, command: str) -> str | None:
    """Arguments from the README's first example of ``command``, like "play life" for "freegames play life"."""
    for line in _code_lines(_readme_text(root)):
        line = re.split(r"\s+#", line, maxsplit=1)[0].strip()
        if not line.startswith(command + " "):
            continue
        args = line[len(command):].strip()
        # Only a subcommand, like "serve" or "play life": options and file names are too specific.
        if re.fullmatch(r"[a-z][a-z0-9_-]*( [a-z][a-z0-9_-]*)?", args):
            return args
    return None


def _module_with(root: Path, pattern: str) -> tuple[str, str] | None:
    """(module, variable) of a top-level file that creates an app object, e.g. ("main", "app") for app = FastAPI()."""
    files = [root / f"{n}.py" for n in ("main", "app", "server", "api", "asgi", "wsgi")]
    files += sorted(p for p in root.glob("*.py") if p not in files)
    for folder in ("app", "src", "backend/app"):
        files += [root / folder / f"{n}.py" for n in ("main", "app", "server", "api")]
    for path in files:
        if not path.is_file():
            continue
        m = re.search(r"(?m)^(\w+)\s*=\s*" + pattern, _read(path, 100_000))
        if m:
            module = ".".join(path.relative_to(root).with_suffix("").parts)
            return module, m.group(1)
    return None


def _python(root: Path, win: bool) -> list[Candidate]:
    req = _requirements(root)
    pyproject = root / "pyproject.toml"
    setup = root / "setup.py"
    readme = _readme_commands(root)
    entries = list(dict.fromkeys(readme + [e for e in PY_ENTRIES if (root / e).is_file()]))
    manage = (root / "manage.py").is_file()
    if not (req or pyproject.is_file() or setup.is_file() or entries or manage):
        return []
    reqs_text = _read(req).lower() if req else ""
    project = _toml(pyproject) if pyproject.is_file() else {}
    proj = project.get("project") or {}
    poetry = ((project.get("tool") or {}).get("poetry") or {})
    # "pip install -e ." needs something to build with. A pyproject.toml with only a
    # [project] table (common in apps like ComfyUI) isn't meant to be installed.
    installable = bool(setup.is_file() or poetry.get("name") or (proj.get("name") and ("build-system" in project or proj.get("scripts"))))
    all_text = reqs_text + " " + " ".join(proj.get("dependencies") or []).lower() + " " + " ".join((poetry.get("dependencies") or {})).lower()

    def uses(package: str) -> bool:
        return re.search(r"(?m)(^|[\s\"'])" + re.escape(package) + r"(\b|$)", all_text) is not None

    steps = ["{system_python} -m venv .venv"]
    if req:
        steps.append("{venv_python} -m pip install -r " + q(req.relative_to(root).as_posix()))
    if installable:
        steps.append("{venv_python} -m pip install -e .")
    elif not req and proj.get("dependencies"):
        # Dependencies listed in pyproject.toml of a project that can't be installed itself.
        steps.append("{venv_python} -m pip install " + " ".join(f'"{d}"' for d in proj["dependencies"][:60] if '"' not in d))
    deps = " && ".join(steps) if len(steps) > 1 else None
    common = dict(kind="python", deps=deps, deps_marker=".venv" if deps else None)
    with_install = {**common, "deps": deps or "{system_python} -m venv .venv && {venv_python} -m pip install -e .", "deps_marker": ".venv"}

    out = []
    scripts = proj.get("scripts") or poetry.get("scripts") or {}
    if installable:
        for name in list(scripts)[:2]:
            # Command-line tools often need arguments; use the README's example if it has one.
            args = _readme_args(root, name)
            label = f"{name} {args}" if args else f"{name} (installed command)"
            out.append(Candidate(label, f'"{{venv_bin}}{os.sep}{name}"' + (f" {args}" if args else ""), **with_install))
    if manage:
        out.append(Candidate("Django dev server", "{python} manage.py runserver {port}", url="http://localhost:{port}/", **common))
    if not entries and uses("streamlit"):
        entries = [p.name for p in sorted(root.glob("*.py")) if re.search(r"(?m)^\s*import streamlit|^\s*from streamlit", _read(p, 60_000))][:2]
    for entry in entries:
        src = _read(root / entry, 60_000)
        if uses("streamlit") and "streamlit" in src:
            out.append(Candidate(f"streamlit run {entry}", f"{{python}} -m streamlit run {q(entry)} --server.port {{port}}", url="http://localhost:{port}/", **common))
        else:
            out.append(Candidate(f"python {entry}", f"{{python}} {q(entry)}", **common))
    if uses("fastapi") and uses("uvicorn"):
        found = _module_with(root, r"FastAPI\(")
        if found:
            target = f"{found[0]}:{found[1]}"
            out.append(Candidate(f"uvicorn {target}", f"{{python}} -m uvicorn {target} --port {{port}}", url="http://localhost:{port}/docs", **common))
    if uses("flask") and not manage:
        env = _read(root / ".flaskenv")
        if "FLASK_APP" in env or any((root / n).is_file() for n in ("app.py", "wsgi.py")) or (root / "app" / "__init__.py").is_file():
            out.append(Candidate("flask run", "{python} -m flask run --port {port}", url="http://localhost:{port}/", **common))
    if not out:
        # A package with __main__.py: python -m package
        for main in _find(root, "__main__.py", depth=3):
            pkg = main.parent
            if pkg == root or pkg.name in PY_NOT_MODULE or any(p in PY_NOT_MODULE for p in pkg.relative_to(root).parts):
                continue
            module = ".".join(pkg.relative_to(root / "src" if (root / "src") in pkg.parents else root).parts)
            out.append(Candidate(f"python -m {module}", f"{{python}} -m {module}", **(with_install if installable or not deps else common)))
            break
    if not out:
        # Last resort: top-level scripts with an `if __name__ == "__main__":` block,
        # preferring one named after the project.
        mains = [p for p in sorted(root.glob("*.py")) if not PY_NOT_ENTRY.match(p.name) and re.search(r"(?m)^if __name__ ==", _read(p, 200_000))]
        slug = re.sub(r"[^a-z0-9]", "", root.name.lower().split("_", 1)[-1])
        mains.sort(key=lambda p: re.sub(r"[^a-z0-9]", "", p.stem.lower()) not in slug)
        for p in mains[:2]:
            out.append(Candidate(f"python {p.name}", f"{{python}} {q(p.name)}", **common))
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
    if not m:
        return []
    command = m.group(1).strip()
    # Procfiles are written for Linux servers; gunicorn and shell syntax don't work on Windows.
    if win and re.search(r"gunicorn|uwsgi|;|\$\{|\bexec\b", command):
        return []
    return [Candidate("Procfile web", command.replace("${PORT}", "{port}").replace("$PORT", "{port}"), "procfile", url="http://localhost:{port}/")]


COMPOSE_NAMES = ("compose.yaml", "compose.yml", "docker-compose.yml", "docker-compose.yaml")


def _compose_services(text: str) -> int:
    block = re.search(r"(?ms)^services:\s*\n(.*?)(?=^\S|\Z)", text)
    if not block:
        return 0
    indents = re.findall(r"(?m)^( +)[\w.-]+:\s*$", block.group(1))
    return indents.count(min(indents, key=len)) if indents else 0


def _compose(root: Path, win: bool) -> list[Candidate]:
    for folder in ("", "docker", "deploy", "deployment"):
        for name in COMPOSE_NAMES:
            path = root / folder / name
            if not path.is_file():
                continue
            notes = ["Docker Desktop must be running"]
            services = _compose_services(_read(path))
            if services >= 3:
                notes.append(f"starts {services} services together")
            example = next((n for n in ("example.env", ".env.example", ".env.sample") if (path.parent / n).is_file()), None)
            if example and not (path.parent / ".env").is_file():
                notes.append(f"may need a .env file first: copy {folder + '/' if folder else ''}{example} to .env")
            if folder:
                command = f"docker compose -f {folder}/{name} up --build"
            else:
                command = "docker compose up --build"
            return [Candidate("docker compose up", command, "docker", tool="docker", notes=notes)]
    return []


def _dockerfile(root: Path, win: bool) -> list[Candidate]:
    if not (root / "Dockerfile").is_file():
        return []
    tag = "repodock-" + re.sub(r"[^a-z0-9_.-]", "-", root.name.lower())
    return [Candidate("docker build and run", f"docker build -t {tag} . && docker run --rm -P {tag}", "docker", tool="docker", notes=["Docker Desktop must be running"])]


# Launcher scripts that projects ship for exactly this purpose, best first.
LAUNCHERS_WIN = ("start_windows.bat", "webui-user.bat", "start.bat", "run.bat", "launch.bat", "quickstart.bat", "start.cmd", "run.cmd")
LAUNCHERS_POSIX = ("start_linux.sh", "start_macos.sh", "webui.sh", "start.sh", "run.sh", "launch.sh", "quickstart.sh")
# Helper scripts that aren't how you start a project.
NOT_LAUNCHER = re.compile(r"(?i)^(cmd_|update|uninstall|install|setup|make\.bat|build|clean|test|lint|format|release|deploy|publish)")


def _scripts(root: Path, win: bool) -> list[Candidate]:
    out = []
    names = sorted(p.name for p in root.iterdir() if p.is_file())
    lower = {n.lower(): n for n in names}
    launchers = LAUNCHERS_WIN if win else tuple(n for n in LAUNCHERS_POSIX if ("macos" in n) == (sys.platform == "darwin") or "_" not in n)
    mine = "windows" if win else "macos" if sys.platform == "darwin" else "linux"
    os_words = {"windows": "windows", "win": "windows", "linux": "linux", "macos": "macos", "mac": "macos", "osx": "macos"}

    def shell(name: str) -> str:
        return "bash" if "bash" in _read(root / name, 200).split("\n", 1)[0] else "sh"

    for launcher in launchers:
        name = lower.get(launcher)
        if name:
            command = q(name) if win else f"{shell(name)} {q(name)}"
            out.append(Candidate(f"Run {name}", command, "launcher", tool=None if win else shell(name), notes=["the project's own start script"]))
    ranked = sorted(names, key=lambda n: not re.match(r"(?i)(start|run|launch|play|webui)", n))
    for name in ranked:
        low = name.lower()
        if low in launchers or NOT_LAUNCHER.match(name):
            continue
        if any(os_words.get(w, mine) != mine for w in re.split(r"[^a-z]+", low)):
            continue  # e.g. start_macos.sh on Linux
        if win and low.endswith((".bat", ".cmd")):
            out.append(Candidate(f"Run {name}", q(name), "script"))
        elif win and low.endswith(".ps1"):
            out.append(Candidate(f"Run {name}", f"powershell -NoProfile -ExecutionPolicy Bypass -File {q(name)}", "script", tool="powershell"))
        elif not win and low.endswith(".sh") and re.match(r"(?i)(start|run|launch|play|serve)", name):
            out.append(Candidate(f"Run {name}", f"{shell(name)} {q(name)}", "script", tool=shell(name)))
    return out[:3]


def _static(root: Path, win: bool) -> list[Candidate]:
    for folder in ("", "public", "docs", "site", "dist", "build", "www"):
        if (root / folder / "index.html").is_file():
            target = folder or "."
            return [Candidate("Static website", f"{{repodock}} static {q(target)} --port {{port}}", "static", url="http://localhost:{port}/")]
    # A collection of small sites, one per folder: serve them all with a list of folders.
    sites = [p for p in root.iterdir() if p.is_dir() and not p.name.startswith(".") and p.name not in SKIP and (p / "index.html").is_file()]
    if len(sites) >= 2:
        return [Candidate("Static websites", "{repodock} static . --port {port}", "static", url="http://localhost:{port}/",
                          notes=[f"{len(sites)} small sites, one per folder: pick one from the list"])]
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


def frozen() -> bool:
    """True in the standalone Windows build, where sys.executable is repodock.exe, not Python."""
    return bool(getattr(sys, "frozen", False))


def system_python() -> str | None:
    """A Python to create project virtual environments with, or None if there is none."""
    if not frozen():
        return sys.executable
    for name in ("python", "python3"):
        path = shutil.which(name)
        # Windows ships a "python.exe" stub in WindowsApps that only opens the Microsoft Store.
        if path and "windowsapps" not in path.lower():
            return path
    launcher = shutil.which("py")
    return f"{launcher} -3" if launcher else None


def repodock_command() -> str:
    """How to start repodock itself (used to serve static sites)."""
    if frozen():
        # The Windows build has a windowed repodock.exe and a console repodock-cli.exe next to it.
        cli = Path(sys.executable).with_name("repodock-cli.exe")
        return q(str(cli if cli.exists() else sys.executable))
    return f"{q(sys.executable)} -m repodock"


def expand(command: str, root: Path, port: int | str | None = None, platform: str | None = None, assume_venv: bool = False) -> str:
    venv_python, venv_bin = venv_paths(platform)
    found = system_python()
    system = (q(found) if found and not found.endswith(" -3") else found) or "python"
    values = {
        "repodock": repodock_command(),
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
    if candidate.kind == "python" and system_python() is None:
        return "Python"
    if candidate.tool and not shutil.which(candidate.tool):
        return TOOL_NAMES.get(candidate.tool, candidate.tool)
    return None
