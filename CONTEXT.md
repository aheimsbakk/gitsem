# CONTEXT: gitsem

## Current project state
- Greenfield Python project
- Repository currently has minimal documentation only
- `BLUEPRINT.md` now defines the initial product scope and architecture

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
- Refuse conflicting remote exact tags unless `--force` is provided
- Reject managed annotated tags rather than replacing them
- Package the tool so it is runnable through `uvx`

## Repository conventions established so far
- Source code belongs in `src/`
- Tests belong in `tests/`
- Tests must use `unittest`
- Implementation must use Python builtins and standard library only unless explicitly approved later
- Documentation remains English-only
- No CI/CD files under `.github`

## CLI requirements established so far
- Support `-h` and `--help`
- Support `-V` and `--version`
- Support `-v` and `--verbose`
- Support `--push`, `--force`, and `--switch`
- Use friendly but concise CLI summaries, with discrete visual flair and more detail in verbose mode
- Prefer distinct exit codes suitable for automation

## Architectural direction
- Keep CLI parsing, semantic-version parsing, Git command execution, and tag orchestration in separate modules
- Use Python standard library only unless the user explicitly approves an exception
- Use subprocess calls with explicit argument lists and timeouts for Git operations
- Treat repository health checks and style detection as explicit first-class behaviors
- Only modify recognized managed version tags; do not touch unrelated tags
- Treat detached HEAD as an unhealthy repository state for this tool

## Open decisions for later implementation
- whether to expose a dry-run mode in a later version
- exact numeric exit-code assignments
- better handling of ambiguous non-release tag name collisions in a later version
