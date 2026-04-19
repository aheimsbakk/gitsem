"""Semantic version validation, prefix preservation, and managed tag derivation."""

import re
from dataclasses import dataclass

from .errors import InvalidVersionError

# Accepts 1.3 / v1.3 / 1.3.4 / v1.3.4 — no pre-release or build metadata.
_VERSION_RE = re.compile(r"^(v?)(\d+)\.(\d+)(?:\.(\d+))?$")

# Pattern that identifies any managed version tag (with or without 'v' prefix).
_MANAGED_TAG_RE = re.compile(r"^v?\d+(\.\d+(\.\d+)?)?$")


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
