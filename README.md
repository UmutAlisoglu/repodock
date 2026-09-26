# repodock

**Paste a GitHub link, and repodock downloads the project and runs it from a local dashboard.**

Trying out a project from GitHub usually means cloning it, reading the README to
work out how to start it, installing its dependencies and keeping a terminal
open. repodock does that from one page in your browser: paste a link (or a
username to pick from all their repositories), and each project gets a card with
its detected run command, a Run/Stop button, live output, and buttons to update,
open or delete it. It never installs or runs anything without asking first.
Works on Windows, macOS and Linux. Pure Python, no dependencies.

![repodock with four projects, one running and one showing its output](docs/dashboard.png)

## Download for Windows

**[Download repodock-setup.exe](https://github.com/UmutAlisoglu/repodock/releases/latest/download/repodock-setup.exe)**,
double-click it and click through the installer. No Python or admin rights
needed. It adds repodock to the Start Menu (and the desktop, if you tick the
box) and can be removed from Windows Settings > Apps like any other program.

- Windows may say "Windows protected your PC" because the installer isn't
  signed. Click **More info**, then **Run anyway**.
- Starting repodock opens a small black window and the dashboard in your
  browser. Close the window to stop repodock and everything it started.
- Rather not install anything? Download
  [repodock-windows-portable.zip](https://github.com/UmutAlisoglu/repodock/releases/latest/download/repodock-windows-portable.zip),
  unzip it anywhere and double-click `repodock.exe`.
- repodock itself needs nothing else, but projects do: a Python project needs
  [Python](https://www.python.org/downloads/), a Node.js project needs
  [Node.js](https://nodejs.org/), and so on. The card tells you when something
  is missing. [Git](https://git-scm.com/downloads) is optional.

## Install with pipx (macOS, Linux, Windows)

```console
pipx install git+https://github.com/UmutAlisoglu/repodock
```

On Windows, install [Python](https://www.python.org/downloads/) first (tick
"Add python.exe to PATH"), then in PowerShell:

```powershell
py -m pip install --user pipx
py -m pipx ensurepath
pipx install git+https://github.com/UmutAlisoglu/repodock
```

[Git](https://git-scm.com/downloads) is recommended but optional: without it,
repodock downloads zip archives instead.

## Usage

```console
repodock
```

This opens the dashboard at http://localhost:8766. Paste any of these into the box:

- `https://github.com/owner/project` (also `.git` links, `/tree/branch` links and `git@github.com:` links)
- `owner/project`
- `https://github.com/owner` or just `owner` to choose from all of their repositories

![Choosing repositories from a user, with forks and archived ones left out](docs/add-user.png)

Projects are downloaded into `~/repodock/<owner>/<project>` and grouped by owner
on the page. Other commands:

```console
repodock --dir D:\Projects        # keep projects somewhere else (or set REPODOCK_DIR)
repodock --port 9000 --no-open
repodock add owner/project        # download from the terminal
repodock add owner --all          # every repository of a user, except forks and archived ones
repodock list
repodock detect path/to/folder    # show how repodock would run a folder
```

A GitHub token is optional. repodock uses `GITHUB_TOKEN`, `GH_TOKEN` or your
GitHub CLI login when present, which raises the API rate limit and lets it
recognize your own repositories.

## How it runs projects

repodock looks at the files in the project and suggests a run command. You can
pick another suggestion or type your own, and it's remembered per project.

| Project | Suggested command | Dependencies (asked first) |
|---|---|---|
| Node.js | `npm run dev`, `npm start`, or `node main.js` (pnpm, Yarn and Bun detected from the lockfile) | `npm install` / `npm ci` / `pnpm install` / ... |
| Python | `python main.py` (also `app.py`, `run.py`, ...), `python -m package`, Django `manage.py runserver`, Streamlit, or the project's own command from `pyproject.toml` | a `.venv` in the project, then `pip install -r requirements.txt` and/or `pip install -e .` |
| Go | `go run .` or `go run ./cmd/<name>` | downloaded by Go |
| Rust | `cargo run --release` | downloaded by Cargo |
| .NET | `dotnet run --project <App>.csproj` | restored by dotnet |
| Java | `mvn spring-boot:run`, `mvnw`, `gradlew run` / `bootRun` | downloaded by the build tool |
| Deno | `deno task dev` / `start` | |
| Makefile | `make run` / `start` / `serve` / `dev` | |
| Procfile | the `web:` command | |
| Docker | `docker compose up --build`, or build and run the Dockerfile | |
| Windows programs | a `.exe`, `.bat`, `.cmd` or `.ps1` in the project | |
| Shell scripts | `start.sh`, `run.sh`, ... on macOS and Linux | |
| Static website | serves `index.html` (or `public/`, `docs/`, `dist/`) on a local port | |

When a command needs a program you don't have (Node.js, Go, Docker, ...),
the card says so.

### Nothing runs without your say-so

- The first time you run a project, and whenever its command changes, repodock
  shows the exact command before anything runs.
- Dependencies are never installed automatically. If a project needs them,
  you choose between **Install and run**, **Run without installing** or
  **Cancel**, and you see the exact install command. Python dependencies go into
  a `.venv` inside the project, never into your system Python.
- Projects from other people get a clear warning: their code runs with your
  permissions, so only run what you trust.
- **Stop** ends the whole process tree (for example npm and the node server it
  started), on Windows too. Stopping repodock with Ctrl+C stops everything it started.
- The dashboard only listens on `127.0.0.1`. The API refuses requests from
  other websites (a custom header is required) and from other host names
  (which blocks DNS rebinding).

### Updating and deleting

**Update** runs `git pull`, or for zip downloads fetches the new version while
keeping installed dependencies. **Delete** stops the project and removes its
folder. Folders you clone into `~/repodock/<owner>/<project>` yourself show up
automatically.

## Development

```console
python -m venv .venv && source .venv/bin/activate
pip install -e .
python -m unittest discover -s tests
```

The tests use local git repositories and a fake GitHub API, so they need no
network. CI runs them on Linux (Python 3.9 to 3.13), Windows and macOS.

## License

MIT
