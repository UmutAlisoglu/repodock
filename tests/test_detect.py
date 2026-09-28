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
        self.assertEqual(c.command, "{repodock} static docs --port {port}")

    def test_order_prefers_the_app_over_docker(self):
        found = detect(self.repo({"package.json": json.dumps({"scripts": {"dev": "vite"}}), "Dockerfile": "", "index.html": ""}), "linux")
        self.assertEqual([c.kind for c in found], ["node", "docker", "static"])

    # Found by trying popular repositories -------------------------------------------

    def test_python_apps_without_a_standard_entry(self):
        c = self.first({"requirements.txt": "streamlit\npandas\n", "streamlit_app.py": "import streamlit as st\n"})
        self.assertEqual(c.command, "{python} -m streamlit run streamlit_app.py --server.port {port}")
        c = self.first({"requirements.txt": "flask\npython-dotenv\n", ".flaskenv": "FLASK_APP=blog.py\n", "blog.py": "from app import app\n"})
        self.assertEqual(c.command, "{python} -m flask run --port {port}")
        c = self.first({"requirements.txt": "fastapi\nuvicorn\n", "api.py": "from fastapi import FastAPI\napi = FastAPI()\n"})
        self.assertEqual(c.command, "{python} -m uvicorn api:api --port {port}")
        c = self.first({"requirements.txt": "pygame\n", "snake.py": "x = 1\nif __name__ == \"__main__\":\n    main()\n", "setup.py": ""})
        self.assertEqual(c.command, "{python} snake.py")

    def test_python_readme_command_and_requirements_variants(self):
        c = self.first({"requirements_versions.txt": "torch\n", "requirements_docker.txt": "", "entry_with_update.py": "", "launch.py": "",
                        "readme.md": "Run `python entry_with_update.py` or `python devscripts/x.py`\n", "devscripts/x.py": ""})
        self.assertEqual((c.command, c.deps), ("{python} entry_with_update.py", "{system_python} -m venv .venv && {venv_python} -m pip install -r requirements_versions.txt"))
        c = self.first({"manage.py": "", "requirements/dev.txt": "django\n", "requirements/prod.txt": ""})
        self.assertTrue(c.deps.endswith("-m pip install -r requirements/dev.txt"))

    def test_pip_install_e_only_when_buildable(self):
        # A pyproject.toml with just a [project] table isn't meant to be installed (ComfyUI).
        c = self.first({"pyproject.toml": '[project]\nname = "app"\ndependencies = ["numpy"]\n', "requirements.txt": "numpy\n", "main.py": ""})
        self.assertNotIn("-e .", c.deps)
        c = self.first({"pyproject.toml": '[project]\nname = "app"\ndependencies = ["django==5.0"]\n', "manage.py": ""})
        self.assertTrue(c.deps.endswith('pip install "django==5.0"'))
        c = self.first({"pyproject.toml": '[build-system]\nrequires = ["hatchling"]\n[project]\nname = "app"\n', "main.py": ""})
        self.assertIn("-e .", c.deps)

    def test_installed_command_uses_readme_arguments(self):
        files = {"pyproject.toml": '[build-system]\nrequires = ["setuptools"]\n[project]\nname = "games"\n[project.scripts]\nfreegames = "g:main"\n',
                 "README.rst": "Install::\n\n  $ pipx install freegames\n  $ freegames --help\n  $ freegames play life\n"}
        c = self.first(files)
        self.assertEqual((c.label, c.command), ("freegames play life", '"{venv_bin}/freegames" play life'))

    def test_python_m_skips_build_helpers(self):
        found = detect(self.repo({"setup.py": "", "buildconfig/__main__.py": ""}), "linux")
        self.assertFalse(any("buildconfig" in c.command for c in found))

    def test_launcher_scripts_first(self):
        files = {"server.py": "", "start_windows.bat": "", "cmd_windows.bat": "", "update_wizard_windows.bat": "",
                 "start_linux.sh": "#!/usr/bin/env bash\n", "start_macos.sh": ""}
        found = detect(self.repo(files), "win32")
        self.assertEqual(found[0].command, "start_windows.bat")
        self.assertFalse(any("cmd_windows" in c.command or "update" in c.command for c in found))
        found = [c.command for c in detect(self.repo(files), "linux")]
        self.assertEqual(found[0], "bash start_linux.sh")
        self.assertNotIn("sh start_macos.sh", found)
        self.assertNotIn("make.bat", [c.command for c in detect(self.repo({"make.bat": "", "setup.py": ""}), "win32")])

    def test_compose_with_many_services_first(self):
        compose = "services:\n  web:\n    build: .\n  worker:\n    build: w\n  db:\n    image: postgres\n    environment:\n      A: b\n"
        found = detect(self.repo({"package.json": json.dumps({"scripts": {"dev": "vite"}}), "compose.yml": compose, ".env.example": "A=1"}), "linux")
        self.assertEqual(found[0].command, "docker compose up --build")
        self.assertIn("starts 3 services together", found[0].notes)
        self.assertTrue(any(".env.example" in n for n in found[0].notes))
        c = self.first({"docker/docker-compose.yml": "services:\n  a:\n    image: x\n"})
        self.assertEqual(c.command, "docker compose -f docker/docker-compose.yml up --build")
        # One service: the app's own command still comes first.
        found = detect(self.repo({"package.json": json.dumps({"scripts": {"dev": "vite"}}), "compose.yml": "services:\n  web:\n    build: .\n"}), "linux")
        self.assertEqual(found[0].command, "npm run dev")

    def test_bun_workspace_has_dependencies(self):
        c = self.first({"package.json": json.dumps({"workspaces": ["frontend"], "scripts": {"dev": "bun run --filter frontend dev"}}), "bun.lock": ""})
        self.assertEqual(c.deps, "bun install")

    def test_folder_of_static_sites(self):
        c = self.first({"a/index.html": "", "b/index.html": "", "README.md": ""})
        self.assertEqual(c.command, "{repodock} static . --port {port}")

    def test_procfile_gunicorn_not_on_windows(self):
        self.assertEqual(detect(self.repo({"Procfile": "web: gunicorn app:app\n"}), "win32"), [])

    def test_nothing(self):
        self.assertEqual(detect(self.repo({"README.md": "# hi"})), [])


