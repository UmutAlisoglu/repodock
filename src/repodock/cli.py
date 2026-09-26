"""Command line interface for repodock."""

from __future__ import annotations

import argparse
import os
import signal
import sys
import time
import webbrowser
from pathlib import Path

from . import __version__
from .app import Dock, DockError
from .detect import detect, expand, missing_tool
from .github import API, GitHub, find_token
from .store import Store, default_root

EXIT_OK = 0
EXIT_ERROR = 2


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="repodock", description="Paste a GitHub link, download the repo and run it from a local dashboard.")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument("--dir", help="where repositories are kept (default: $REPODOCK_DIR or ~/repodock)")
    sub = p.add_subparsers(dest="command", metavar="COMMAND")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--dir", default=argparse.SUPPRESS, help=argparse.SUPPRESS)  # also accepted after the command

    serve = sub.add_parser("serve", parents=[common], help="start the dashboard (the default)")
    _serve_args(serve)

    add = sub.add_parser("add", parents=[common], help="download a repository (or pick from a user's) without the dashboard")
    add.add_argument("link", help="GitHub link, owner/repo or username")
    add.add_argument("--all", action="store_true", help="for a username: add all their repositories except forks and archived ones")

    sub.add_parser("list", parents=[common], help="list downloaded repositories")

    det = sub.add_parser("detect", parents=[common], help="show how repodock would run a folder")
    det.add_argument("path", nargs="?", default=".")

    # Used by the "Static website" run command, so it works without a separate Python.
    static = sub.add_parser("static")
    static.add_argument("folder")
    static.add_argument("--port", type=int, default=8000)
    _serve_args(p)
    return p


def _serve_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--port", type=int, default=int(os.environ.get("REPODOCK_PORT", "8766")), help="port (default: 8766)")
    p.add_argument("--no-open", action="store_true", help="don't open the browser")
    p.add_argument("-v", "--verbose", action="store_true", help="log requests")


def make_dock(args, token: str | None = None) -> Dock:
    root = Path(args.dir).expanduser() if args.dir else default_root()
    token = token if token is not None else find_token()
    gh = GitHub(token, os.environ.get("REPODOCK_API", API))
    return Dock(Store(root), gh, me=os.environ.get("REPODOCK_ME") or gh.viewer(),
                git_base=os.environ.get("REPODOCK_GIT_BASE", "https://github.com"))


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    command = args.command or "serve"
    try:
        if command == "detect":
            return cmd_detect(args)
        if command == "static":
            return cmd_static(args)
        dock = make_dock(args)
        if command == "add":
            return cmd_add(dock, args)
        if command == "list":
            return cmd_list(dock)
        return cmd_serve(dock, args)
    except DockError as exc:
        print(f"repodock: {exc}", file=sys.stderr)
        return EXIT_ERROR
    except OSError as exc:
        print(f"repodock: {exc}", file=sys.stderr)
        return EXIT_ERROR


def cmd_serve(dock: Dock, args) -> int:
    from .server import make_server

    try:
        server = make_server(dock, args.port, args.verbose)
    except OSError as exc:
        print(f"repodock: cannot use port {args.port} ({exc.strerror or exc}). Is repodock already running? Try --port.", file=sys.stderr)
        return EXIT_ERROR
    url = f"http://localhost:{server.server_address[1]}/"
    print(f"repodock is running at {url}  (Ctrl+C to stop)\nRepositories are kept in {dock.store.root}", file=sys.stderr)
    if not dock.use_git:
        print("Git isn't installed; repositories will be downloaded as zip files.", file=sys.stderr)
    if not args.no_open:
        webbrowser.open(url)

    def on_term(_sig, _frame):  # stop running projects when repodock itself is stopped
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, on_term)
    if hasattr(signal, "SIGBREAK"):  # Windows: Ctrl+Break, and closing the console window
        signal.signal(signal.SIGBREAK, on_term)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping running projects...", file=sys.stderr)
    finally:
        dock.runner.stop_all()
        server.server_close()
    return EXIT_OK


def _wait(dock: Dock, keys: list[str]) -> bool:
    shown: dict[str, int] = {}
    while True:
        busy = False
        for key in keys:
            job = dock.runner.job(key)
            if not job:
                continue
            for seq, line in job.output(shown.get(key, 0)):
                shown[key] = seq
                print(f"[{key}] {line}" if len(keys) > 1 else line)
            busy = busy or job.running
        if not busy:
            return all(not (dock.runner.job(k) and dock.runner.job(k).error) for k in keys)
        time.sleep(0.2)


def cmd_add(dock: Dock, args) -> int:
    result = dock.add(args.link)
    if result["kind"] == "user":
        repos = result["repos"]
        if not args.all:
            print(f"{result['owner']} has {len(repos)} public repositories:")
            for r in repos:
                tags = ", ".join(t for t, on in (("fork", r["fork"]), ("archived", r["archived"]), ("added", r["present"])) if on)
                print(f"  {r['full_name']:<40} {r['size_kb'] / 1024:6.1f} MB  {tags}")
            print("Add one with `repodock add owner/repo`, or all of them with --all.")
            return EXIT_OK
        names = [r["full_name"] for r in repos if r["suggested"]]
        out = dock.add_many(names)
        for name, error in out["errors"].items():
            print(f"{name}: {error}", file=sys.stderr)
        ok = _wait(dock, out["added"])
    else:
        ok = _wait(dock, [result["key"]])
    print(f"Done. Run `repodock` to open the dashboard." if ok else "Some downloads failed.")
    return EXIT_OK if ok else EXIT_ERROR


def cmd_list(dock: Dock) -> int:
    repos = dock.state()["repos"]
    if not repos:
        print(f"No repositories yet in {dock.store.root}. Add one: repodock add owner/repo")
    for r in repos:
        cmd = r.get("command") or "(no run command found)"
        print(f"{r['key']:<40} {r.get('status', ''):<8} {cmd}")
    return EXIT_OK


def cmd_static(args) -> int:
    import functools
    from http.server import SimpleHTTPRequestHandler

    from .server import LocalServer

    folder = Path(args.folder)
    if not folder.is_dir():
        print(f"repodock: {folder} is not a folder", file=sys.stderr)
        return EXIT_ERROR
    server = LocalServer(("127.0.0.1", args.port), functools.partial(SimpleHTTPRequestHandler, directory=str(folder)))
    print(f"Serving {folder} at http://localhost:{server.server_address[1]}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return EXIT_OK


def cmd_detect(args) -> int:
    root = Path(args.path)
    if not root.is_dir():
        print(f"repodock: {root} is not a folder", file=sys.stderr)
        return EXIT_ERROR
    found = detect(root)
    if not found:
        print("No run command found. Check the README.")
        return EXIT_OK
    for i, c in enumerate(found):
        mark = "*" if i == 0 else " "
        print(f"{mark} {c.label}\n    run:     {expand(c.command, root, 8000)}")
        if c.deps:
            print(f"    install: {expand(c.deps, root)}")
        tool = missing_tool(c)
        if tool:
            print(f"    needs {tool}, which isn't installed")
        for note in c.notes:
            print(f"    note: {note}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
