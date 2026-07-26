# CODEBASE: gitsem

## Package overview

```
gitsem — Docker-like floating semantic-version tags for Git repositories.

A Python 3.10+ CLI tool that applies moving channel tags to your current Git
commit, mirroring how Docker manages `latest`, `1`, and `1.3` alongside `1.3.4`.
A single release command keeps all related tags aligned on the same commit,
moving floating tags automatically and pinning exact release tags.
```

## Version and packaging

- **Version:** 0.5.0
- **Python:** >= 3.10
- **Build system:** setuptools (no external runtime dependencies)
- **Entry point:** `gitsem = "gitsem.cli:main"`
- **Runnable via:** `uvx --from git+https://github.com/aheimsbakk/gitsem gitsem`
- **License:** MIT

## Repository layout

```
src/gitsem/
  __init__.py    # Package version via importlib.metadata
  __main__.py    # python -m gitsem entry point
  cli.py         # Argument parsing, result formatting, exit-code mapping
  versioning.py  # Version validation, prefix preservation, tag derivation
  git_ops.py     # Git subprocess operations with timeouts
  tag_service.py # Orchestration: style detection, tagging, switching, push
  errors.py      # Typed domain errors with exit codes
tests/
  test_versioning.py   # Unit tests for versioning logic (423 lines)
  test_tag_service.py  # Unit tests for tag orchestration, mocked Git (927 lines)
  test_cli.py          # Unit tests for CLI parsing and output modes (535 lines)
  test_integration.py  # Integration tests against real temporary Git repos (933 lines)
scripts/
  bump-version.sh       # Bump patch / minor / major in pyproject.toml
  validate-worklog.sh   # Validate docs/worklogs/ front-matter schema
docs/worklogs/
  2026-02-14-*.md       # Agent worklog files
```

## Module responsibilities

### `errors.py` — Typed domain errors

Seven error classes, each with a fixed `exit_code` and `token`:

| Class | Exit code | Token |
|---|---|---|
| `InvalidVersionError` | 1 | `invalid-version` |
| `UnhealthyRepositoryError` | 2 | `unhealthy-repo` |
| `StyleMismatchError` | 3 | `style-mismatch` |
| `TagConflictError` | 4 | `tag-conflict` |
| `RemoteConflictError` | 5 | `remote-conflict` |
| `RemotePermissionError` | 6 | `remote-permission` |
| `GitExecutionError` | 7 | `git-execution` |

All accept `hint: str | None` for a one-line remedy shown to humans and agents.

### `versioning.py` — Semantic version logic

- `ParsedVersion(prefix, major, minor, patch)` — frozen dataclass
- `parse_version(str) → ParsedVersion` — validates and parses `MAJOR.MINOR` / `MAJOR.MINOR.PATCH` with optional `v` prefix
- `derive_managed_tags(ParsedVersion) → list[str]` — ordered list of all managed tag names
- `get_floating_tags(ParsedVersion) → list[str]` — all except the exact tag
- `get_exact_tag(ParsedVersion) → str` — the pinned release tag
- `is_managed_version_tag(str) → bool` — regex match against `v?\d+(\.\d+(\.\d+)?)?`
- `get_tag_prefix(str) → str` — returns `"v"` or `""`
- `switch_tag_prefix(str, str) → str` — replaces prefix
- `classify_tag_role(str, dict) → "exact" | "floating"` — classifies from full inventory with cross-prefix isolation
- `compute_floating_tag_targets(dict) → dict[str, str]` — pure function deriving correct commit for every floating tag from exact-tag inventory

### `git_ops.py` — Git subprocess operations

- `_run(args, timeout)` — core subprocess runner (no raise on non-zero)
- `health_check() → str` — validates repo is in a safe state, returns HEAD commit
- `get_head_commit() → str` — resolves HEAD SHA
- `list_local_tags() → dict[str, TagInfo]` — all local tags with commit + annotated flag
- `create_tag(name, commit)` — lightweight tag creation
- `delete_local_tag(name)` — lightweight tag deletion
- `list_remote_tags(remote) → dict[str, TagInfo]` — all remote tags via `ls-remote`
- `push_tag(name, remote)` — push tag to remote
- `delete_remote_tag(name, remote)` — delete tag from remote

Timeouts: 30s local, 60s remote. Permission errors detected via keyword matching.

### `tag_service.py` — Orchestration layer

- `ApplyResult` — dataclass tracking created, moved, skipped, deleted, switched, pushed, remote_skipped operations plus `head_commit` and `dry_run`
- `detect_style(dict) → "v" | "" | None` — infers prefix style, raises on mixed
- `_execute_switch(new_prefix, managed_tags, result, dry_run)` — migrates all tags to new prefix
- `_execute_version_tags(parsed, managed_tags, head, result, dry_run)` — creates/moves tags for a version
- `_execute_push(parsed, head, force, result, remote, dry_run)` — syncs version tags to remote
- `_execute_repair_push(targets, result, remote, dry_run)` — pushes floating tag corrections
- `apply(version_str, migrate, push, force, verbose, dry_run) → ApplyResult` — main tagging flow
- `sync_all(force, dry_run, remote) → ApplyResult` — versionless `--push` syncs all managed tags
- `repair_floating(push, dry_run, remote) → ApplyResult` — reconciles floating tags from exact-tag inventory

