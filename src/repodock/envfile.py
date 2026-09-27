"""Read and edit a project's .env file, keeping its comments and order."""

from __future__ import annotations

import re
from pathlib import Path

LINE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_.]*)\s*=\s*(.*?)\s*$")
NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        inner = value[1:-1]
        return inner.replace("\\n", "\n").replace('\\"', '"') if value[0] == '"' else inner
    return re.sub(r"\s+#.*$", "", value)  # an unquoted value can end with a comment


def _quote(value: str) -> str:
    if value == "" or re.fullmatch(r"[A-Za-z0-9_./:@+,=-]+", value):
        return value
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def read(path: Path) -> list[tuple[str, str]]:
    """The variables in a .env file, in order."""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (FileNotFoundError, UnicodeDecodeError):
        return []
    found: dict[str, str] = {}
    for line in text.splitlines():
        m = LINE.match(line)
        if m and not line.lstrip().startswith("#"):
            found[m.group(1)] = _unquote(m.group(2))
    return list(found.items())


def write(path: Path, values: list[tuple[str, str]]) -> None:
    """Save variables: changed ones are edited in place, removed ones dropped, new ones appended."""
    for name, _ in values:
        if not NAME.match(name):
            raise ValueError(f"not a valid variable name: {name!r}")
    wanted = dict(values)
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except (FileNotFoundError, UnicodeDecodeError):
        lines = []
    out, seen = [], set()
    for line in lines:
        m = LINE.match(line)
        if not m or line.lstrip().startswith("#"):
            out.append(line)
            continue
        name = m.group(1)
        if name not in wanted or name in seen:
            continue
        seen.add(name)
        out.append(line if _unquote(m.group(2)) == wanted[name] else f"{name}={_quote(wanted[name])}")
    out += [f"{name}={_quote(value)}" for name, value in values if name not in seen]
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
