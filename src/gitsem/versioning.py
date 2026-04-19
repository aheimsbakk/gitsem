"""Semantic version validation, prefix preservation, and managed tag derivation."""

import re
from dataclasses import dataclass

from .errors import InvalidVersionError

# Accepts 1.3 / v1.3 / 1.3.4 / v1.3.4 — no pre-release or build metadata.
_VERSION_RE = re.compile(r"^(v?)(\d+)\.(\d+)(?:\.(\d+))?$")

# Pattern that identifies any managed version tag (with or without 'v' prefix).
_MANAGED_TAG_RE = re.compile(r"^v?\d+(\.\d+(\.\d+)?)?$")

# Matches any managed tag including MAJOR-only (e.g. '1', 'v1', '1.3', 'v1.3.4').
_TAG_DEPTH_RE = re.compile(r"^(v?)(\d+)(?:\.(\d+)(?:\.(\d+))?)?$")


@dataclass(frozen=True)
class ParsedVersion:
    """Immutable representation of a parsed semantic version string."""

    prefix: str        # '' or 'v'
    major: int
    minor: int
    patch: int | None  # None for MAJOR.MINOR style


def parse_version(version_str: str) -> ParsedVersion:
    """Parse and validate a version string, preserving prefix style.

    Raises:
        InvalidVersionError: if the string does not match an accepted form.
    """
    match = _VERSION_RE.fullmatch(version_str)
    if not match:
        raise InvalidVersionError(
            f"Invalid version {version_str!r}. "
            "Accepted forms: 1.3  v1.3  1.3.4  v1.3.4"
        )
    prefix = match.group(1)
    major = int(match.group(2))
    minor = int(match.group(3))
    patch = int(match.group(4)) if match.group(4) is not None else None
    return ParsedVersion(prefix=prefix, major=major, minor=minor, patch=patch)


def derive_managed_tags(parsed: ParsedVersion) -> list[str]:
    """Return the ordered list of managed tag names for the given version.

    For MAJOR.MINOR.PATCH: [MAJOR, MAJOR.MINOR, MAJOR.MINOR.PATCH]
    For MAJOR.MINOR:       [MAJOR, MAJOR.MINOR]

    Prefix style is preserved throughout.
    """
    p = parsed.prefix
    tags: list[str] = [
        f"{p}{parsed.major}",
        f"{p}{parsed.major}.{parsed.minor}",
    ]
    if parsed.patch is not None:
        tags.append(f"{p}{parsed.major}.{parsed.minor}.{parsed.patch}")
    return tags


def get_floating_tags(parsed: ParsedVersion) -> list[str]:
    """Return only the floating (moveable) tags — everything except the exact tag."""
    return derive_managed_tags(parsed)[:-1]


def get_exact_tag(parsed: ParsedVersion) -> str:
    """Return the exact (pinned) release tag name."""
    return derive_managed_tags(parsed)[-1]


def is_managed_version_tag(name: str) -> bool:
    """Return True if *name* looks like a managed version tag.

    Managed version tags match: optional 'v' followed by MAJOR, MAJOR.MINOR,
    or MAJOR.MINOR.PATCH — nothing else.
    """
    return bool(_MANAGED_TAG_RE.fullmatch(name))


def get_tag_prefix(name: str) -> str:
    """Return 'v' if *name* starts with 'v', otherwise ''."""
    return "v" if name.startswith("v") else ""


def switch_tag_prefix(name: str, new_prefix: str) -> str:
    """Return *name* with its prefix replaced by *new_prefix*."""
    bare = name[1:] if name.startswith("v") else name
    return new_prefix + bare


