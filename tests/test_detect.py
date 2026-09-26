import json
import unittest
from pathlib import Path

from repodock.detect import detect, expand, q

from helpers import TempDir, write_files


class DetectTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TempDir()
        self.n = 0

    def tearDown(self):
        self.tmp.cleanup()

    def repo(self, files: dict[str, str]) -> Path:
        self.n += 1
        return write_files(self.tmp.path / f"r{self.n}", files)

    def first(self, files, platform="linux"):
        found = detect(self.repo(files), platform)
        self.assertTrue(found, "nothing detected")
        return found[0]

    def test_node_scripts_and_package_manager(self):
        pkg = json.dumps({"scripts": {"start": "node s.js", "dev": "vite"}, "dependencies": {"x": "1"}})
        c = self.first({"package.json": pkg})
        self.assertEqual((c.command, c.deps, c.deps_marker), ("npm run dev", "npm install", "node_modules"))
        c = self.first({"package.json": pkg, "package-lock.json": "{}"})
        self.assertEqual(c.deps, "npm ci")
        c = self.first({"package.json": pkg, "pnpm-lock.yaml": ""})
        self.assertEqual((c.command, c.deps), ("pnpm run dev", "pnpm install"))
        c = self.first({"package.json": json.dumps({"scripts": {"start": "node s.js"}})})
        self.assertEqual((c.command, c.deps), ("npm start", None))

    def test_node_without_scripts(self):
        c = self.first({"package.json": json.dumps({"main": "lib/app.js"}), "lib/app.js": ""})
        self.assertEqual(c.command, "node lib/app.js")

    def test_python_entry_with_requirements(self):
        c = self.first({"requirements.txt": "requests\n", "main.py": "print(1)"})
        self.assertEqual(c.command, "{python} main.py")
        self.assertIn("-m venv .venv", c.deps)
        self.assertIn("pip install -r requirements.txt", c.deps)
        self.assertEqual(c.deps_marker, ".venv")

    def test_python_without_dependencies(self):
        c = self.first({"app.py": "print(1)"})
        self.assertEqual((c.command, c.deps), ("{python} app.py", None))

    def test_pyproject_scripts(self):
        c = self.first({"pyproject.toml": '[project]\nname = "tool"\n[project.scripts]\ntool = "tool.cli:main"\n'})
        self.assertTrue(c.command.startswith('"{venv_bin}'))
        self.assertTrue(c.command.endswith('tool"'))
        self.assertIn("pip install -e .", c.deps)

    def test_package_main_module(self):
        c = self.first({"setup.py": "", "src/cool/__init__.py": "", "src/cool/__main__.py": ""})
        self.assertEqual(c.command, "{python} -m cool")

    def test_django_and_streamlit(self):
        c = self.first({"manage.py": "", "requirements.txt": "django"})
        self.assertEqual(c.command, "{python} manage.py runserver {port}")
        self.assertEqual(c.url, "http://localhost:{port}/")
        c = self.first({"app.py": "import streamlit as st", "requirements.txt": "streamlit"})
        self.assertIn("-m streamlit run app.py", c.command)

    def test_compiled_languages(self):
        self.assertEqual(self.first({"go.mod": "module x", "main.go": "package main"}).command, "go run .")
        self.assertEqual(self.first({"go.mod": "module x", "cmd/srv/main.go": "package main"}).command, "go run ./cmd/srv")
        self.assertEqual(self.first({"Cargo.toml": "[package]"}).command, "cargo run --release")
        c = self.first({"App/App.csproj": "<OutputType>Exe</OutputType>", "App.Tests/App.Tests.csproj": ""})
        self.assertIn("dotnet run --project", c.command)
        self.assertIn("App.csproj", c.command)
        self.assertNotIn("Tests", c.command)

    def test_java(self):
        self.assertEqual(self.first({"pom.xml": "<artifactId>spring-boot</artifactId>"}).command, "mvn spring-boot:run")
        self.assertEqual(self.first({"pom.xml": "", "mvnw": ""}).command, "./mvnw compile exec:java")
        self.assertEqual(self.first({"build.gradle": "", "gradlew": ""}).command, "./gradlew run")
        self.assertEqual(self.first({"build.gradle": "", "gradlew.bat": ""}, platform="win32").command, "gradlew.bat run")

    def test_make_procfile_docker(self):
        self.assertEqual(self.first({"Makefile": "build:\n\tx\nrun: build\n\tx\n"}).command, "make run")
        self.assertEqual(self.first({"Procfile": "web: gunicorn app -b :$PORT\n"}).command, "gunicorn app -b :{port}")
        self.assertEqual(self.first({"docker-compose.yml": ""}).command, "docker compose up --build")
        self.assertIn("docker build -t repodock-", self.first({"Dockerfile": "FROM x"}).command)

    def test_windows_programs_and_scripts(self):
        c = self.first({"Game.exe": "", "unins000.exe": "", "start.bat": ""}, platform="win32")
        self.assertEqual(c.command, "Game.exe")
        found = [c.command for c in detect(self.repo({"run.ps1": "", "setup.sh": ""}), "win32")]
        self.assertIn("powershell -NoProfile -ExecutionPolicy Bypass -File run.ps1", found)
        self.assertFalse(any("setup.sh" in f for f in found))
        # .exe files mean nothing on Linux or macOS
        self.assertEqual(detect(self.repo({"Game.exe": ""}), "linux"), [])
        self.assertEqual(self.first({"start.sh": ""}).command, "sh start.sh")

    def test_static_site(self):
        c = self.first({"docs/index.html": "<h1>hi</h1>"})
        self.assertIn("-m http.server {port} --bind 127.0.0.1 --directory docs", c.command)

    def test_order_prefers_the_app_over_docker(self):
        found = detect(self.repo({"package.json": json.dumps({"scripts": {"dev": "vite"}}), "Dockerfile": "", "index.html": ""}), "linux")
        self.assertEqual([c.kind for c in found], ["node", "docker", "static"])

    def test_nothing(self):
        self.assertEqual(detect(self.repo({"README.md": "# hi"})), [])


class ExpandTests(unittest.TestCase):
    def test_placeholders(self):
        tmp = TempDir()
        try:
            root = tmp.path
            out = expand("{python} a.py --port {port}", root, 1234, "linux")
            self.assertTrue(out.endswith("a.py --port 1234"))
            self.assertNotIn(".venv", out)
            (root / ".venv/bin").mkdir(parents=True)
            (root / ".venv/bin/python").write_text("")
            self.assertEqual(expand("{python} a.py", root, platform="linux"), ".venv/bin/python a.py")
            self.assertEqual(expand("{venv_python} -m pip", root, platform="win32"), r".venv\Scripts\python.exe -m pip")
            self.assertRegex(expand("x {port}", root), r"^x \d+$")
        finally:
            tmp.cleanup()

    def test_quote(self):
        self.assertEqual(q("plain.exe"), "plain.exe")
        self.assertEqual(q("My Game.exe"), '"My Game.exe"')


if __name__ == "__main__":
    unittest.main()
