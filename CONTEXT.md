# CONTEXT: gitsem

## Current project state
- v0.3.0 — full implementation complete; 162 tests passing
- `sync_all` / versionless `--push` feature implemented (pending wrap-up to v0.4.0)
- Source under `src/gitsem/`, tests under `tests/`
- Runnable via `uvx --from git+https://github.com/aheimsbakk/gitsem gitsem`

## Agreed product intent
- Build a Python 3.10+ CLI named `gitsem`
- Accept `1.3`, `1.3.4`, `v1.3`, or `v1.3.4`
- Preserve the repository's chosen tag prefix style instead of stripping `v`
- Support both `MAJOR.MINOR` and `MAJOR.MINOR.PATCH` release strategies
- Allow repositories to begin with `MAJOR.MINOR` releases and later transition to `MAJOR.MINOR.PATCH`
- Allow historical `MAJOR.MINOR` exact tags to become floating tags once patch releases begin for that minor line
- Ensure all managed tags for the requested version style point to `HEAD`
- Move floating tags locally when needed
- Optionally synchronize the same managed tags to `origin` with `--push`
- Detect existing prefixed versus unprefixed release-tag style and reject mismatches by default
- Allow style migration with `--migrate`, affecting all managed historical version tags
- Floating remote tags are moved automatically by `--push` (no `--force` required)
- Exact remote release tags that conflict require `--force` to overwrite
- Reject managed annotated tags rather than replacing them
- Package the tool so it is runnable through `uvx`

## Repository conventions established so far
- Source code belongs in `src/`
- Tests belong in `tests/`
- Tests must use `unittest`
- Implementation uses Python builtins and standard library only
- Documentation remains English-only
- No CI/CD files under `.github`
- Virtual environment at `.venv/` (created by uv)
- Use `uv`/`uvx` only — no pip references

## Module responsibilities (implemented)
- `errors.py`: typed domain errors with explicit exit codes (1–7); each error has a `token: str` class attribute and accepts `hint: str | None` keyword arg
- `versioning.py`: parse/validate version string, derive managed tag names, prefix helpers, `classify_tag_role()` for floating/exact classification from full local inventory
- `git_ops.py`: `subprocess.run`-based Git calls with timeouts; local and remote tag CRUD; detached-HEAD error carries a hint
- `tag_service.py`: orchestration — health check, style detection, switch migration, local tagging, remote sync; `ApplyResult` carries `head_commit` and `dry_run` fields; all execution helpers accept `dry_run: bool = False`; `sync_all()` synchronizes every local managed tag to remote without local mutations
- `cli.py`: `argparse`-based argument parsing, result formatting, exception-to-exit-code mapping; `version` is `nargs="?"` (optional); versionless `--push` routes to `sync_all()`; `_print_result`/`_print_human` accept `version_str: str | None`
- `__init__.py`: `importlib.metadata` version resolution
- `__main__.py`: `python -m gitsem` entry point

## CLI surface (implemented)
- `gitsem [--push] [--force] [--migrate] [--dry-run] [-q/--quiet] [--porcelain] [-v/--verbose] <version>`
- `gitsem --push [--force] [--dry-run] [-q/--quiet] [--porcelain]`  ← versionless sync-all
- `-h/--help`, `-V/--version`

## Output modes
| Mode | Flag | Per-tag lines | Skipped lines | Summary | HEAD SHA |
|------|------|--------------|---------------|---------|----------|
| Default | (none) | ✓ | ✗ | ✓ | 12 chars |
| Verbose | `-v` | ✓ | ✓ | ✓ | full |
| Quiet | `-q` | ✗ | ✗ | ✓ | hidden |
| Porcelain | `--porcelain` | `ACTION tag` (all) | always | `status ok` | `head <full-sha>` |

## Error format (implemented)
- GitsemError → `error[token]: message` on stderr, then optional `hint: ...` line
- Timeout/unexpected → `error[git-execution]: ...` on stderr
- Each error class has a `token` attribute (`invalid-version`, `unhealthy-repo`, `style-mismatch`, `tag-conflict`, `remote-conflict`, `remote-permission`, `git-execution`)

## Exit codes (implemented)
| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Invalid version string |
| 2 | Unhealthy repository state |
| 3 | Style mismatch |
| 4 | Local tag conflict |
| 5 | Remote tag conflict |
| 6 | Remote permission / policy error |
| 7 | Git execution error |

## Dry-run semantics (implemented)
- All validation and conflict checks run normally
- No local tags are created, moved, or deleted
- No remote pushes or deletes are performed
- Remote tags are still queried for conflict detection
- Switch migration is simulated in memory (no disk reload)
- `ApplyResult.dry_run = True`; `head_commit` is always populated
- Human output uses "would create / move / migrate / remove / push" verbs
- Summary appends `(dry run)` and uses "would be created / moved / migrated / pushed"

## Architectural direction
- Keep CLI parsing, semantic-version parsing, Git command execution, and tag orchestration in separate modules
- Use Python standard library only
- Use subprocess calls with explicit argument lists and timeouts for Git operations
- Treat repository health checks and style detection as explicit first-class behaviors
- Only modify recognized managed version tags; do not touch unrelated tags
- Treat detached HEAD as an unhealthy repository state for this tool
- Pre-flight annotated-tag check before any mutations

## Remote sync policy (clarified during implementation)
- Floating remote tags are moved freely by `--push` (delete-then-push without `--force`)
- Only exact remote release tags require `--force` to overwrite
- Annotated remote tags are always rejected, even with `--force`
- `gitsem --push` (no version) calls `sync_all()`: classifies every local managed tag via `versioning.classify_tag_role()` and applies same push rules to all

## Tag classification (floating vs exact from inventory alone)
- `MAJOR.MINOR.PATCH` → always exact
- `MAJOR` → always floating
- `MAJOR.MINOR` → floating if a same-prefix `MAJOR.MINOR.PATCH` sibling exists locally; exact otherwise
- Cross-prefix isolation: `v1.3` is not made floating by unprefixed `1.3.4`

## Open decisions for later implementation
- configurable remote beyond `origin`
- better handling of ambiguous non-release tag name collisions
