# gitsem

Docker-style floating semantic-version tags for Git repositories.

## What it does

`gitsem` applies **moving channel tags** to your current Git commit, mirroring how Docker manages `latest`, `1`, and `1.3` alongside `1.3.4`. A single release command keeps all related tags aligned on the same commit, moving floating tags automatically and pinning exact release tags.

```
gitsem 1.3.4       → tags  1,  1.3,  1.3.4  all pointing to HEAD
gitsem v1.3.4      → tags v1, v1.3, v1.3.4  all pointing to HEAD
gitsem 1.3         → tags  1,  1.3           all pointing to HEAD
gitsem --push 1.3.4  → same as above, then syncs to origin
```

## Requirements

- Python 3.10 or newer
- Git
- [uv](https://docs.astral.sh/uv/getting-started/installation/)

## Installation & usage

### Run without installing

Execute the latest commit directly from GitHub — no clone required:

```sh
uvx --from git+https://github.com/aheimsbakk/gitsem gitsem 1.3.4
```

### Install globally from GitHub

Install as a persistent tool available on your `PATH`:

```sh
uv tool install git+https://github.com/aheimsbakk/gitsem
gitsem 1.3.4
```

### Install locally from a clone

```sh
git clone https://github.com/aheimsbakk/gitsem
cd gitsem
uv sync
uv run gitsem 1.3.4
```

## Usage

```
gitsem [--push] [--force] [--switch] [--verbose] <version>
gitsem --help
gitsem --version
```

### Arguments

| Argument | Description |
|---|---|
| `<version>` | Required. Accepted forms: `1.3`, `v1.3`, `1.3.4`, `v1.3.4` |
| `--push` | Synchronize managed tags to `origin` after local tagging |
| `--force` | Allow overwriting conflicting exact release tags on the remote (requires `--push`) |
| `--switch` | Migrate all managed release tags to the prefix style of the requested version |
| `-v`, `--verbose` | Emit additional operational detail |
| `-V`, `--version` | Show the application version |
| `-h`, `--help` | Show usage |

### Prefix style detection

`gitsem` inspects your existing managed release tags and enforces a consistent prefix style. If your repository already uses `v1.x` tags, passing `1.3.5` (unprefixed) will fail with a clear error. Use `--switch` to migrate the entire tag history to the new style.

```sh
# Migrate from unprefixed to prefixed in one command
gitsem --switch v1.3.5
```

### Floating vs exact tags

| Depth | Floating | Exact |
|---|---|---|
| `MAJOR.MINOR.PATCH` | `MAJOR`, `MAJOR.MINOR` | `MAJOR.MINOR.PATCH` |
| `MAJOR.MINOR` | `MAJOR` | `MAJOR.MINOR` |

Floating tags are always moved to the latest release. Exact release tags are pinned and will not be overwritten unless deleted manually.

### Remote synchronization

`--push` uses delete-then-push to keep remote floating tags aligned. Floating remote tags are updated automatically; conflicting exact remote release tags require `--force`.

### Exit codes

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | Invalid version string |
| `2` | Unhealthy repository state |
| `3` | Prefix style mismatch |
| `4` | Local tag conflict |
| `5` | Remote tag conflict |
| `6` | Remote permission / server policy error |
| `7` | Git execution error |

## Repository layout

```
src/gitsem/
  __init__.py    # package version
  __main__.py    # python -m gitsem entry point
  cli.py         # argument parsing and exit-code mapping
  versioning.py  # version validation, prefix preservation, tag derivation
  git_ops.py     # Git subprocess operations
  tag_service.py # orchestration: style detection, tagging, switching, push
  errors.py      # typed domain errors
tests/
  test_versioning.py   # unit tests for versioning logic
  test_tag_service.py  # unit tests for tag orchestration (mocked Git)
  test_cli.py          # unit tests for CLI argument parsing and exit codes
  test_integration.py  # integration tests against real temporary Git repos
scripts/
  bump-version.sh       # bump patch / minor / major in pyproject.toml
  validate-worklog.sh   # validate docs/worklogs/ front-matter schema
```

## Running tests

```sh
uv run python -m unittest discover -s tests -v
```

## Scripts

### `scripts/bump-version.sh`

Bumps the version in `pyproject.toml`.

```sh
scripts/bump-version.sh patch   # 0.1.0 → 0.1.1
scripts/bump-version.sh minor   # 0.1.0 → 0.2.0
scripts/bump-version.sh major   # 0.1.0 → 1.0.0
```

### `scripts/validate-worklog.sh`

Validates all Markdown files in `docs/worklogs/` for required YAML front-matter keys and filename format.

```sh
scripts/validate-worklog.sh
```
