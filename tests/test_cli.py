from __future__ import annotations

from pathlib import Path

import pytest

from pre_commit_tox_version_sync.cli import main


REPO = "https://github.com/jsh9/muff-pre-commit"


def write_project(tmp_path: Path, *, rev: str = "0.15.18", dep: str = "muff==0.15.18") -> None:
    (tmp_path / ".pre-commit-config.yaml").write_text(
        f"""
repos:
  - repo: {REPO}
    rev: {rev}
    hooks:
      - id: muff-lint
""",
        encoding="utf-8",
    )
    (tmp_path / "tox.ini").write_text(
        f"""
[testenv:muff-lint]
deps =
    {dep}
""",
        encoding="utf-8",
    )


def cli_args(tmp_path: Path) -> list[str]:
    return [
        "--pre-commit-config",
        str(tmp_path / ".pre-commit-config.yaml"),
        "--tox-ini",
        str(tmp_path / "tox.ini"),
        "--pre-commit-repo",
        REPO,
        "--tox-env",
        "muff-lint",
        "--tox-dep",
        "muff",
    ]


def test_cli_success_exit_code_and_stdout(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write_project(tmp_path)

    exit_code = main(cli_args(tmp_path))

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == "OK: muff==0.15.18 matches pre-commit rev for 1 tox env.\n"
    assert captured.err == ""


def test_cli_failure_exit_code_and_stdout(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write_project(tmp_path, dep="muff==0.15.17")

    exit_code = main(cli_args(tmp_path))

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == (
        "pre-commit/tox version sync failed:\n"
        "- muff-lint: muff==0.15.17 does not match pre-commit rev 0.15.18\n"
    )
    assert captured.err == ""


def test_cli_config_error_exit_code_and_stderr(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_project(tmp_path)
    (tmp_path / ".pre-commit-config.yaml").write_text("repos: [", encoding="utf-8")

    exit_code = main(cli_args(tmp_path))

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert captured.err.startswith("error: ")
    assert "could not parse YAML" in captured.err


def test_cli_invalid_usage_exits_2(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main([])

    captured = capsys.readouterr()
    assert exc_info.value.code == 2
    assert "the following arguments are required" in captured.err
