# BLUEPRINT: gitsem

## 1. Product definition
gitsem is a Python command-line application for applying Docker-like floating semantic-version tags to a Git repository. A single release command aligns either two or three tags on the same commit depending on the repository's versioning style.

Examples:
- `gitsem 1.3.4`
- `gitsem v1.3.4`
- `gitsem 1.3`
- `gitsem --push 1.3.4`
- `gitsem --switch v1.3.4`
- `gitsem --push --force 1.3.4`

The command must preserve the caller's prefix style. If the requested version is `v1.3.4`, managed tags are `v1`, `v1.3`, and `v1.3.4`. If the requested version is `1.3.4`, managed tags are `1`, `1.3`, and `1.3.4`.

The tool must detect the repository's current release-tag style and protect it by default. If the repository already uses prefixed release tags, an unprefixed request must fail with a clear error. If the repository already uses unprefixed release tags, a prefixed request must fail with a clear error. The user may pass `--switch` to migrate managed release tags to the requested style.

## 2. Primary goal
Make Git tags behave like Docker-style moving channels while preserving the repository's chosen prefix style:
- for `MAJOR.MINOR.PATCH` repositories, `MAJOR` always points to the newest released `MAJOR.x.y`, `MAJOR.MINOR` always points to the newest released `MAJOR.MINOR.y`, and `MAJOR.MINOR.PATCH` points to the exact release commit
- for `MAJOR.MINOR` repositories, `MAJOR` always points to the newest released `MAJOR.x`, and `MAJOR.MINOR` points to the exact release commit

Repositories may evolve from `MAJOR.MINOR` releases to `MAJOR.MINOR.PATCH` releases over time. That transition is allowed.

## 3. Functional scope
The first implementation must:
- run on Python 3.10 or newer
- be installable and runnable through `uvx`
- keep source code under `src/`
- keep tests under `tests/`
- use Python builtins and standard library only
- use `unittest` for the test suite
- operate on the current repository and target `HEAD`
- validate a stable semantic version in either `MAJOR.MINOR` or `MAJOR.MINOR.PATCH` form
- accept both prefixed and unprefixed version styles without stripping the prefix
- derive managed tags that match the chosen version depth and prefix style
- detect whether the repository currently uses prefixed or unprefixed managed release tags
- reject style mismatches unless `--switch` is explicitly requested
- migrate managed release tags to the requested style when `--switch` is used
- create missing local tags
- move existing floating local tags to `HEAD` when they already exist elsewhere
- operate only on healthy Git repositories

## 4. Tagging rules
For input `1.3.4`, gitsem must ensure all of the following point to the same commit:
- `1`
- `1.3`
- `1.3.4`

For input `v1.3.4`, gitsem must ensure all of the following point to the same commit:
- `v1`
- `v1.3`
- `v1.3.4`

For input `1.3`, gitsem must ensure all of the following point to the same commit:
- `1`
- `1.3`

For input `v1.3`, gitsem must ensure all of the following point to the same commit:
- `v1`
- `v1.3`

Expected behavior:
- If a managed floating tag does not exist locally, create it on `HEAD`
- If a managed floating tag already exists on another commit, move it to `HEAD`
- If the exact release tag does not exist locally, create it on `HEAD`
- If the exact release tag already exists on `HEAD`, treat the operation as idempotent
- If the exact release tag already exists on a different commit, fail by default instead of silently rewriting a specific release tag

Floating versus exact tags:
- In `MAJOR.MINOR.PATCH`, floating tags are `MAJOR` and `MAJOR.MINOR`; exact tag is `MAJOR.MINOR.PATCH`
- In `MAJOR.MINOR`, floating tag is `MAJOR`; exact tag is `MAJOR.MINOR`
- Prefix style is part of the tag identity, so `v1.3` and `1.3` are distinct tags