### `cli.py` — CLI entry point

- `_build_parser() → ArgumentParser` — defines all flags and arguments
- `_print_result(result, version_str, verbose, quiet, porcelain)` — output routing by mode
- `_print_porcelain(result)` — machine-readable `ACTION tag` lines
- `_print_human(result, version_str, verbose, quiet)` — colored human-readable output
- `main(argv) → None` — entry point with error-to-exit-code mapping

Output modes (priority: porcelain > quiet > verbose > default):

| Mode | Flag | Per-tag | Skipped | Summary | HEAD |
|---|---|---|---|---|---|
| Default | — | yes | no | yes | 12 chars |
| Verbose | `-v` | yes | yes | yes | full |
| Quiet | `-q` | no | no | yes | hidden |
| Porcelain | `--porcelain` | yes (all) | always | `status ok` | `head <full-sha>` |

### `__init__.py` — Version resolution

Uses `importlib.metadata.version("gitsem")` with fallback to `"0.0.0+dev"`.

### `__main__.py` — Module execution

Imports and calls `cli.main()` for `python -m gitsem`.

## CLI surface

```
gitsem [--push] [--force] [--migrate] [--dry-run] [-q] [--porcelain] [-v] <version>
gitsem --push [--force] [--dry-run] [-q] [--porcelain]
gitsem --repair [--push] [--dry-run] [-q] [--porcelain] [-v]
gitsem --help
gitsem --version
```

### Flags

| Flag | Short | Description |
|---|---|---|
| `--push` | | Sync managed tags to `origin` |
| `--force` | | Overwrite conflicting exact remote tags (requires `--push`) |
| `--migrate` | | Migrate all managed tags to requested prefix style |
| `--repair` | | Reconcile floating tags from exact-tag inventory |
| `--dry-run` | | Validate and plan without mutations |
| `--quiet` | `-q` | Suppress per-tag output |
| `--porcelain` | | Machine-readable output |
| `--verbose` | `-v` | Additional operational detail |
| `--version` | `-V` | Show version |
| `--help` | `-h` | Show usage |

## Tag rules

### Floating vs exact

| Depth | Floating | Exact |
|---|---|---|
| `MAJOR.MINOR.PATCH` | `MAJOR`, `MAJOR.MINOR` | `MAJOR.MINOR.PATCH` |
| `MAJOR.MINOR` | `MAJOR` | `MAJOR.MINOR` |

### Classification from inventory

- `MAJOR.MINOR.PATCH` → always exact
- `MAJOR` → always floating
- `MAJOR.MINOR` → floating if same-prefix `MAJOR.MINOR.PATCH` sibling exists; exact otherwise
- Cross-prefix isolation: `v1.3` is not made floating by unprefixed `1.3.4`

### Repair targets

- `MAJOR` float → highest `(minor, patch)` in that `(prefix, major)` family
- `MAJOR.MINOR` float → highest patch among same-prefix `MAJOR.MINOR.PATCH` exact tags
- `MAJOR.MINOR` exact tags contribute to MAJOR float but do not spawn their own MAJOR.MINOR float

## Testing

- **Framework:** `unittest` (standard library)
- **Total tests:** 201
- **Run:** `uv run python -m unittest discover -s tests -v`
- **Test files:**
  - `test_versioning.py` — version parsing, tag derivation, classification, floating targets
  - `test_tag_service.py` — style detection, apply flow, sync_all, repair_floating, dry-run
  - `test_cli.py` — argument parsing, exit codes, output modes (porcelain, quiet, verbose)
  - `test_integration.py` — real Git repos, tagging, pushing, repair, style migration

## Operational semantics

### Dry-run
All validation and conflict checks run normally. No local tags are created, moved, or deleted. No remote pushes or deletes. Remote tags are still queried for conflict detection. Output uses "would create / move / migrate / push" phrasing.

### Style detection
Inspects existing managed release tags. All prefixed → `"v"`, all unprefixed → `""`, mixed → raises `TagConflictError`, none → `None` (greenfield).

### Push (versioned)
Syncs only the managed tags for the requested version. Floating remote tags are updated freely. Exact remote tags require `--force`. Annotated remote tags are always rejected.

### Push (versionless — sync_all)
Synchronizes every local managed tag to remote. No local mutations. Each tag is classified as exact or floating from the local inventory. Same conflict rules apply.

### Repair
Reconciles all floating tags from the exact-tag inventory. Creates missing floating tags, moves stale ones, skips correct ones. Exact tags are never touched. Mutually exclusive with `<version>`, `--migrate`, and `--force`.

## Health checks

Before any mutation, the tool validates:
1. Current directory is inside a Git repository
2. `HEAD` resolves to a commit
3. Repository is not in detached HEAD state

If any check fails, the tool exits with code 2 and a descriptive error.
