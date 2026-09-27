"""Programs that projects need (Node.js, Go, ...) and how to install them."""

from __future__ import annotations

import os
import shutil
import sys

# name shown to the user -> (winget package id, download page)
TOOLCHAINS = {
    "Node.js": ("OpenJS.NodeJS.LTS", "https://nodejs.org/"),
    "Python": ("Python.Python.3.12", "https://www.python.org/downloads/"),
    "Go": ("GoLang.Go", "https://go.dev/dl/"),
    "Rust (cargo)": ("Rustlang.Rustup", "https://rustup.rs/"),
    ".NET SDK": ("Microsoft.DotNet.SDK.8", "https://dotnet.microsoft.com/download"),
    "Java": ("EclipseAdoptium.Temurin.21.JDK", "https://adoptium.net/"),
    "Maven": ("Apache.Maven", "https://maven.apache.org/download.cgi"),
    "Gradle": ("Gradle.Gradle", "https://gradle.org/install/"),
    "Docker": ("Docker.DockerDesktop", "https://www.docker.com/products/docker-desktop/"),
    "Deno": ("DenoLand.Deno", "https://deno.com/"),
    "Bun": ("Oven-sh.Bun", "https://bun.sh/"),
    "pnpm": ("pnpm.pnpm", "https://pnpm.io/installation"),
    "Yarn": ("Yarn.Yarn", "https://yarnpkg.com/getting-started/install"),
    "Git": ("Git.Git", "https://git-scm.com/downloads"),
}


def has_winget() -> bool:
    return sys.platform.startswith("win") and shutil.which("winget") is not None


def install_info(tool: str | None) -> dict | None:
    """What the card offers for a missing program: a winget command on Windows, a download page otherwise."""
    if not tool or tool not in TOOLCHAINS:
        return None
    package, page = TOOLCHAINS[tool]
    info = {"tool": tool, "page": page, "command": None}
    if has_winget():
        info["command"] = f"winget install --id {package} -e --source winget --accept-source-agreements --accept-package-agreements"
    return info


def refresh_path() -> None:
    """Pick up PATH changes made by an installer, without restarting repodock (Windows only)."""
    if not sys.platform.startswith("win"):
        return
    import winreg  # type: ignore[import-not-found]

    parts: list[str] = []
    for hive, sub in ((winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
                      (winreg.HKEY_CURRENT_USER, "Environment")):
        try:
            with winreg.OpenKey(hive, sub) as key:
                value, _ = winreg.QueryValueEx(key, "Path")
                parts += [os.path.expandvars(p) for p in value.split(";") if p]
        except OSError:
            continue
    for p in os.environ.get("PATH", "").split(os.pathsep):
        if p and p not in parts:
            parts.append(p)
    os.environ["PATH"] = os.pathsep.join(parts)
