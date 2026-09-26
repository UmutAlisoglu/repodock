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


if __name__ == "__main__":
    unittest.main()
