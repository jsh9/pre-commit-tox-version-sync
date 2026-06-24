"""Parsing helpers for tox.ini."""

from __future__ import annotations

import configparser
from pathlib import Path

from .errors import ConfigError


def load_tox_env_deps(path: Path, env_names: list[str]) -> dict[str, list[str] | None]:
    """Return dependency lines for selected tox environments.

    A value of ``None`` means the requested environment section was not present.
    """

    parser = configparser.ConfigParser(interpolation=None)
    try:
        with path.open("r", encoding="utf-8") as file:
            parser.read_file(file)
    except OSError as exc:
        raise ConfigError(f"{path}: could not read file: {exc.strerror}") from exc
    except configparser.Error as exc:
        raise ConfigError(f"{path}: could not parse INI: {exc}") from exc

    env_deps: dict[str, list[str] | None] = {}
    for env_name in env_names:
        section = f"testenv:{env_name}"
        if not parser.has_section(section):
            env_deps[env_name] = None
            continue

        raw_deps = parser.get(section, "deps", fallback="")
        env_deps[env_name] = list(_iter_dep_lines(raw_deps))

    return env_deps


def _iter_dep_lines(raw_deps: str) -> list[str]:
    lines: list[str] = []
    for raw_line in raw_deps.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        before_comment = line.split("#", 1)[0].strip()
        if before_comment:
            lines.append(before_comment)

    return lines
