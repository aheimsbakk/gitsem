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


def _err(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)


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
        "-v",
        "--verbose",
        action="store_true",
        help="Emit additional operational detail.",
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
    verbose: bool,
) -> None:
    """Print a concise, user-friendly operation summary."""
    any_output = False

    for tag in result.switched:
        _switch(f"migrated  {tag}")
        any_output = True
    for tag in result.deleted:
        _delete(f"removed   {tag}")
        any_output = True
    for tag in result.created:
        _ok(f"created   {tag}")
        any_output = True
    for tag in result.moved:
        _move(f"moved     {tag}")
        any_output = True
    if verbose:
        for tag in result.skipped:
            _skip(f"skipped   {tag}  (already at HEAD)")
            any_output = True
    for tag in result.pushed:
        _push(f"pushed    {tag}  → origin")
        any_output = True
    if verbose:
        for tag in result.remote_skipped:
            _skip(f"skipped   {tag}  (remote already at HEAD)")
            any_output = True

    if not any_output and not result.skipped and not result.remote_skipped:
        # Nothing happened at all — shouldn't normally occur, but be safe.
        print(f"Nothing to do for {version_str}.")
    elif not any_output:
        # Everything was already correct.
        print(f"All managed tags for {version_str} are already up to date.")
    else:
        # Print a blank line then a compact totals line.
        parts: list[str] = []
        if result.created:
            parts.append(f"{len(result.created)} created")
        if result.moved:
            parts.append(f"{len(result.moved)} moved")
        if result.switched:
            parts.append(f"{len(result.switched)} migrated")
        if result.pushed:
            parts.append(f"{len(result.pushed)} pushed")
        if result.skipped and not verbose:
            parts.append(f"{len(result.skipped)} skipped")
        if parts:
            print(f"\n  {', '.join(parts)}.")


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
        )
    except GitsemError as exc:
        _err(str(exc))
        sys.exit(exc.exit_code)
    except subprocess.TimeoutExpired as exc:
        _err(f"Git command timed out: {exc}")
        sys.exit(EXIT_GIT_EXECUTION)
    except Exception as exc:  # noqa: BLE001
        _err(f"Unexpected error: {exc}")
        sys.exit(EXIT_GIT_EXECUTION)

    _print_result(result, args.version, args.verbose)
    sys.exit(EXIT_OK)
