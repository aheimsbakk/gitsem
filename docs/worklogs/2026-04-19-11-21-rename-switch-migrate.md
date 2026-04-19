---
when: 2026-04-19T11:21:30Z
why: --migrate better describes the operation than the ambiguous --switch
what: rename --switch to --migrate across all source, tests, and documentation
model: github-copilot/claude-sonnet-4.6
tags: [rename, cli, refactor, patch]
---

Renamed the `--switch` flag to `--migrate` throughout the entire codebase. Changes span `src/gitsem/cli.py` (argparse definition and routing guard), `src/gitsem/tag_service.py` (the `apply()` parameter `switch` → `migrate` and hint strings), all call sites in `tests/test_tag_service.py`, `tests/test_cli.py`, and `tests/test_integration.py`, and all documentation in `README.md`, `BLUEPRINT.md`, and `CONTEXT.md`. The README arguments table was also restructured to a `Long | Short | Description` column layout. Version bumped to v0.4.1.
