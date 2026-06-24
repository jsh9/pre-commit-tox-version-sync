"""Parsing helpers for tox.ini."""

from __future__ import annotations

import configparser
import re
from dataclasses import dataclass
from pathlib import Path

from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name

from .errors import ConfigError
from .requirements import find_dependency_pin


@dataclass(frozen=True)
class ToxSyncResult:
    """Result of syncing selected tox dependency lines."""

    failures: list[str]
    checked_envs: int
    changed_envs: list[str]


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


def sync_tox_env_deps(
    path: Path,
    env_names: list[str],
    package_name: str,
    expected_version: str,
) -> ToxSyncResult:
    """Rewrite selected tox deps to the expected exact package pin."""

    env_deps = load_tox_env_deps(path, env_names)

    failures: list[str] = []
    checked_envs = 0
    envs_to_rewrite: set[str] = set()
    for env_name, dep_lines in env_deps.items():
        if dep_lines is None:
            failures.append(f"missing tox env: {env_name}")
            continue

        checked_envs += 1
        dep_pin = find_dependency_pin(dep_lines, package_name)
        if dep_pin is None:
            failures.append(f"{env_name}: missing tox dependency {package_name!r}")
            continue

        if not dep_pin.is_rewritable:
            failures.append(
                f"{env_name}: {package_name!r} must be bare or pinned with exactly "
                f"one == specifier (found {dep_pin.requirement!r})"
            )
            continue

        if dep_pin.version != expected_version:
            envs_to_rewrite.add(env_name)

    changed_envs: list[str] = []
    if envs_to_rewrite:
        text = _read_text(path)
        new_text, changed_envs = _rewrite_tox_text(
            text=text,
            env_names=env_names,
            envs_to_rewrite=envs_to_rewrite,
            package_name=package_name,
            expected_version=expected_version,
        )

        missing_rewrites = envs_to_rewrite.difference(changed_envs)
        for env_name in sorted(missing_rewrites):
            failures.append(
                f"{env_name}: could not update tox dependency {package_name!r}"
            )

        if new_text != text:
            try:
                path.write_text(new_text, encoding="utf-8")
            except OSError as exc:
                raise ConfigError(
                    f"{path}: could not write file: {exc.strerror}"
                ) from exc

    ordered_changed_envs = [env_name for env_name in env_names if env_name in changed_envs]
    return ToxSyncResult(
        failures=failures,
        checked_envs=checked_envs,
        changed_envs=ordered_changed_envs,
    )


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"{path}: could not read file: {exc.strerror}") from exc


def _rewrite_tox_text(
    *,
    text: str,
    env_names: list[str],
    envs_to_rewrite: set[str],
    package_name: str,
    expected_version: str,
) -> tuple[str, list[str]]:
    lines = text.splitlines(keepends=True)
    selected_envs = set(env_names)
    current_env: str | None = None
    in_deps = False
    changed_envs: set[str] = set()

    for index, line in enumerate(lines):
        section_name = _section_name(line)
        if section_name is not None:
            current_env = _tox_env_name(section_name)
            in_deps = False
            continue

        if current_env not in selected_envs:
            in_deps = False
            continue

        option = _option_line(line)
        if option is not None:
            option_name, value_start = option
            in_deps = option_name == "deps"
            if in_deps and current_env in envs_to_rewrite:
                new_line, changed = _rewrite_value_segment(
                    line[:value_start],
                    line[value_start:],
                    package_name,
                    expected_version,
                )
                if changed:
                    lines[index] = new_line
                    changed_envs.add(current_env)
            continue

        if in_deps and current_env in envs_to_rewrite and _is_continuation_line(line):
            new_line, changed = _rewrite_value_segment(
                "",
                line,
                package_name,
                expected_version,
            )
            if changed:
                lines[index] = new_line
                changed_envs.add(current_env)
            continue

        if line.strip():
            in_deps = False

    return "".join(lines), list(changed_envs)


def _section_name(line: str) -> str | None:
    stripped = line.strip()
    if stripped.startswith("[") and stripped.endswith("]"):
        return stripped[1:-1].strip()
    return None


def _tox_env_name(section_name: str) -> str | None:
    prefix = "testenv:"
    if section_name.startswith(prefix):
        return section_name[len(prefix) :]
    return None


def _option_line(line: str) -> tuple[str, int] | None:
    body, _newline = _split_newline(line)
    match = re.match(r"^\s*([A-Za-z0-9_.-]+)(\s*[:=])(?![=])", body)
    if match is None:
        return None

    option_name = match.group(1).strip().lower()
    return option_name, match.end()


def _is_continuation_line(line: str) -> bool:
    body, _newline = _split_newline(line)
    return bool(body) and body[0].isspace()


def _rewrite_value_segment(
    prefix: str,
    value_segment: str,
    package_name: str,
    expected_version: str,
) -> tuple[str, bool]:
    body, newline = _split_newline(value_segment)
    leading = body[: len(body) - len(body.lstrip())]
    content = body[len(leading) :]
    if not content or content.startswith(("#", ";")):
        return prefix + value_segment, False

    requirement_part, comment = _split_inline_comment(content)
    requirement_text = requirement_part.strip()
    if not requirement_text:
        return prefix + value_segment, False

    try:
        requirement = Requirement(requirement_text)
    except InvalidRequirement:
        return prefix + value_segment, False

    if canonicalize_name(requirement.name) != canonicalize_name(package_name):
        return prefix + value_segment, False

    dep_pin = find_dependency_pin([requirement_text], package_name)
    if dep_pin is None or not dep_pin.is_rewritable:
        return prefix + value_segment, False
    if dep_pin.version == expected_version:
        return prefix + value_segment, False

    trailing = requirement_part[len(requirement_part.rstrip()) :]
    new_requirement = _pinned_requirement_text(requirement, expected_version)
    return prefix + leading + new_requirement + trailing + comment + newline, True


def _split_newline(line: str) -> tuple[str, str]:
    if line.endswith("\r\n"):
        return line[:-2], "\r\n"
    if line.endswith("\n"):
        return line[:-1], "\n"
    return line, ""


def _split_inline_comment(content: str) -> tuple[str, str]:
    requirement_part, separator, comment = content.partition("#")
    if separator:
        return requirement_part, separator + comment
    return content, ""


def _pinned_requirement_text(requirement: Requirement, expected_version: str) -> str:
    extras = f"[{','.join(sorted(requirement.extras))}]" if requirement.extras else ""
    marker = f"; {requirement.marker}" if requirement.marker else ""
    return f"{requirement.name}{extras}=={expected_version}{marker}"


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
