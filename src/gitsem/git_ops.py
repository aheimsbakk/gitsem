"""Safe Git subprocess operations with explicit argument lists and timeouts."""

import subprocess
from dataclasses import dataclass

from .errors import GitExecutionError, RemotePermissionError, UnhealthyRepositoryError

# Default timeout for local Git commands (seconds).
_LOCAL_TIMEOUT = 30
# Default timeout for network Git commands (seconds).
_REMOTE_TIMEOUT = 60

_PERMISSION_KEYWORDS = ("Permission denied", "denied", "EPERM", "403", "401")


def _run(args: list[str], timeout: int = _LOCAL_TIMEOUT) -> subprocess.CompletedProcess[str]:
    """Execute a git command and return the completed process.

    Never raises on non-zero return codes — callers check returncode.
    """
    return subprocess.run(
        ["git"] + args,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _is_permission_error(stderr: str) -> bool:
    return any(kw.lower() in stderr.lower() for kw in _PERMISSION_KEYWORDS)


# ---------------------------------------------------------------------------
# Repository health
# ---------------------------------------------------------------------------


def health_check() -> str:
    """Assert the repository is in a state safe for tag mutation.

    Returns the HEAD commit hash on success.

    Raises:
        UnhealthyRepositoryError: on any health-check failure.
    """
    result = _run(["rev-parse", "--git-dir"])
    if result.returncode != 0:
        raise UnhealthyRepositoryError("Not inside a Git repository.")

    result = _run(["rev-parse", "HEAD"])
    if result.returncode != 0:
        raise UnhealthyRepositoryError("HEAD does not resolve to a commit.")
    head_commit = result.stdout.strip()

    # Detached HEAD: symbolic-ref exits non-zero when HEAD is not a branch ref.
    result = _run(["symbolic-ref", "--quiet", "HEAD"])
    if result.returncode != 0:
        raise UnhealthyRepositoryError(
            "Repository is in detached HEAD state.",
            hint="check out a branch before running gitsem",
        )

    return head_commit


def get_head_commit() -> str:
    """Return the full SHA-1 hash of HEAD.

    Raises:
        GitExecutionError: if the command fails.
    """
    result = _run(["rev-parse", "HEAD"])
    if result.returncode != 0:
        raise GitExecutionError(
            f"Failed to resolve HEAD: {result.stderr.strip()}"
        )
    return result.stdout.strip()


# ---------------------------------------------------------------------------
# Local tag operations
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TagInfo:
    """Information about a single Git tag."""

    commit: str    # Full SHA-1 of the commit the tag points to.
    annotated: bool


def list_local_tags() -> dict[str, TagInfo]:
    """Return a mapping of tag name → TagInfo for every local tag.

    Raises:
        GitExecutionError: if the underlying Git command fails.
    """
    result = _run(
        [
            "for-each-ref",
            "refs/tags",
            "--format=%(refname:short)\t%(objecttype)\t%(*objectname)\t%(objectname)",
        ]
    )
    if result.returncode != 0:
        raise GitExecutionError(
            f"Failed to list local tags: {result.stderr.strip()}"
        )

    tags: dict[str, TagInfo] = {}
    for line in result.stdout.splitlines():
        parts = line.split("\t", 3)
        if len(parts) != 4:
            continue
        name, obj_type, deref_commit, obj_hash = parts
        annotated = obj_type == "tag"
        # For annotated tags the dereferenced commit is in *objectname;
        # for lightweight tags the commit is objectname directly.
        commit = deref_commit if (annotated and deref_commit) else obj_hash
        tags[name] = TagInfo(commit=commit, annotated=annotated)

    return tags


def create_tag(name: str, commit: str) -> None:
    """Create a lightweight tag pointing to *commit*.

    Raises:
        GitExecutionError: if the command fails.
    """
    result = _run(["tag", name, commit])
    if result.returncode != 0:
        raise GitExecutionError(
            f"Failed to create tag {name!r}: {result.stderr.strip()}"
        )


def delete_local_tag(name: str) -> None:
    """Delete a local tag by name.

    Raises:
        GitExecutionError: if the command fails.
    """
    result = _run(["tag", "-d", name])
    if result.returncode != 0:
        raise GitExecutionError(
            f"Failed to delete local tag {name!r}: {result.stderr.strip()}"
        )


# ---------------------------------------------------------------------------
# Remote tag operations
# ---------------------------------------------------------------------------


def list_remote_tags(remote: str = "origin") -> dict[str, TagInfo]:
    """Return a mapping of tag name → TagInfo for every tag on *remote*.

    Uses ``git ls-remote --tags`` output:
    - A ``refs/tags/<name>^{}`` entry signals an annotated tag; its hash is
      the dereferenced commit.
    - A plain ``refs/tags/<name>`` entry without a corresponding ``^{}`` is a
      lightweight tag.

    Raises:
        GitExecutionError: if the command fails.
    """
    result = _run(["ls-remote", "--tags", remote], timeout=_REMOTE_TIMEOUT)
    if result.returncode != 0:
        raise GitExecutionError(
            f"Failed to list remote tags from {remote!r}: {result.stderr.strip()}"
        )

    raw: dict[str, str] = {}     # name → object hash (may be tag object for annotated)
    deref: dict[str, str] = {}   # name → commit hash (from ^{} lines)

    for line in result.stdout.splitlines():
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        obj_hash, ref = parts
        if ref.endswith("^{}"):
            tag_name = ref[len("refs/tags/"):-3]
            deref[tag_name] = obj_hash
        elif ref.startswith("refs/tags/"):
            tag_name = ref[len("refs/tags/"):]
            raw[tag_name] = obj_hash

    tags: dict[str, TagInfo] = {}
    for name, obj_hash in raw.items():
        if name in deref:
            tags[name] = TagInfo(commit=deref[name], annotated=True)
        else:
            tags[name] = TagInfo(commit=obj_hash, annotated=False)

    return tags


def push_tag(name: str, remote: str = "origin") -> None:
    """Push a single tag to *remote*.

    Raises:
        RemotePermissionError: on access-denied errors.
        GitExecutionError: on other failures.
    """
    result = _run(
        ["push", remote, f"refs/tags/{name}"],
        timeout=_REMOTE_TIMEOUT,
    )
    if result.returncode != 0:
        err = result.stderr.strip()
        if _is_permission_error(err):
            raise RemotePermissionError(
                f"Permission denied pushing tag {name!r} to {remote!r}: {err}"
            )
        raise GitExecutionError(
            f"Failed to push tag {name!r} to {remote!r}: {err}"
        )


def delete_remote_tag(name: str, remote: str = "origin") -> None:
    """Delete a tag from *remote*.

    Raises:
        RemotePermissionError: on access-denied errors.
        GitExecutionError: on other failures.
    """
    result = _run(
        ["push", remote, "--delete", f"refs/tags/{name}"],
        timeout=_REMOTE_TIMEOUT,
    )
    if result.returncode != 0:
        err = result.stderr.strip()
        if _is_permission_error(err):
            raise RemotePermissionError(
                f"Permission denied deleting remote tag {name!r} from {remote!r}: {err}"
            )
        raise GitExecutionError(
            f"Failed to delete remote tag {name!r} from {remote!r}: {err}"
        )