class ExpandTests(unittest.TestCase):
    def test_placeholders(self):
        tmp = TempDir()
        try:
            root = tmp.path
            out = expand("{python} a.py --port {port}", root, 1234, "linux")
            self.assertTrue(out.endswith("a.py --port 1234"))
            self.assertFalse(out.startswith(".venv"))
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


class FrozenBuildTests(unittest.TestCase):
    """The Windows build runs as repodock.exe, so Python must come from PATH."""

    def setUp(self):
        import repodock.detect as d
        self.d = d
        self.saved = (getattr(d.sys, "frozen", None), d.shutil.which)

    def tearDown(self):
        frozen, which = self.saved
        if frozen is None:
            self.d.sys.__dict__.pop("frozen", None)
        else:
            self.d.sys.frozen = frozen
        self.d.shutil.which = which

    def use(self, paths):
        self.d.sys.frozen = True
        self.d.shutil.which = lambda name: paths.get(name)

    def test_python_from_path_skips_the_store_stub(self):
        self.use({"python": r"C:\Users\me\AppData\Local\Microsoft\WindowsApps\python.exe", "py": r"C:\Windows\py.exe"})
        self.assertEqual(self.d.system_python(), r"C:\Windows\py.exe -3")
        self.use({"python": r"C:\Program Files\Python312\python.exe"})
        self.assertEqual(self.d.expand("{system_python} -m venv .venv", Path(".")), r'"C:\Program Files\Python312\python.exe" -m venv .venv')

    def test_no_python_is_reported(self):
        self.use({})
        self.assertIsNone(self.d.system_python())
        c = self.d.Candidate("python main.py", "{python} main.py", "python")
        self.assertEqual(self.d.missing_tool(c), "Python")

    def test_static_site_uses_repodock_itself(self):
        self.use({})
        self.assertTrue(self.d.expand("{repodock} static .", Path(".")).endswith(" static ."))
        self.assertNotIn("-m repodock", self.d.expand("{repodock} static .", Path(".")))
