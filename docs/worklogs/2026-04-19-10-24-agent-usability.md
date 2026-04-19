---
when: 2026-04-19T10:24:49Z
why: improve agent-usability with structured error output, dry-run planning, and machine-readable porcelain mode
what: add --dry-run, -q/--quiet, --porcelain flags; structured error[token]/hint stderr; v0.3.0
model: github-copilot/claude-sonnet-4.6
tags: [cli, dry-run, porcelain, errors, agent-usability, tests]
---

Added `--dry-run` (plan without mutating), `-q/--quiet` (summary-only output), and `--porcelain` (machine-readable `ACTION tag` lines with `head <sha>` and `status ok`) flags to `cli.py`. Errors now emit `error[token]: message` with an optional `hint:` line on stderr; timeout and unexpected errors use `error[git-execution]:` format. `tag_service.py` already carried `dry_run` support and `ApplyResult.head_commit`; `cli.py` and all three test files were updated to cover the new surface. Version bumped from 0.2.0 to 0.3.0. Files touched: `src/gitsem/cli.py`, `src/gitsem/errors.py`, `src/gitsem/git_ops.py`, `src/gitsem/tag_service.py`, `tests/test_cli.py`, `tests/test_tag_service.py`, `tests/test_integration.py`, `CONTEXT.md`, `pyproject.toml`.
