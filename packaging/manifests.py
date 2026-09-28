"""Write the winget and Scoop manifests for a release.

Run by .github/workflows/windows.yml when a release is published, with the
installer and zip it just attached to the release:

    python packaging/manifests.py 0.2.0 dist/repodock-setup.exe dist/repodock-windows-portable.zip dist/manifests

It updates bucket/repodock.json (so `scoop bucket add repodock
https://github.com/UmutAlisoglu/repodock` always installs the latest release)
and writes the three winget manifests into the output folder, ready to submit
to https://github.com/microsoft/winget-pkgs.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import sys
from pathlib import Path

REPO = "UmutAlisoglu/repodock"
PACKAGE = "UmutAlisoglu.repodock"
DOWNLOAD = f"https://github.com/{REPO}/releases/download/v{{version}}/{{name}}"
SUMMARY = "Paste a GitHub link, and repodock downloads the project and runs it from a local dashboard."
DESCRIPTION = """\
repodock downloads projects from GitHub and runs them from one window. Paste a
link (or a username to pick from their repositories) and each project gets a
card with its detected run command, Run and Stop buttons, live output, CPU and
memory use, and buttons to update, configure or delete it. It works out how to
run Node.js, Python, Go, Rust, .NET, Java and Docker projects, static websites
and ready-made programs from GitHub Releases, and never installs or runs
anything without asking first."""
MANIFEST_VERSION = "1.6.0"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def header(kind: str) -> str:
    return f"# yaml-language-server: $schema=https://aka.ms/winget-manifest.{kind}.{MANIFEST_VERSION}.schema.json\n\n"


def winget(version: str, setup: Path) -> dict[str, str]:
    url = DOWNLOAD.format(version=version, name=setup.name)
    today = datetime.date.today().isoformat()
    base = f"PackageIdentifier: {PACKAGE}\nPackageVersion: {version}\n"
    description = "\n".join("  " + line for line in DESCRIPTION.splitlines())
    return {
        f"{PACKAGE}.yaml": header("version") + base + f"DefaultLocale: en-US\nManifestType: version\nManifestVersion: {MANIFEST_VERSION}\n",
        f"{PACKAGE}.installer.yaml": header("installer") + base + f"""\
InstallerType: inno
Scope: user
InstallModes:
- interactive
- silent
- silentWithProgress
UpgradeBehavior: install
ReleaseDate: {today}
Installers:
- Architecture: x64
  InstallerUrl: {url}
  InstallerSha256: {sha256(setup).upper()}
  ProductCode: '{{6F3C2B8E-4D1A-4E7B-9C55-2A1D7E0B9F41}}_is1'
ManifestType: installer
ManifestVersion: {MANIFEST_VERSION}
""",
        f"{PACKAGE}.locale.en-US.yaml": header("defaultLocale") + base + f"""\
PackageLocale: en-US
Publisher: UmutAlisoglu
PublisherUrl: https://github.com/UmutAlisoglu
PublisherSupportUrl: https://github.com/{REPO}/issues
PackageName: repodock
PackageUrl: https://github.com/{REPO}
License: MIT
LicenseUrl: https://github.com/{REPO}/blob/main/LICENSE
ShortDescription: {SUMMARY}
Description: |-
{description}
Moniker: repodock
Tags:
- github
- launcher
- dashboard
- developer-tools
- self-hosted
ReleaseNotesUrl: https://github.com/{REPO}/releases/tag/v{version}
ManifestType: defaultLocale
ManifestVersion: {MANIFEST_VERSION}
""",
    }


def scoop(version: str, portable: Path) -> dict:
    return {
        "version": version,
        "description": SUMMARY,
        "homepage": f"https://github.com/{REPO}",
        "license": "MIT",
        "notes": "Projects are downloaded into ~/repodock. Start it from the Start Menu, or run `repodock` in a terminal.",
        "architecture": {"64bit": {"url": DOWNLOAD.format(version=version, name=portable.name), "hash": sha256(portable)}},
        "bin": [["repodock-cli.exe", "repodock"]],
        "shortcuts": [["repodock.exe", "repodock"]],
        "checkver": "github",
        "autoupdate": {"architecture": {"64bit": {"url": DOWNLOAD.format(version="$version", name=portable.name)}}},
    }


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print(__doc__)
        return 2
    version, setup, portable, out = argv[0].lstrip("v"), Path(argv[1]), Path(argv[2]), Path(argv[3])
    folder = out / "winget" / "manifests" / PACKAGE[0].lower() / PACKAGE.split(".")[0] / PACKAGE.split(".")[1] / version
    folder.mkdir(parents=True, exist_ok=True)
    for name, text in winget(version, setup).items():
        (folder / name).write_text(text, encoding="utf-8", newline="\n")
    bucket = json.dumps(scoop(version, portable), indent=4) + "\n"
    (out / "repodock.json").write_text(bucket, encoding="utf-8", newline="\n")
    root = Path(__file__).resolve().parent.parent
    (root / "bucket").mkdir(exist_ok=True)
    (root / "bucket" / "repodock.json").write_text(bucket, encoding="utf-8", newline="\n")
    print(f"winget manifests in {folder}, Scoop manifest in bucket/repodock.json")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
