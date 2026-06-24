from __future__ import annotations

from pathlib import Path

from pre_commit_tox_version_sync.checker import check_versions


MUFF_REPO = "https://github.com/jsh9/muff-pre-commit"


def write_configs(
    tmp_path: Path,
    *,
    pre_commit_config: str | None = None,
    tox_ini: str | None = None,
) -> tuple[Path, Path]:
    pre_commit_path = tmp_path / ".pre-commit-config.yaml"
    tox_path = tmp_path / "tox.ini"
    pre_commit_path.write_text(
        pre_commit_config
        if pre_commit_config is not None
        else f"""
repos:
  - repo: {MUFF_REPO}
    rev: 0.15.18
    hooks:
      - id: muff-lint
""",
        encoding="utf-8",
    )
    tox_path.write_text(
        tox_ini
        if tox_ini is not None
        else """
[testenv:muff-lint]
deps =
    muff==0.15.18

[testenv:muff-format]
deps =
    muff==0.15.18
""",
        encoding="utf-8",
    )
    return pre_commit_path, tox_path


def run_check(
    pre_commit_path: Path,
    tox_path: Path,
    *,
    repos: list[str] | None = None,
    tox_envs: list[str] | None = None,
    tox_dep: str = "muff",
):
    return check_versions(
        pre_commit_config=pre_commit_path,
        tox_ini=tox_path,
        pre_commit_repos=repos or [MUFF_REPO],
        tox_envs=tox_envs or ["muff-lint", "muff-format"],
        tox_dep=tox_dep,
        strip_rev_prefix="v",
    )


def test_successful_sync_across_two_tox_envs(tmp_path: Path) -> None:
    pre_commit_path, tox_path = write_configs(tmp_path)

    result = run_check(pre_commit_path, tox_path)

    assert result.ok
    assert result.expected_version == "0.15.18"
    assert result.failures == []
    assert result.changed_envs == []


def test_v_prefix_normalization(tmp_path: Path) -> None:
    pre_commit_path, tox_path = write_configs(
        tmp_path,
        pre_commit_config="""
repos:
  - repo: https://example.com/tool-pre-commit
    rev: v1.2.3
    hooks:
      - id: tool
""",
        tox_ini="""
[testenv:tool]
deps =
    tool==1.2.3
""",
    )

    result = run_check(
        pre_commit_path,
        tox_path,
        repos=["https://example.com/tool-pre-commit"],
        tox_envs=["tool"],
        tox_dep="tool",
    )

    assert result.ok
    assert result.expected_version == "1.2.3"


def test_bare_dependencies_are_pinned_across_two_tox_envs(tmp_path: Path) -> None:
    pre_commit_path, tox_path = write_configs(
        tmp_path,
        tox_ini="""
[testenv:muff-lint]
deps =
    muff

[testenv:muff-format]
deps =
    muff
""",
    )

    result = run_check(pre_commit_path, tox_path)

    assert not result.ok
    assert result.failures == []
    assert result.changed_envs == ["muff-lint", "muff-format"]
    assert tox_path.read_text(encoding="utf-8") == """
[testenv:muff-lint]
deps =
    muff==0.15.18

[testenv:muff-format]
deps =
    muff==0.15.18
"""


def test_v_prefix_normalization_pins_bare_dependency(tmp_path: Path) -> None:
    pre_commit_path, tox_path = write_configs(
        tmp_path,
        pre_commit_config="""
repos:
  - repo: https://example.com/tool-pre-commit
    rev: v1.2.3
    hooks:
      - id: tool
""",
        tox_ini="""
[testenv:tool]
deps =
    tool
""",
    )

    result = run_check(
        pre_commit_path,
        tox_path,
        repos=["https://example.com/tool-pre-commit"],
        tox_envs=["tool"],
        tox_dep="tool",
    )

    assert not result.ok
    assert result.failures == []
    assert result.changed_envs == ["tool"]
    assert "tool==1.2.3" in tox_path.read_text(encoding="utf-8")


def test_missing_pre_commit_repo_fails(tmp_path: Path) -> None:
    pre_commit_path, tox_path = write_configs(tmp_path)
    original_tox = tox_path.read_text(encoding="utf-8")

    result = run_check(pre_commit_path, tox_path, repos=["https://example.com/missing"])

    assert not result.ok
    assert result.failures == ["missing pre-commit repo: https://example.com/missing"]
    assert result.changed_envs == []
    assert tox_path.read_text(encoding="utf-8") == original_tox


def test_missing_tox_env_fails(tmp_path: Path) -> None:
    pre_commit_path, tox_path = write_configs(tmp_path)

    result = run_check(pre_commit_path, tox_path, tox_envs=["muff-lint", "missing"])

    assert not result.ok
    assert result.failures == ["missing tox env: missing"]