Depth transition rules:
- Release depth is determined by the version passed for the current command
- A repository may contain historical releases created with `MAJOR.MINOR` only and later begin using `MAJOR.MINOR.PATCH`
- When the current release uses `MAJOR.MINOR`, manage `MAJOR` as floating and `MAJOR.MINOR` as exact
- When the current release uses `MAJOR.MINOR.PATCH`, manage `MAJOR` and `MAJOR.MINOR` as floating and `MAJOR.MINOR.PATCH` as exact
- A historical `MAJOR.MINOR` exact tag may later become a floating tag once patch releases begin for that same minor line
- This repurposing is intentional and must be reflected consistently in local and optional remote synchronization

Style detection and switching:
- The tool must inspect existing managed release tags to detect whether the repository uses prefixed or unprefixed release tags
- If the detected style differs from the requested style, the command must fail with a warning and explain that another release-tag style is already in use
- `--switch` authorizes migration of managed release tags from one style to the other
- `--switch` must migrate all managed historical version tags in the repository to the requested style, not only the currently requested version family
- Style switching must update only managed version tags and must not touch unrelated non-version tags
- During a style switch, old-style managed tags must be replaced with equivalent new-style managed tags that point to the same intended commits after reconciliation

Safety boundaries:
- The tool must not interfere with tags that are not recognized as managed version tags
- If a tag collision or naming ambiguity prevents safe interpretation, the command must warn and exit
- If a managed version tag already exists as an annotated tag, the command must warn and exit rather than replace it
- Any suspicious or unsupported tag scenario should fail closed in v1 rather than guess

Initial implementation should use lightweight Git tags because they behave as simple movable references.

## 5. Remote synchronization
`--push` enables remote synchronization after local tags are correct.

When `--push` is used **with a version**, gitsem must:
- push the managed tags to the remote repository
- make the remote tag positions comply with the local tag positions
- update moved floating tags remotely as well as locally
- remain idempotent when local and remote tag state already match
- fail with a non-zero exit code if remote synchronization does not complete successfully

When `--push` is used **without a version**, gitsem performs a **full sync** of every local managed tag to the remote (`sync_all`):
- no local tags are created, moved, or deleted — pure remote conformance
- each local managed tag is classified as 'exact' or 'floating' from the full local inventory
- a `MAJOR.MINOR.PATCH` tag is always 'exact'; a `MAJOR` tag is always 'floating'; a `MAJOR.MINOR` tag is 'floating' if a same-prefix `MAJOR.MINOR.PATCH` sibling exists locally, 'exact' otherwise
- the same conflict rules apply as for version-scoped push (see below)
- `--switch` is meaningless without a version and must be rejected with a usage error

Initial remote scope:
- target the `origin` remote
- only touch the managed tags for the requested version and style
- do nothing remotely when `--push` is not supplied

Remote correction must use delete-then-push for managed tags. The implementation must be deterministic and must not report success before remote state is aligned with local state.

Remote conflict rules:
- If a managed exact tag already exists on the remote and points to a different commit than the local intended target, the command must warn and exit
- `--force` explicitly authorizes fixing conflicting managed remote tags
- Without `--force`, remote conflicts must never be rewritten
- If a managed remote tag is annotated, the command must warn and exit rather than replace it
- If remote deletion or push fails because of permissions or server-side policy, the command must exit with a clear failure message

## 6. Command contract
Planned CLI surface for the first version:

```text
gitsem [--push] [--force] [--switch] [--verbose] <version>
gitsem --push [--force] [--dry-run] [-q] [--porcelain]
gitsem --help
gitsem --version
```

Input rules:
- `<version>` is required when tagging HEAD; accepted forms are `1.3`, `1.3.4`, `v1.3`, and `v1.3.4`
- `<version>` may be omitted when `--push` is used alone (triggers `sync_all`)
- `--switch` requires a `<version>` argument; using it without a version is a usage error
- prerelease and build metadata are out of scope for the first version

Flags:
- `--push`: synchronize managed tags to `origin`
- `--force`: allow repair of conflicting managed remote tags
- `--switch`: migrate managed release tags to the requested prefix style
- `-v`, `--verbose`: emit more detailed operational output
- `-h`, `--help`: show usage
- `-V`, `--version`: show the application version