def compute_floating_tag_targets(managed_tags: dict[str, str]) -> dict[str, str]:
    """Compute the correct target commit for every floating tag that should exist.

    Given the full managed tag inventory (*managed_tags*, mapping tag name →
    commit hash), this function classifies every tag as exact or floating, then
    derives — from the exact tags only — where each floating tag must point.

    Rules:
    - MAJOR floating tag: points to the commit of the highest-version exact tag
      in that (prefix, MAJOR) family.  Sort key is (minor, patch) where
      ``patch = -1`` for MAJOR.MINOR exact tags (no patch component).
    - MAJOR.MINOR floating tag: points to the commit of the highest patch among
      same-prefix MAJOR.MINOR.PATCH exact tags in that minor family.  A
      MAJOR.MINOR tag that is itself exact (no patch children) does *not* spawn
      a floating MAJOR.MINOR above itself — it *is* the exact.

    Cross-prefix isolation is preserved: ``v1.3.4`` does not influence the
    target of the unprefixed ``1`` floating tag, and vice versa.

    Returns:
        A dict mapping each floating tag name that *should* exist to the
        commit it must point to.  An empty dict means nothing is needed
        (e.g. the inventory is empty or has no exact tags).
    """
    if not managed_tags:
        return {}

    # Separate exact from floating using the full inventory for classification.
    exact_tags: dict[str, str] = {
        name: commit
        for name, commit in managed_tags.items()
        if classify_tag_role(name, managed_tags) == "exact"
    }

    # Parse exact tags into structured tuples for numeric comparison.
    # Each entry: (prefix, major, minor, patch_or_None, commit)
    parsed: list[tuple[str, int, int, int | None, str]] = []
    for name, commit in exact_tags.items():
        m = _TAG_DEPTH_RE.fullmatch(name)
        if m is None:
            continue
        prefix = m.group(1)
        major_s, minor_s, patch_s = m.group(2), m.group(3), m.group(4)
        if minor_s is None:
            continue  # MAJOR-only tags are always floating — never exact
        major = int(major_s)
        minor = int(minor_s)
        patch = int(patch_s) if patch_s is not None else None
        parsed.append((prefix, major, minor, patch, commit))

    # MAJOR floating: highest (minor, patch) in each (prefix, major) family wins.
    # MAJOR.MINOR exact tags use patch=-1 so they rank below any MAJOR.MINOR.PATCH
    # of the same minor but above a lower minor entirely.
    major_best: dict[tuple[str, int], tuple[tuple[int, int], str]] = {}
    for prefix, major, minor, patch, commit in parsed:
        key = (prefix, major)
        sort_key = (minor, patch if patch is not None else -1)
        if key not in major_best or sort_key > major_best[key][0]:
            major_best[key] = (sort_key, commit)

    # MAJOR.MINOR floating: highest patch in each (prefix, major, minor) family wins.
    # Only MAJOR.MINOR.PATCH exact tags contribute — a MAJOR.MINOR exact tag is the
    # exact itself and does not create a floating MAJOR.MINOR above it.
    minor_best: dict[tuple[str, int, int], tuple[int, str]] = {}
    for prefix, major, minor, patch, commit in parsed:
        if patch is None:
            continue
        key = (prefix, major, minor)
        if key not in minor_best or patch > minor_best[key][0]:
            minor_best[key] = (patch, commit)

    # Assemble result.
    targets: dict[str, str] = {}
    for (prefix, major), (_, commit) in major_best.items():
        targets[f"{prefix}{major}"] = commit
    for (prefix, major, minor), (_, commit) in minor_best.items():
        targets[f"{prefix}{major}.{minor}"] = commit

    return targets


def classify_tag_role(name: str, all_managed: dict[str, object]) -> str:
    """Return 'exact' or 'floating' for a managed tag given the full inventory.

    Classification rules:
    - MAJOR.MINOR.PATCH → always 'exact'
    - MAJOR             → always 'floating'
    - MAJOR.MINOR       → 'floating' if a MAJOR.MINOR.PATCH tag with the same
                          prefix and same MAJOR.MINOR family exists in
                          *all_managed*; 'exact' otherwise.

    Cross-prefix isolation: a prefixed tag (e.g. 'v1.3') is never made floating
    by an unprefixed sibling (e.g. '1.3.4'), and vice versa.

    Raises:
        ValueError: if *name* is not a recognized managed version tag.
    """
    m = _TAG_DEPTH_RE.fullmatch(name)
    if m is None:
        raise ValueError(f"{name!r} is not a recognized managed version tag")

    prefix, major, minor, patch = m.group(1), m.group(2), m.group(3), m.group(4)

    if patch is not None:
        # MAJOR.MINOR.PATCH — always exact.
        return "exact"

    if minor is None:
        # MAJOR only — always floating.
        return "floating"

    # MAJOR.MINOR — floating only if a same-prefix MAJOR.MINOR.PATCH sibling exists.
    sibling_re = re.compile(
        rf"^{re.escape(prefix)}{re.escape(major)}\.{re.escape(minor)}\.\d+$"
    )
    return "floating" if any(sibling_re.fullmatch(t) for t in all_managed) else "exact"
