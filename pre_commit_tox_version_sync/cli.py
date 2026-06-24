"""Command line interface for the pre-commit hook."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from .checker import check_versions, format_failure, format_success
from .errors import ConfigError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sync-precommit-tox-versions",
        description="Check selected pre-commit repo revs against tox dependency pins.",
    )
    parser.add_argument(
        "--pre-commit-config",
        default=".pre-commit-config.yaml",
        type=Path,
        help="Path to .pre-commit-config.yaml. Defaults to %(default)s.",
    )
    parser.add_argument(
        "--tox-ini",
        default="tox.ini",
        type=Path,
        help="Path to tox.ini. Defaults to %(default)s.",
    )
    parser.add_argument(
        "--pre-commit-repo",
        action="append",
        required=True,
        help="Pre-commit repo URL to check. May be provided more than once.",
    )
    parser.add_argument(
        "--tox-env",
        action="append",
        required=True,
        help="tox environment name to check. May be provided more than once.",
    )
    parser.add_argument(
        "--tox-dep",
        required=True,
        help="tox dependency package name to compare against the pre-commit rev.",
    )
    parser.add_argument(
        "--strip-rev-prefix",
        default="v",
        help="Leading pre-commit rev prefix to remove once before comparison.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        result = check_versions(
            pre_commit_config=args.pre_commit_config,
            tox_ini=args.tox_ini,
            pre_commit_repos=args.pre_commit_repo,
            tox_envs=args.tox_env,
            tox_dep=args.tox_dep,
            strip_rev_prefix=args.strip_rev_prefix,
        )
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if result.ok:
        print(format_success(result))
        return 0

    print(format_failure(result))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
