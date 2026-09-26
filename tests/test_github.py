import unittest

from repodock.github import Target, parse, summarize


class ParseTests(unittest.TestCase):
    def test_repositories(self):
        cases = {
            "https://github.com/octo/tool": ("octo", "tool", None),
            "https://github.com/octo/tool.git": ("octo", "tool", None),
            "http://www.github.com/octo/tool/": ("octo", "tool", None),
            "github.com/octo/tool/tree/dev/sub": ("octo", "tool", "dev/sub"),
            "https://github.com/octo/tool/blob/main/README.md": ("octo", "tool", None),
            "git@github.com:octo/tool.git": ("octo", "tool", None),
            "octo/tool": ("octo", "tool", None),
            "  octo/my.tool_v2  ": ("octo", "my.tool_v2", None),
        }
        for text, (owner, repo, branch) in cases.items():
            with self.subTest(text=text):
                self.assertEqual(parse(text), Target(owner, repo, branch))

    def test_users(self):
        for text in ("https://github.com/octo", "github.com/octo/", "@octo", "octo"):
            with self.subTest(text=text):
                self.assertEqual(parse(text), Target("octo"))

    def test_rejects(self):
        for text in ("", "https://gitlab.com/a/b", "https://github.com/", "not a repo", "a/b/c", "https://evilgithub.com/a/b"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse(text)

    def test_summarize(self):
        s = summarize({"full_name": "o/r", "name": "r", "size": 10, "fork": True})
        self.assertEqual((s["owner"], s["size_kb"], s["fork"], s["default_branch"]), ("o", 10, True, "main"))


if __name__ == "__main__":
    unittest.main()
