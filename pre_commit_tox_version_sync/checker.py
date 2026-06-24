"""Version comparison and report formatting."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .pre_commit_config import load_pre_commit_revs
from .requirements import find_dependency_pin
from .tox_config import load_tox_env_deps


@dataclass(frozen=True)
class CheckResult:
    """Result of a version sync check."""

    expected_version: str | None
    failures: list[str]
    checked_envs: int
    package_name: str

    @property
    def ok(self) -> bool:
        return not self.failures


def check_versions(
    *,
    pre_commit_config: Path,
    tox_ini: Path,
    pre_commit_repos: list[str],
    tox_envs: list[str],
    tox_dep: str,
    strip_rev_prefix: str,
) -> CheckResult:
    """Check selected pre-commit repo revs against tox dependency pins."""

    raw_revs = load_pre_commit_revs(pre_commit_config, pre_commit_repos)
    env_deps = load_tox_env_deps(tox_ini, tox_envs)

    failures: list[str] = []
    normalized_revs: dict[str, str] = {}
    for repo_url, rev in raw_revs.items():
        if rev is None:
            failures.append(f"missing pre-commit repo: {repo_url}")
            continue
        normalized_revs[repo_url] = normalize_rev(rev, strip_rev_prefix)

    expected_versions = set(normalized_revs.values())
    if len(expected_versions) == 1:
        expected_version = next(iter(expected_versions))
    else:
        expected_version = None
        if expected_versions:
            versions = ", ".join(
                f"{repo_url}={version}"
                for repo_url, version in sorted(normalized_revs.items())
            )
            failures.append(f"pre-commit repos resolve to different versions: {versions}")

    checked_envs = 0
    for env_name, dep_lines in env_deps.items():
        if dep_lines is None:
            failures.append(f"missing tox env: {env_name}")
            continue

        checked_envs += 1
        dep_pin = find_dependency_pin(dep_lines, tox_dep)
        if dep_pin is None:
            failures.append(f"{env_name}: missing tox dependency {tox_dep!r}")
            continue

        if not dep_pin.is_exact:
            failures.append(
                f"{env_name}: {tox_dep!r} must be pinned with exactly one == specifier "
                f"(found {dep_pin.requirement!r})"
            )
            continue

        if expected_version is not None and dep_pin.version != expected_version:
            failures.append(
                f"{env_name}: {tox_dep}=={dep_pin.version} does not match "
                f"pre-commit rev {expected_version}"
            )

    return CheckResult(
        expected_version=expected_version,
        failures=failures,
        checked_envs=checked_envs,
        package_name=tox_dep,
    )


def normalize_rev(rev: str, strip_rev_prefix: str) -> str:
    """Remove one configured leading prefix from a pre-commit rev."""

    if strip_rev_prefix and rev.startswith(strip_rev_prefix):
        return rev[len(strip_rev_prefix) :]
    return rev


def format_success(result: CheckResult) -> str:
    version = result.expected_version or "<unknown>"
    env_label = "tox env" if result.checked_envs == 1 else "tox envs"
    return (
        f"OK: {result.package_name}=={version} matches pre-commit rev "
        f"for {result.checked_envs} {env_label}."
    )


def format_failure(result: CheckResult) -> str:
    lines = ["pre-commit/tox version sync failed:"]
    lines.extend(f"- {failure}" for failure in result.failures)
    return "\n".join(lines)
