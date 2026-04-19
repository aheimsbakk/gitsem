# CONTEXT: gitsem

## Current project state
- v0.1.1 — initial implementation complete, all 79 tests passing
- Source under `src/gitsem/`, tests under `tests/`
- Installable via `uvx gitsem` or `pip install gitsem`

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
- Allow style migration with `--switch`, affecting all managed historical version tags
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

## Module responsibilities (implemented)
- `errors.py`: typed domain errors with explicit exit codes (1–7)
- `versioning.py`: parse/validate version string, derive managed tag names, prefix helpers
- `git_ops.py`: `subprocess.run`-based Git calls with timeouts; local and remote tag CRUD
- `tag_service.py`: orchestration — health check, style detection, switch migration, local tagging, remote sync
- `cli.py`: `argparse`-based argument parsing, result formatting, exception-to-exit-code mapping
- `__init__.py`: `importlib.metadata` version resolution
- `__main__.py`: `python -m gitsem` entry point

## CLI surface (implemented)
- `gitsem [--push] [--force] [--switch] [-v/--verbose] <version>`
- `-h/--help`, `-V/--version`

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

## Open decisions for later implementation
- dry-run mode
- configurable remote beyond `origin`
- better handling of ambiguous non-release tag name collisions
