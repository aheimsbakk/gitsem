---
when: 2026-04-19T11:50:10Z
why: Provide a way to reconcile floating tags across the whole repository without re-tagging HEAD
what: Add --repair flag to gitsem CLI for automated floating-tag reconciliation
model: github-copilot/claude-sonnet-4.6
tags: [feature, cli, repair, floating-tags, versioning]
---

Added `--repair` mode (v0.5.0) that computes the correct target commit for every floating tag from the existing exact-tag inventory and creates or moves any that are missing or misplaced, without touching exact tags. Changes span `versioning.py` (`compute_floating_tag_targets()`), `tag_service.py` (`repair_floating()` + `_execute_repair_push()`), and `cli.py` (argument parsing and routing). Covered by 39 new tests across `test_versioning.py`, `test_tag_service.py`, and `test_integration.py` (201 total, all green).
