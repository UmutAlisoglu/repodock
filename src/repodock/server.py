"""The local web server behind the dashboard.

repodock can run commands, so the API only answers requests that are clearly
from its own page: the Host header must be this machine (blocks DNS
rebinding) and every POST must carry an X-Repodock header, which other
websites can't add to a cross-site request without a CORS preflight that
this server never approves.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.parse
import socketserver
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import __version__
from .app import Dock, DockError
from .page import FAVICON, PAGE

LOCAL_HOSTS = {"127.0.0.1", "localhost", "[::1]"}
MAX_BODY = 5_000_000


def make_handler(dock: Dock, verbose: bool = False) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "repodock"

        def host_ok(self) -> bool:
            host = (self.headers.get("Host") or "").lower()
            name = host.rsplit(":", 1)[0] if not host.endswith("]") else host
            return name in LOCAL_HOSTS

        def do_GET(self) -> None:  # noqa: N802
            if not self.host_ok():
                return self.send(403, {"error": "open repodock through localhost"})
            url = urllib.parse.urlsplit(self.path)
            query = urllib.parse.parse_qs(url.query)
            if url.path in ("/", "/index.html"):
                self.send_raw(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
            elif url.path == "/favicon.svg":
                self.send_raw(200, FAVICON.encode("utf-8"), "image/svg+xml")
            elif url.path == "/api/state":
                self.send(200, dock.state())
            elif url.path == "/api/log":
                key = (query.get("key") or [""])[0]
                after = int((query.get("after") or ["0"])[0] or 0)
                job = dock.runner.job(key)
                lines = job.output(after) if job else []
                self.send(200, {"lines": lines, "job": job.to_dict() if job else None})
            elif url.path == "/api/ping":
                self.send(200, {"app": "repodock", "version": __version__, "pid": os.getpid()})
            elif url.path == "/api/export":
                body = json.dumps(dock.export(), indent=2).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Disposition", 'attachment; filename="repodock-library.json"')
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send(404, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            if not self.host_ok() or self.headers.get("X-Repodock") != "1":
                return self.send(403, {"error": "forbidden"})
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY:
                return self.send(413, {"error": "request too large"})
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
                if not isinstance(body, dict):
                    raise ValueError
            except ValueError:
                return self.send(400, {"error": "invalid JSON"})
            route = urllib.parse.urlsplit(self.path).path
            action = ACTIONS.get(route)
            if not action:
                return self.send(404, {"error": "not found"})
            try:
                result = action(dock, body)
            except (DockError, RuntimeError) as exc:
                return self.send(400, {"error": str(exc)})
            except (KeyError, TypeError, ValueError, AttributeError) as exc:
                return self.send(400, {"error": f"bad request: {exc}"})
            except OSError as exc:
                return self.send(500, {"error": str(exc)})
            self.send(200, result if isinstance(result, dict) else {"ok": True})

        def send(self, code: int, data: dict) -> None:
            self.send_raw(code, json.dumps(data).encode("utf-8"), "application/json")

        def send_raw(self, code: int, body: bytes, kind: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
                             "img-src 'self' data: https://github.com https://avatars.githubusercontent.com; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt: str, *args) -> None:
            if verbose:
                sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    return Handler


def _show(d: Dock, _b: dict) -> dict:
    if d.show_window:
        d.show_window()
        return {"shown": True}
    return {"shown": False}


def _quit(d: Dock, _b: dict) -> dict:
    if not d.quit:
        raise DockError("close the terminal window (or press Ctrl+C) to quit repodock")
    d.quit()
    return {"quitting": True}


ACTIONS = {
    "/api/add": lambda d, b: d.add(b["input"]),
    "/api/add-many": lambda d, b: d.add_many(list(b["repos"])),
    "/api/search": lambda d, b: d.search(str(b["query"])),
    "/api/run": lambda d, b: d.run(b["key"], b.get("command"), bool(b.get("confirmed")), b.get("install"), b.get("action")),
    "/api/install": lambda d, b: d.install(b["key"]),
    "/api/stop": lambda d, b: {"stopped": d.stop(b["key"])},
    "/api/stop-all": lambda d, b: {"stopped": d.stop_all()},
    "/api/command": lambda d, b: d.set_command(b["key"], b.get("command")),
    "/api/configure": lambda d, b: (d.configure(b["key"], **b["fields"]), None)[1],
    "/api/env": lambda d, b: d.env(b["key"]),
    "/api/set-env": lambda d, b: d.set_env(b["key"], list(b["vars"])),
    "/api/update": lambda d, b: d.update(b["key"]),
    "/api/update-all": lambda d, b: d.update_all(),
    "/api/check-updates": lambda d, b: d.check_updates(b.get("keys")),
    "/api/delete": lambda d, b: d.delete(b["key"], bool(b.get("files", True))),
    "/api/open": lambda d, b: d.open_folder(b["key"], b.get("which", "project")),
    "/api/open-url": lambda d, b: d.open_url(str(b["url"])),
    "/api/redetect": lambda d, b: (d.candidates(b["key"], refresh=True), None)[1],
    "/api/releases": lambda d, b: {"releases": d.releases(b["key"])},
    "/api/download-release": lambda d, b: d.download_release(b["key"], str(b["tag"]), str(b["asset"])),
    "/api/logs": lambda d, b: {"logs": d.logs(b["key"])},
    "/api/log-file": lambda d, b: {"text": d.log_file(b["key"], str(b["name"]))},
    "/api/cleanable": lambda d, b: {"items": d.cleanable(b["key"])},
    "/api/clean": lambda d, b: d.clean(b["key"], list(b["names"])),
    "/api/install-tool": lambda d, b: d.install_tool(str(b["tool"])),
    "/api/settings": lambda d, b: {"settings": d.set_settings(dict(b["changes"]))},
    "/api/import": lambda d, b: d.import_(b["library"]),
    "/api/show": _show,
    "/api/open-link": lambda d, b: {**d.open_link(str(b.get("link", ""))), "shown": bool(d.show_window)},
    "/api/link-done": lambda d, b: (d.link_done(int(b.get("id", 0))), None)[1],
    "/api/lookup": lambda d, b: d.lookup(str(b["repo"])),
    "/api/quit": _quit,
}


class LocalServer(ThreadingHTTPServer):
    """A threaded HTTP server on 127.0.0.1.

    HTTPServer.server_bind looks up the host's full name, which can hang for
    half a minute on macOS; a local server doesn't need it.
    """

    daemon_threads = True

    def server_bind(self):
        socketserver.TCPServer.server_bind(self)
        self.server_name = "localhost"
        self.server_port = self.server_address[1]


def make_server(dock: Dock, port: int, verbose: bool = False) -> ThreadingHTTPServer:
    server = LocalServer(("127.0.0.1", port), make_handler(dock, verbose))
    server.daemon_threads = True
    return server
