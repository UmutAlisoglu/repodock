import http.client
import json
import threading
import unittest

from repodock.app import Dock
from repodock.github import GitHub
from repodock.server import make_server
from repodock.store import Store

from helpers import FakeGitHub, TempDir, make_remote, repo_json, wait_for


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TempDir()
        self.gh = FakeGitHub()
        self.gh.repos["octo/app"] = repo_json("octo/app")
        make_remote(self.tmp.path / "remotes", "octo/app", {"main.py": "print('served')"})
        self.dock = Dock(Store(self.tmp.path / "dock"), GitHub(None, self.gh.url), git_base=str(self.tmp.path / "remotes"))
        self.server = make_server(self.dock, 0)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.dock.runner.stop_all()
        self.server.shutdown()
        self.server.server_close()
        self.gh.close()
        self.tmp.cleanup()

    def call(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        hdrs = {"Host": f"localhost:{self.port}"}
        if body is not None:
            hdrs.update({"Content-Type": "application/json", "X-Repodock": "1"})
        hdrs.update(headers or {})
        conn.request(method, path, json.dumps(body) if body is not None else None, hdrs)
        resp = conn.getresponse()
        data = resp.read()
        conn.close()
        kind = resp.getheader("Content-Type", "")
        return resp.status, json.loads(data) if "json" in kind else data.decode()

    def test_page_and_state(self):
        status, page = self.call("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("repodock", page)
        status, state = self.call("GET", "/api/state")
        self.assertEqual((status, state["repos"]), (200, []))

    def test_add_run_and_log_through_the_api(self):
        status, res = self.call("POST", "/api/add", {"input": "octo/app"})
        self.assertEqual((status, res["key"]), (200, "octo/app"))
        wait_for(lambda: self.call("GET", "/api/state")[1]["repos"][0]["status"] == "ready")
        status, res = self.call("POST", "/api/run", {"key": "octo/app"})
        self.assertIn("confirm", res)
        status, res = self.call("POST", "/api/run", {"key": "octo/app", "confirmed": True})
        self.assertEqual(res, {"started": "run"})
        wait_for(lambda: not self.call("GET", "/api/log?key=octo/app")[1]["job"]["running"])
        lines = [line for _, line in self.call("GET", "/api/log?key=octo/app&after=0")[1]["lines"]]
        self.assertIn("served", lines)
        last = self.call("GET", "/api/log?key=octo/app")[1]["lines"][-1][0]
        self.assertEqual(self.call("GET", f"/api/log?key=octo/app&after={last}")[1]["lines"], [])

    def test_errors_are_json(self):
        status, res = self.call("POST", "/api/add", {"input": "not a link"})
        self.assertEqual(status, 400)
        self.assertIn("not a GitHub link", res["error"])
        status, res = self.call("POST", "/api/run", {"key": "nobody/here"})
        self.assertEqual(status, 400)
        status, _ = self.call("POST", "/api/nope", {})
        self.assertEqual(status, 404)

    def test_other_websites_cannot_use_the_api(self):
        # No custom header: a plain cross-site form post.
        status, _ = self.call("POST", "/api/add", None, {"Content-Type": "text/plain"})
        self.assertEqual(status, 403)
        # DNS rebinding: right port, wrong host name.
        status, _ = self.call("GET", "/api/state", None, {"Host": f"evil.example:{self.port}"})
        self.assertEqual(status, 403)
        status, _ = self.call("POST", "/api/add", {"input": "octo/app"}, {"Host": "evil.example"})
        self.assertEqual(status, 403)
        status, _ = self.call("GET", "/api/state", None, {"Host": f"127.0.0.1:{self.port}"})
        self.assertEqual(status, 200)

    def test_new_routes(self):
        status, ping = self.call("GET", "/api/ping")
        self.assertEqual((status, ping["app"]), (200, "repodock"))
        status, res = self.call("POST", "/api/settings", {"changes": {"theme": "dark"}})
        self.assertEqual(res["settings"]["theme"], "dark")
        status, res = self.call("POST", "/api/settings", {"changes": {"theme": 5}})
        self.assertEqual(status, 400)
        self.call("POST", "/api/add", {"input": "octo/app"})
        wait_for(lambda: self.call("GET", "/api/state")[1]["repos"][0]["status"] == "ready")
        status, _ = self.call("POST", "/api/configure", {"key": "octo/app", "fields": {"tags": ["x"]}})
        self.assertEqual(status, 200)
        self.assertEqual(self.call("GET", "/api/state")[1]["repos"][0]["tags"], ["x"])
        status, res = self.call("POST", "/api/configure", {"key": "octo/app", "fields": {"port": "abc"}})
        self.assertEqual(status, 400)
        status, res = self.call("POST", "/api/set-env", {"key": "octo/app", "vars": [["A", "1"]]})
        self.assertEqual(self.call("POST", "/api/env", {"key": "octo/app"})[1]["vars"], [["A", "1"]])
        status, library = self.call("GET", "/api/export")
        self.assertEqual(library["repos"][0]["full_name"], "octo/app")
        status, res = self.call("POST", "/api/releases", {"key": "octo/app"})
        self.assertEqual(res, {"releases": []})
        status, res = self.call("POST", "/api/quit", {})
        self.assertEqual(status, 400)  # only the app window can quit itself
        self.assertEqual(self.call("POST", "/api/show", {})[1], {"shown": False})
        status, res = self.call("POST", "/api/open-url", {"url": "file:///etc/passwd"})
        self.assertEqual(status, 400)
        status, res = self.call("POST", "/api/stop-all", {})
        self.assertEqual(res, {"stopped": 0})


if __name__ == "__main__":
    unittest.main()
