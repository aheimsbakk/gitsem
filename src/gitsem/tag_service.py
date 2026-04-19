"""Orchestration of local tagging, style detection, style switching, and remote sync."""

from dataclasses import dataclass, field

from . import git_ops, versioning
from .errors import (
    RemoteConflictError,
    StyleMismatchError,
    TagConflictError,
)
from .versioning import ParsedVersion


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------


@dataclass
class ApplyResult:
    """Summary of all tag operations performed during a single run."""

    created: list[str] = field(default_factory=list)
    moved: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    switched: list[str] = field(default_factory=list)
    pushed: list[str] = field(default_factory=list)
    remote_skipped: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Style detection
# ---------------------------------------------------------------------------


def detect_style(
    managed_tags: dict[str, git_ops.TagInfo],
) -> str | None:
    """Infer the repository's release-tag prefix style.

    Returns:
        'v'  – all managed tags are prefixed.
        ''   – all managed tags are unprefixed.
        None – no managed tags exist yet (greenfield repository).

    Raises:
        TagConflictError: if the repository has a mix of prefixed and
            unprefixed managed tags (an ambiguous, unsafe state).
    """
    if not managed_tags:
        return None

    prefixed = [n for n in managed_tags if n.startswith("v")]
    unprefixed = [n for n in managed_tags if not n.startswith("v")]

    if prefixed and unprefixed:
        raise TagConflictError(
            "Repository has a mix of prefixed (e.g. v1.3) and unprefixed "
            "(e.g. 1.3) managed version tags. This state is ambiguous and "
            "unsafe. Please resolve the inconsistency manually."
        )

    return "v" if prefixed else ""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_managed_subset(
    all_tags: dict[str, git_ops.TagInfo],
) -> dict[str, git_ops.TagInfo]:
    """Filter *all_tags* to only those that are recognized managed version tags."""
    return {
        name: info
        for name, info in all_tags.items()
        if versioning.is_managed_version_tag(name)
    }


def _assert_not_annotated(name: str, info: git_ops.TagInfo, context: str) -> None:
    if info.annotated:
        raise TagConflictError(
            f"Tag {name!r} is an annotated tag{context}. "
            "gitsem only manages lightweight tags. "
            "Delete or convert the annotated tag manually."
        )


def _execute_switch(
    new_prefix: str,
    managed_tags: dict[str, git_ops.TagInfo],
    result: ApplyResult,
) -> None:
    """Migrate all managed tags from their current prefix style to *new_prefix*.

    For each old-style tag a new-style tag is created pointing to the same
    commit, then the old-style tag is deleted.
    """
    # Guard: no annotated managed tags may be migrated.
    for name, info in managed_tags.items():
        _assert_not_annotated(name, info, " — cannot migrate annotated tags")

    # Build migration map: old_name → (new_name, commit).
    migration: dict[str, tuple[str, str]] = {}
    for name, info in managed_tags.items():
        new_name = versioning.switch_tag_prefix(name, new_prefix)
        migration[name] = (new_name, info.commit)

    # Guard: no collision where a new-style target already exists with a
    # different commit (can happen if partially migrated externally).
    for old_name, (new_name, commit) in migration.items():
        if new_name in managed_tags and new_name != old_name:
            existing_commit = managed_tags[new_name].commit
            if existing_commit != commit:
                raise TagConflictError(
                    f"Cannot migrate {old_name!r} → {new_name!r}: "
                    f"target already exists at a different commit "
                    f"({existing_commit[:8]} vs {commit[:8]})."
                )

    # Create new-style tags first (fail before deleting anything on error).
    for old_name, (new_name, commit) in migration.items():
        if new_name not in managed_tags:
            git_ops.create_tag(new_name, commit)
            result.switched.append(new_name)

    # Delete old-style tags.
    for old_name, (new_name, _) in migration.items():
        if old_name != new_name:
            git_ops.delete_local_tag(old_name)
            result.deleted.append(old_name)


