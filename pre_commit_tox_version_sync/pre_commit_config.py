"""Parsing helpers for .pre-commit-config.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .errors import ConfigError


def load_pre_commit_revs(path: Path, repo_urls: list[str]) -> dict[str, str | None]:
    """Return revs for requested pre-commit repository URLs.

    A value of ``None`` means the repo URL was not present in the config.
    """

    data = _load_yaml_mapping(path)
    repos = data.get("repos")
    if not isinstance(repos, list):
        raise ConfigError(f"{path}: expected top-level 'repos' list")

    requested = set(repo_urls)
    found: dict[str, str | None] = {repo_url: None for repo_url in repo_urls}
    for index, repo in enumerate(repos):
        if not isinstance(repo, dict):
            raise ConfigError(f"{path}: expected repos[{index}] to be a mapping")

        repo_url = repo.get("repo")
        if repo_url in requested:
            rev = repo.get("rev")
            if not isinstance(rev, str) or not rev:
                raise ConfigError(f"{path}: repo {repo_url!r} is missing a string 'rev'")
            found[repo_url] = rev

    return found


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as file:
            data = yaml.safe_load(file)
    except OSError as exc:
        raise ConfigError(f"{path}: could not read file: {exc.strerror}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path}: could not parse YAML: {exc}") from exc

    if data is None:
        raise ConfigError(f"{path}: file is empty")
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: expected a YAML mapping")

    return data
