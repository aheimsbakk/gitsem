"""CLI argument parsing and error-to-exit-code mapping."""

from __future__ import annotations

import argparse
import subprocess
import sys

from . import tag_service
from .errors import GitsemError

# ---------------------------------------------------------------------------
# Exit codes (matches errors.py exit_code attributes)
# ---------------------------------------------------------------------------
EXIT_OK = 0
EXIT_INVALID_INPUT = 1
EXIT_UNHEALTHY_REPO = 2
EXIT_STYLE_MISMATCH = 3
EXIT_TAG_CONFLICT = 4
EXIT_REMOTE_CONFLICT = 5
EXIT_REMOTE_PERMISSION = 6
EXIT_GIT_EXECUTION = 7

# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

_RESET = "\033[0m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_CYAN = "\033[36m"
_DIM = "\033[2m"


def _ok(msg: str) -> None:
    print(f"{_GREEN}✓{_RESET} {msg}")


def _move(msg: str) -> None:
    print(f"{_CYAN}→{_RESET} {msg}")


def _skip(msg: str) -> None:
    print(f"{_DIM}={_RESET} {msg}")


def _push(msg: str) -> None:
    print(f"{_YELLOW}↑{_RESET} {msg}")


def _switch(msg: str) -> None:
    print(f"{_CYAN}~{_RESET} {msg}")


def _delete(msg: str) -> None:
    print(f"{_DIM}-{_RESET} {msg}")


def _err(exc: Exception) -> None:
    """Emit a structured error to stderr.

    For GitsemError subclasses emits ``error[token]: message`` followed
    optionally by a ``hint: ...`` line.  For all other exceptions emits the
    plain ``error: message`` form.
    """
    if isinstance(exc, GitsemError):
        print(f"error[{exc.token}]: {exc}", file=sys.stderr)
        if exc.hint:
            print(f"hint: {exc.hint}", file=sys.stderr)
    else:
        print(f"error: {exc}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    from . import __version__

    parser = argparse.ArgumentParser(
        prog="gitsem",
        description=(
            "Apply Docker-style floating semantic-version tags to a Git repository.\n\n"
            "Accepted version forms:  1.3  v1.3  1.3.4  v1.3.4\n\n"
            "Style detection:\n"
            "  gitsem inspects existing managed release tags and enforces a\n"
            "  consistent prefix style (prefixed 'v1.x' or unprefixed '1.x').\n"
            "  A mismatch fails by default; use --switch to migrate.\n\n"
            "Floating tags:\n"
            "  For 1.3.4 → tags 1, 1.3, and 1.3.4 are all pointed at HEAD.\n"
            "  '1' and '1.3' move automatically; '1.3.4' is pinned.\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "version",
        help="Semantic version to tag HEAD with (e.g. 1.3.4 or v1.3.4).",
    )
    parser.add_argument(
        "--push",
        action="store_true",
        help="Synchronize managed tags to the 'origin' remote after local tagging.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow overwriting conflicting managed tags on the remote (requires --push).",
    )
    parser.add_argument(
        "--switch",
        action="store_true",
        help=(
            "Migrate all managed release tags to the prefix style of the requested "
            "version before applying new tags."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Validate and plan all operations without making any mutations. "
            "Conflict checks still run."
        ),
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress per-tag output; emit only the final summary line.",
    )
    parser.add_argument(
        "--porcelain",
        action="store_true",
        help=(
            "Emit machine-readable output: one ACTION TAG line per operation "
            "(skipped and remote-skipped always included), a head line, and a "
            "status line. Suitable for scripting."
        ),
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Emit additional operational detail (skipped tags, full HEAD SHA).",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


# ---------------------------------------------------------------------------
# Result formatting
# ---------------------------------------------------------------------------


def _print_result(
    result: tag_service.ApplyResult,
    version_str: str,
    *,
    verbose: bool,
    quiet: bool,
    porcelain: bool,
) -> None:
    """Print operation summary in the requested output mode.

    Modes (evaluated in priority order: porcelain > quiet > verbose > default):
      - porcelain: machine-readable lines; all actions always emitted to stdout.
      - quiet:     summary or no-op message only; no per-tag lines; no HEAD shown.
      - verbose:   per-tag lines + skipped/remote-skipped + summary + full HEAD SHA.
      - default:   per-tag lines (no skipped) + summary + 12-char HEAD SHA.
    """
    if porcelain:
        _print_porcelain(result)
        return

    _print_human(result, version_str, verbose=verbose, quiet=quiet)


def _print_porcelain(result: tag_service.ApplyResult) -> None:
    """Emit machine-readable output; all actions always included."""
    print(f"head {result.head_commit}")
    if result.dry_run:
        print("dry-run true")
    for tag in result.switched:
        print(f"switched {tag}")
    for tag in result.deleted:
        print(f"deleted {tag}")
    for tag in result.created:
        print(f"created {tag}")
    for tag in result.moved:
        print(f"moved {tag}")
    for tag in result.skipped:
        print(f"skipped {tag}")
    for tag in result.pushed:
        print(f"pushed {tag}")
    for tag in result.remote_skipped:
        print(f"remote-skipped {tag}")
    print("status ok")


def _print_human(
    result: tag_service.ApplyResult,
    version_str: str,
    *,
    verbose: bool,
    quiet: bool,
) -> None:
    """Emit human-readable output (default, quiet, or verbose)."""
    dry_run = result.dry_run
    head = result.head_commit

    # Verb phrasing varies for dry-run vs real operations.
    verb_create = "would create" if dry_run else "created  "
    verb_move   = "would move  " if dry_run else "moved    "
    verb_switch = "would migrate" if dry_run else "migrated "
    verb_delete = "would remove" if dry_run else "removed  "
    verb_push   = "would push  " if dry_run else "pushed   "

    if not quiet:
        for tag in result.switched:
            _switch(f"{verb_switch} {tag}")
        for tag in result.deleted:
            _delete(f"{verb_delete} {tag}")
        for tag in result.created:
            _ok(f"{verb_create} {tag}")
        for tag in result.moved:
            _move(f"{verb_move} {tag}")
        if verbose:
            for tag in result.skipped:
                _skip(f"skipped   {tag}  (already at HEAD)")
        for tag in result.pushed:
            _push(f"{verb_push}  {tag}  → origin")
        if verbose:
            for tag in result.remote_skipped:
                _skip(f"skipped   {tag}  (remote already at HEAD)")

    # Determine which summary branch to use.
    has_mutations = bool(
        result.created or result.moved or result.switched
        or result.deleted or result.pushed
    )
    has_skipped = bool(result.skipped or result.remote_skipped)

    if not has_mutations and not has_skipped:
        print(f"Nothing to do for {version_str}.")
    elif not has_mutations:
        print(f"All managed tags for {version_str} are already up to date.")
    else:
        parts: list[str] = []
        if result.created:
            noun = "would be created" if dry_run else "created"
            parts.append(f"{len(result.created)} {noun}")
        if result.moved:
            noun = "would be moved" if dry_run else "moved"
            parts.append(f"{len(result.moved)} {noun}")
        if result.switched:
            noun = "would be migrated" if dry_run else "migrated"
            parts.append(f"{len(result.switched)} {noun}")
        if result.pushed:
            noun = "would be pushed" if dry_run else "pushed"
            parts.append(f"{len(result.pushed)} {noun}")
        if result.skipped and not verbose:
            parts.append(f"{len(result.skipped)} skipped")
        if parts:
            suffix = " (dry run)" if dry_run else ""
            print(f"\n  {', '.join(parts)}{suffix}.")

    # HEAD SHA — suppressed in quiet mode and when head is unknown.
    if not quiet and head:
        if verbose:
            print(f"HEAD: {head}")
        else:
            print(f"HEAD: {head[:12]}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        result = tag_service.apply(
            args.version,
            switch=args.switch,
            push=args.push,
            force=args.force,
            verbose=args.verbose,
            dry_run=args.dry_run,
        )
    except GitsemError as exc:
        _err(exc)
        sys.exit(exc.exit_code)
    except subprocess.TimeoutExpired as exc:
        print(f"error[git-execution]: Git command timed out: {exc}", file=sys.stderr)
        sys.exit(EXIT_GIT_EXECUTION)
    except Exception as exc:  # noqa: BLE001
        print(f"error[git-execution]: Unexpected error: {exc}", file=sys.stderr)
        sys.exit(EXIT_GIT_EXECUTION)

    _print_result(
        result,
        args.version,
        verbose=args.verbose,
        quiet=args.quiet,
        porcelain=args.porcelain,
    )
    sys.exit(EXIT_OK)