Exit behavior:
- exit `0` on success
- use distinct non-zero exit codes for invalid input, unhealthy repository state, style mismatch, tag conflict, remote conflict, permission failure, and generic Git execution failure

Output behavior:
- keep stdout concise, user-oriented, and with discrete visual flair only
- provide a friendly success summary of created, moved, skipped, deleted, and pushed managed tags
- increase operational detail when `--verbose` is enabled
- send actionable failure details to stderr

Usage help:
- CLI help must document the version formats, style detection behavior, `--switch`, `--push`, `--force`, and verbosity

## 7. Architecture plan
The application should be organized as a small, testable package with clear boundaries:

```text
src/gitsem/
  __init__.py
  __main__.py
  cli.py
  versioning.py
  git_ops.py
  tag_service.py
  errors.py
```

Module responsibilities:
- `cli.py`: parse arguments and map exceptions to exit codes
- `versioning.py`: validate version input, preserve prefix style, and derive managed tag names
- `git_ops.py`: safe Git subprocess operations with explicit argument lists
- `tag_service.py`: orchestration of local tagging, style detection, optional style switching, and optional remote sync
- `errors.py`: typed domain errors for predictable handling

Implementation guidance:
- use the Python standard library first
- execute Git through `subprocess.run(..., check=False, shell=False)`
- pass explicit argument lists only
- apply timeouts to Git subprocess calls
- keep Git command execution separate from version and policy logic
- model repository health checks explicitly before mutating tags
- classify managed version tags separately from unrelated tags

## 8. Packaging and execution
The finished tool must be runnable with `uvx`, so the package should expose a console script named `gitsem`. The repository should be prepared for standard Python packaging with metadata and an entry point that resolves to the CLI main function.

## 9. Testing strategy
Tests must use `unittest` and cover both logic and real Git behavior.

Unit tests:
- semantic-version validation for `MAJOR.MINOR` and `MAJOR.MINOR.PATCH`
- prefixed and unprefixed tag derivation
- derived tag set generation
- error mapping and CLI argument handling
- style detection and mismatch handling
- release-depth transition behavior from `MAJOR.MINOR` to `MAJOR.MINOR.PATCH`
- switch planning for prefixed and unprefixed repositories
- exit code mapping

Integration tests:
- create tags in a temporary local repository
- move existing floating tags to a newer commit
- confirm idempotent behavior when tags already match `HEAD`
- reject conflicting existing exact tags
- handle both prefixed and unprefixed repositories
- handle repositories that release only `MAJOR.MINOR` versions
- allow repositories to start with `MAJOR.MINOR` releases and later use `MAJOR.MINOR.PATCH`
- repurpose historical `MAJOR.MINOR` exact tags into floating tags when patch releases begin
- reject style mismatch unless `--switch` is used
- migrate managed tags when `--switch` is used
- synchronize against a temporary bare remote with `--push`
- keep `--push` idempotent when remote state already matches
- reject conflicting remote exact tags unless `--force` is used
- repair conflicting managed remote tags when `--force` is used
- fail cleanly on missing or inaccessible `origin`
- reject existing managed annotated tags locally and remotely
- verify local and remote refs match expected commit hashes after each scenario

## 10. Repository health requirements
The tool must only mutate tags when the repository is healthy enough for deterministic operation.

Minimum health checks for v1:
- current working directory is inside a Git repository
- `HEAD` resolves to a commit
- repository is not in detached HEAD state
- the repository is not in an obviously broken state for Git reference operations
- required Git commands for reading refs and creating or deleting tags succeed

If health checks fail, the tool must warn and exit before making tag changes.

## 11. Non-goals for v1
The first version does not include:
- prerelease or build-metadata tag handling
- support for tagging arbitrary commits other than `HEAD`
- configurable remote selection beyond `origin`
- GitHub release automation
- CI/CD configuration
- automatic interpretation of ambiguous non-release tag collisions
