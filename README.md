# pre-commit-tox-version-sync

Check that selected pre-commit hook revs match exact dependency pins in selected
tox environments.

The initial use case is keeping `muff` aligned between `pre-commit` and `tox`.
The hook is check-only: it reports mismatches but does not edit files.

## Usage

Add the hook to `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/jsh9/pre-commit-tox-version-sync
    rev: v0.1.0
    hooks:
      - id: sync-precommit-tox-versions
        args:
          - --pre-commit-repo
          - https://github.com/jsh9/muff-pre-commit
          - --tox-env
          - muff-lint
          - --tox-env
          - muff-format
          - --tox-dep
          - muff
```

With this pre-commit repo:

```yaml
repos:
  - repo: https://github.com/jsh9/muff-pre-commit
    rev: 0.15.18
    hooks:
      - id: muff-lint
      - id: muff-format
```

the selected tox environments will pin to the same package version:

```ini
[testenv:muff-lint]
deps =
    muff==0.15.18

[testenv:muff-format]
deps =
    muff==0.15.18
```

## Hook Arguments

- `--pre-commit-config`: path to `.pre-commit-config.yaml`, default
  `.pre-commit-config.yaml`.
- `--tox-ini`: path to `tox.ini`, default `tox.ini`.
- `--pre-commit-repo`: exact pre-commit repo URL to check. Repeatable.
- `--tox-env`: tox environment name to check. Repeatable.
- `--tox-dep`: package name to compare against the pre-commit rev.
- `--strip-rev-prefix`: leading rev prefix to remove once before comparison,
  default `v`.

## Exit Codes

- `0`: every selected tox env pins `tox_dep==pre_commit_rev`.
- `1`: the selected repo, env, dependency, pin, or version check failed.
- `2`: hook arguments are invalid or a config file is unreadable or unparseable.