def _execute_version_tags(
    parsed: ParsedVersion,
    managed_tags: dict[str, git_ops.TagInfo],
    head_commit: str,
    result: ApplyResult,
) -> None:
    """Create or move managed tags for the given version."""
    floating = versioning.get_floating_tags(parsed)
    exact = versioning.get_exact_tag(parsed)

    # Pre-flight: reject any annotated managed tags that would be touched,
    # before making any mutations.
    for tag in [exact] + floating:
        if tag in managed_tags:
            _assert_not_annotated(tag, managed_tags[tag], "")

    # --- Exact tag --------------------------------------------------------
    if exact in managed_tags:
        info = managed_tags[exact]
        if info.commit == head_commit:
            result.skipped.append(exact)
        else:
            raise TagConflictError(
                f"Exact release tag {exact!r} already exists on commit "
                f"{info.commit[:8]}, which is not HEAD ({head_commit[:8]}). "
                "gitsem will not silently overwrite an exact release tag. "
                "If this was intentional, delete the tag manually first."
            )
    else:
        git_ops.create_tag(exact, head_commit)
        result.created.append(exact)

    # --- Floating tags ----------------------------------------------------
    for tag in floating:
        if tag in managed_tags:
            info = managed_tags[tag]
            if info.commit == head_commit:
                result.skipped.append(tag)
            else:
                git_ops.delete_local_tag(tag)
                git_ops.create_tag(tag, head_commit)
                result.moved.append(tag)
        else:
            git_ops.create_tag(tag, head_commit)
            result.created.append(tag)


def _execute_push(
    parsed: ParsedVersion,
    head_commit: str,
    force: bool,
    result: ApplyResult,
    remote: str = "origin",
) -> None:
    """Synchronize the managed tags for *parsed* to *remote*.

    Uses delete-then-push for tags that exist on the remote at a different
    commit.  Requires *force* to overwrite conflicting managed remote tags.
    Refuses to touch annotated remote tags under all circumstances.
    """
    managed_tag_names = versioning.derive_managed_tags(parsed)
    exact_tag = versioning.get_exact_tag(parsed)

    remote_tags = git_ops.list_remote_tags(remote)

    for tag in managed_tag_names:
        is_exact = tag == exact_tag

        if tag in remote_tags:
            remote_info = remote_tags[tag]
            if remote_info.commit == head_commit:
                result.remote_skipped.append(tag)
                continue
            # Remote tag points to a different commit — always reject annotated.
            if remote_info.annotated:
                raise RemoteConflictError(
                    f"Remote tag {tag!r} is an annotated tag at a different "
                    "commit. gitsem will not replace annotated remote tags. "
                    "Remove it manually on the remote first."
                )
            # Exact release tags are pinned: require --force to overwrite.
            if is_exact and not force:
                raise RemoteConflictError(
                    f"Remote exact release tag {tag!r} exists at a different "
                    f"commit ({remote_info.commit[:8]}). "
                    "Use --force to overwrite conflicting managed remote tags."
                )
            # Floating tags or force=True: delete-then-push.
            git_ops.delete_remote_tag(tag, remote)
            git_ops.push_tag(tag, remote)
            result.pushed.append(tag)
        else:
            git_ops.push_tag(tag, remote)
            result.pushed.append(tag)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def apply(
    version_str: str,
    *,
    switch: bool,
    push: bool,
    force: bool,
    verbose: bool,
) -> ApplyResult:
    """Apply managed version tags to HEAD.

    Steps:
        1. Repository health check.
        2. Version parsing.
        3. Local tag inventory and style detection.
        4. Style-mismatch guard (or migration when *switch* is True).
        5. Local tag creation / movement.
        6. Optional remote synchronization (when *push* is True).

    Returns:
        ApplyResult describing every operation performed.

    Raises:
        Any subclass of GitsemError on failure.
    """
    result = ApplyResult()

    # 1. Health check — also returns HEAD commit for free.
    head_commit = git_ops.health_check()

    # 2. Parse version.
    parsed = versioning.parse_version(version_str)

    # 3. Inventory.
    local_tags = git_ops.list_local_tags()
    managed_tags = _get_managed_subset(local_tags)

    # 4. Style detection and mismatch guard.
    detected_style = detect_style(managed_tags)

    if detected_style is not None and detected_style != parsed.prefix:
        if not switch:
            existing_desc = (
                "prefixed (e.g. v1.2.3)" if detected_style == "v" else "unprefixed (e.g. 1.2.3)"
            )
            requested_desc = "prefixed" if parsed.prefix == "v" else "unprefixed"
            raise StyleMismatchError(
                f"Repository already uses {existing_desc} release tags, but "
                f"{version_str!r} is {requested_desc}. "
                "Use --switch to migrate all managed tags to the new style."
            )

        # Perform switch migration.
        _execute_switch(parsed.prefix, managed_tags, result)

        # Reload tag inventory so subsequent steps see the migrated state.
        local_tags = git_ops.list_local_tags()
        managed_tags = _get_managed_subset(local_tags)

    # 5. Apply version tags locally.
    _execute_version_tags(parsed, managed_tags, head_commit, result)

    # 6. Remote synchronization.
    if push:
        _execute_push(parsed, head_commit, force, result)

    return result
