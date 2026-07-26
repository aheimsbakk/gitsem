# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.0] - 2026-04-19

- **why:** Provide a way to reconcile floating tags across the whole repository without re-tagging HEAD
- **model:** github-copilot/claude-sonnet-4.6
- **tags:** feature, cli, repair, floating-tags, versioning

### Added

- `compute_floating_tag_targets()` in `versioning.py` — derives correct target commits for every floating tag from the exact-tag inventory
- `repair_floating()` and `_execute_repair_push()` in `tag_service.py` — orchestrates repair flow with optional remote push
- `--repair` flag — reconciles all floating tags from the exact-tag inventory without re-tagging HEAD
- 39 new tests across `test_versioning.py`, `test_tag_service.py`, and `test_integration.py` (201 total)

## [0.4.1] - 2026-04-19

- **why:** --migrate better describes the operation than the ambiguous --switch
- **model:** github-copilot/claude-sonnet-4.6
- **tags:** rename, cli, refactor, patch

### Changed

- Renamed `--switch` flag to `--migrate` in `cli.py`, `tag_service.py`, all test files, and all documentation

## [0.4.0] - 2026-04-19

- **why:** Allow operators to sync every local managed tag to the remote with a single versionless command
- **model:** github-copilot/claude-sonnet-4.6
- **tags:** feature, sync-all, push, versioning, cli, tests

### Added

- `classify_tag_role()` in `versioning.py` — classifies any managed tag as 'exact' or 'floating' from the local inventory with cross-prefix isolation
- `sync_all()` in `tag_service.py` — pure remote-conformance operation that syncs all local managed tags to the remote
- Versionless `gitsem --push` routes to `sync_all()` for full remote synchronization
- `<version>` argument is now optional when `--push` is used alone
- 39 new tests across all four test files

## [0.3.0] - 2026-04-19

- **why:** Improve agent usability with structured error output, dry-run planning, and machine-readable porcelain mode
- **model:** github-copilot/claude-sonnet-4.6
- **tags:** cli, dry-run, porcelain, errors, agent-usability, tests

### Added

- `--dry-run` flag — validates and plans operations without mutations; conflict checks still run
- `-q` / `--quiet` flag — suppresses per-tag output, emits only the summary line
- `--porcelain` flag — machine-readable output with `ACTION tag` lines, `head <sha>`, and `status ok`
- Structured error output: `error[token]: message` with optional `hint:` line on stderr

### Changed

- `ApplyResult` now carries `head_commit` and `dry_run` fields
- Output modes evaluated in priority order: porcelain > quiet > verbose > default
- Human output uses "would create / move / migrate / push" phrasing in dry-run mode

## [0.2.0] - 2026-04-19

- **why:** Implement the full gitsem CLI tool as specified in BLUEPRINT.md
- **model:** github-copilot/claude-sonnet-4.6
- **tags:** feature, cli, git, semver, tagging, uv

### Added

- Initial implementation of `gitsem` — Docker-style floating semantic-version tags for Git repositories
- `pyproject.toml` with `uvx`-compatible packaging and `gitsem` console script entry point
- `scripts/bump-version.sh` and `scripts/validate-worklog.sh` automation scripts
- 79 passing tests across `test_versioning.py`, `test_tag_service.py`, `test_cli.py`, and `test_integration.py`