def test_missing_tox_dependency_fails(tmp_path: Path) -> None:
    pre_commit_path, tox_path = write_configs(
        tmp_path,
        tox_ini="""
[testenv:muff-lint]
deps =
    pytest
""",
    )

    result = run_check(pre_commit_path, tox_path, tox_envs=["muff-lint"])

    assert not result.ok
    assert result.failures == ["muff-lint: missing tox dependency 'muff'"]


def test_inline_bare_dependency_is_pinned(tmp_path: Path) -> None:
    pre_commit_path, tox_path = write_configs(
        tmp_path,
        tox_ini="""
[testenv:muff-lint]
deps = muff
""",
    )

    result = run_check(pre_commit_path, tox_path, tox_envs=["muff-lint"])

    assert not result.ok
    assert result.failures == []
    assert result.changed_envs == ["muff-lint"]
    assert tox_path.read_text(encoding="utf-8") == """
[testenv:muff-lint]
deps = muff==0.15.18
"""


def test_multiline_formatting_and_unselected_envs_are_preserved(tmp_path: Path) -> None:
    pre_commit_path, tox_path = write_configs(
        tmp_path,
        tox_ini="""
[testenv:muff-lint]
deps =
    pytest
    muff  # keep this comment
    PyYAML

[testenv:other]
deps =
    muff
""",
    )

    result = run_check(pre_commit_path, tox_path, tox_envs=["muff-lint"])

    assert not result.ok
    assert result.failures == []
    assert result.changed_envs == ["muff-lint"]
    assert tox_path.read_text(encoding="utf-8") == """
[testenv:muff-lint]
deps =
    pytest
    muff==0.15.18  # keep this comment
    PyYAML

[testenv:other]
deps =
    muff
"""


def test_range_dependency_fails(tmp_path: Path) -> None:
    pre_commit_path, tox_path = write_configs(
        tmp_path,
        tox_ini="""
[testenv:muff-lint]
deps =
    muff>=0.15
""",
    )

    original_tox = tox_path.read_text(encoding="utf-8")
    result = run_check(pre_commit_path, tox_path, tox_envs=["muff-lint"])

    assert not result.ok
    assert result.failures == [
        "muff-lint: 'muff' must be bare or pinned with exactly one == specifier "
        "(found 'muff>=0.15')"
    ]
    assert result.changed_envs == []
    assert tox_path.read_text(encoding="utf-8") == original_tox


def test_stale_exact_pin_is_updated(tmp_path: Path) -> None:
    pre_commit_path, tox_path = write_configs(
        tmp_path,
        tox_ini="""
[testenv:muff-lint]
deps =
    muff==0.15.17
""",
    )

    result = run_check(pre_commit_path, tox_path, tox_envs=["muff-lint"])

    assert not result.ok
    assert result.failures == []
    assert result.changed_envs == ["muff-lint"]
    assert "muff==0.15.18" in tox_path.read_text(encoding="utf-8")


def test_multiple_repos_with_different_revs_fail_without_editing(tmp_path: Path) -> None:
    pre_commit_path, tox_path = write_configs(
        tmp_path,
        pre_commit_config=f"""
repos:
  - repo: {MUFF_REPO}
    rev: 0.15.18
    hooks:
      - id: muff-lint
  - repo: https://example.com/other-pre-commit
    rev: 1.0.0
    hooks:
      - id: other
""",
        tox_ini="""
[testenv:muff-lint]
deps =
    muff
""",
    )
    original_tox = tox_path.read_text(encoding="utf-8")

    result = run_check(
        pre_commit_path,
        tox_path,
        repos=[MUFF_REPO, "https://example.com/other-pre-commit"],
        tox_envs=["muff-lint"],
    )

    assert not result.ok
    assert result.failures == [
        "pre-commit repos resolve to different versions: "
        "https://example.com/other-pre-commit=1.0.0, "
        "https://github.com/jsh9/muff-pre-commit=0.15.18",
        "muff-lint: 'muff' must be pinned with exactly one == specifier (found 'muff')",
    ]
    assert result.changed_envs == []
    assert tox_path.read_text(encoding="utf-8") == original_tox


def test_reports_all_failures_in_one_run(tmp_path: Path) -> None:
    pre_commit_path, tox_path = write_configs(
        tmp_path,
        tox_ini="""
[testenv:muff-lint]
deps =
    muff==0.15.17

[testenv:muff-format]
deps =
    pytest
""",
    )

    result = run_check(
        pre_commit_path,
        tox_path,
        tox_envs=["muff-lint", "muff-format", "missing"],
    )

    assert not result.ok
    assert result.failures == [
        "muff-format: missing tox dependency 'muff'",
        "missing tox env: missing",
    ]
    assert result.changed_envs == ["muff-lint"]
    assert "muff==0.15.18" in tox_path.read_text(encoding="utf-8")
