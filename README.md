# gitsem

Docker-style floating semantic-version tags for Git repositories.

## What it does

`gitsem` applies **moving channel tags** to your current Git commit, mirroring how Docker manages `latest`, `1`, and `1.3` alongside `1.3.4`. A single release command keeps all related tags aligned on the same commit, moving floating tags automatically and pinning exact release tags.

```
gitsem 1.3.4         → tags  1,  1.3,  1.3.4  all pointing to HEAD
gitsem v1.3.4        → tags v1, v1.3, v1.3.4  all pointing to HEAD
gitsem 1.3           → tags  1,  1.3           all pointing to HEAD
gitsem --push 1.3.4  → same as above, then syncs those tags to origin
gitsem --push        → syncs ALL local managed tags to origin
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
gitsem [--push] [--force] [--migrate] [--dry-run] [-q] [--porcelain] [-v] <version>
gitsem --push [--force] [--dry-run] [-q] [--porcelain]
gitsem --help
gitsem --version
```

### Arguments

| Long | Short | Description |
|---|---|---|
| `<version>` | | Semantic version to tag HEAD with. Required unless `--push` is used alone. Accepted forms: `1.3`, `v1.3`, `1.3.4`, `v1.3.4` |
| `--push` | | Synchronize managed tags to `origin`. When used **without a version**, syncs every local managed tag to the remote (see [Sync all](#sync-all)). When used **with a version**, syncs only the managed tags for that version |
| `--force` | | Allow overwriting conflicting exact release tags on the remote (requires `--push`) |
| `--migrate` | | Migrate all managed release tags to the prefix style of the requested version |
| `--dry-run` | | Validate and plan all operations without making any mutations |
| `--quiet` | `-q` | Suppress per-tag output; emit only the final summary line |
| `--porcelain` | | Emit machine-readable output suitable for scripting (see below) |
| `--verbose` | `-v` | Emit additional operational detail (skipped tags, full HEAD SHA) |
| `--version` | `-V` | Show the application version |
| `--help` | `-h` | Show usage |

### Prefix style detection

`gitsem` inspects your existing managed release tags and enforces a consistent prefix style. If your repository already uses `v1.x` tags, passing `1.3.5` (unprefixed) will fail with a clear error. Use `--migrate` to migrate the entire tag history to the new style.

```sh
# Migrate from unprefixed to prefixed in one command
gitsem --migrate v1.3.5
```

### Floating vs exact tags

| Depth | Floating | Exact |
|---|---|---|
| `MAJOR.MINOR.PATCH` | `MAJOR`, `MAJOR.MINOR` | `MAJOR.MINOR.PATCH` |
| `MAJOR.MINOR` | `MAJOR` | `MAJOR.MINOR` |

Floating tags are always moved to the latest release. Exact release tags are pinned and will not be overwritten unless deleted manually.

### Remote synchronization

`--push` uses delete-then-push to keep remote floating tags aligned. Floating remote tags are updated automatically; conflicting exact remote release tags require `--force`.

#### Sync all

`gitsem --push` (with no version argument) synchronizes **every** local managed tag to the remote in a single command. No local tag creation or movement is performed — it is a pure remote conformance operation. Each tag is classified as floating or exact from the local inventory and the same conflict rules apply:

- floating remote tags are moved freely (no `--force` required)
- exact release tags that conflict on the remote require `--force`
- annotated remote tags are always rejected

```sh
# Sync all local managed tags to origin
gitsem --push

# Preview what would be pushed (remote conflicts still detected)
gitsem --dry-run --push

# Repair a conflicting exact remote tag and sync everything
gitsem --push --force
```

### Dry-run mode

`--dry-run` runs all validation and conflict checks without mutating anything — no local tags are created, moved, or deleted, and nothing is pushed to the remote. The output uses "would create / move / migrate / push" phrasing to make it clear no changes were made.

```sh
# Preview what gitsem would do for a new release
gitsem --dry-run 1.3.4

# Preview a style migration without committing to it
gitsem --dry-run --migrate v1.3.4

# Preview a full push in dry-run mode (remote conflicts are still detected)
gitsem --dry-run --push 1.3.4
```

### Output modes

| Mode | Flag | Per-tag lines | Skipped lines | Summary | HEAD SHA |
|---|---|---|---|---|---|
| Default | *(none)* | ✓ | — | ✓ | 12 chars |
| Verbose | `-v` | ✓ | ✓ | ✓ | full |
| Quiet | `-q` | — | — | ✓ | — |
| Porcelain | `--porcelain` | `ACTION tag` | always | `status ok` | `head <full-sha>` |

### Porcelain output

`--porcelain` emits one line per operation in a stable, space-separated format suitable for scripting. Every field is on its own line; the order is always fixed; `skipped` and `remote-skipped` lines are always present when applicable.

```
head <full-sha>
dry-run true          ← only present when --dry-run is used
switched <tag>
deleted <tag>
created <tag>
moved <tag>
skipped <tag>
pushed <tag>
remote-skipped <tag>
status ok             ← always the last line
```

Example — parse created tags in a shell script:

```sh
gitsem --porcelain 1.3.4 | awk '$1 == "created" { print $2 }'
```

Example — check for a specific tag in CI:

```sh
gitsem --porcelain --dry-run 1.3.4 | grep -q "^created 1.3.4" && echo "will create 1.3.4"
```

### Error format

All errors are written to stderr in a structured, machine-readable format:

```
error[token]: human-readable description
hint: one-line remedy           ← when available
```

The `token` maps directly to an exit code and is stable across versions:

| Token | Exit code | Meaning |
|---|---|---|
| `invalid-version` | `1` | Version string is not a recognised form |
| `unhealthy-repo` | `2` | Repository is not in a safe state for tag mutation |
| `style-mismatch` | `3` | Prefix style of the request differs from the repository |
| `tag-conflict` | `4` | A local tag conflict prevents safe operation |
| `remote-conflict` | `5` | A remote tag conflict prevents safe operation |
| `remote-permission` | `6` | Remote operation failed due to access or server policy |
| `git-execution` | `7` | Git subprocess failed for an unexpected reason |

Example — check the error token in a script:

```sh
output=$(gitsem v1.3.4 2>&1)
if echo "$output" | grep -q '^error\[style-mismatch\]'; then
  gitsem --migrate v1.3.4
fi
```

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
