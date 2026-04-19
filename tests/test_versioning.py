"""Unit tests for gitsem.versioning."""

import unittest

from gitsem.errors import InvalidVersionError
from gitsem.versioning import (
    ParsedVersion,
    classify_tag_role,
    derive_managed_tags,
    get_exact_tag,
    get_floating_tags,
    get_tag_prefix,
    is_managed_version_tag,
    parse_version,
    switch_tag_prefix,
)


class TestParseVersion(unittest.TestCase):
    """parse_version() — valid inputs."""

    def test_major_minor_unprefixed(self) -> None:
        pv = parse_version("1.3")
        self.assertEqual(pv, ParsedVersion(prefix="", major=1, minor=3, patch=None))

    def test_major_minor_prefixed(self) -> None:
        pv = parse_version("v1.3")
        self.assertEqual(pv, ParsedVersion(prefix="v", major=1, minor=3, patch=None))

    def test_major_minor_patch_unprefixed(self) -> None:
        pv = parse_version("1.3.4")
        self.assertEqual(pv, ParsedVersion(prefix="", major=1, minor=3, patch=4))

    def test_major_minor_patch_prefixed(self) -> None:
        pv = parse_version("v1.3.4")
        self.assertEqual(pv, ParsedVersion(prefix="v", major=1, minor=3, patch=4))

    def test_double_digit_components(self) -> None:
        pv = parse_version("10.20.30")
        self.assertEqual(pv, ParsedVersion(prefix="", major=10, minor=20, patch=30))

    def test_zero_patch(self) -> None:
        pv = parse_version("2.0.0")
        self.assertEqual(pv, ParsedVersion(prefix="", major=2, minor=0, patch=0))

    def test_v0_prefix(self) -> None:
        pv = parse_version("v0.1.0")
        self.assertEqual(pv, ParsedVersion(prefix="v", major=0, minor=1, patch=0))


class TestParseVersionInvalid(unittest.TestCase):
    """parse_version() — invalid inputs must raise InvalidVersionError."""

    _invalid = [
        "1",           # major only
        "1.2.3.4",     # four components
        "1.2.3-alpha", # pre-release suffix
        "1.2.3+build", # build metadata
        "v",           # bare prefix
        "",            # empty
        "latest",      # arbitrary label
        "1.2.x",       # wildcard
        " 1.2.3",      # leading space
        "1.2.3 ",      # trailing space
    ]

    def test_invalid_forms(self) -> None:
        for s in self._invalid:
            with self.subTest(version=s):
                with self.assertRaises(InvalidVersionError):
                    parse_version(s)


class TestDeriveManagedTags(unittest.TestCase):
    """derive_managed_tags() produces correct tag lists."""

    def test_patch_unprefixed(self) -> None:
        pv = parse_version("1.3.4")
        self.assertEqual(derive_managed_tags(pv), ["1", "1.3", "1.3.4"])

    def test_patch_prefixed(self) -> None:
        pv = parse_version("v1.3.4")
        self.assertEqual(derive_managed_tags(pv), ["v1", "v1.3", "v1.3.4"])

    def test_minor_unprefixed(self) -> None:
        pv = parse_version("1.3")
        self.assertEqual(derive_managed_tags(pv), ["1", "1.3"])

    def test_minor_prefixed(self) -> None:
        pv = parse_version("v1.3")
        self.assertEqual(derive_managed_tags(pv), ["v1", "v1.3"])

    def test_zero_patch_prefixed(self) -> None:
        pv = parse_version("v2.0.0")
        self.assertEqual(derive_managed_tags(pv), ["v2", "v2.0", "v2.0.0"])


class TestGetFloatingAndExact(unittest.TestCase):
    """get_floating_tags() and get_exact_tag() split correctly."""

    def test_patch_floating(self) -> None:
        pv = parse_version("1.3.4")
        self.assertEqual(get_floating_tags(pv), ["1", "1.3"])

    def test_patch_exact(self) -> None:
        pv = parse_version("1.3.4")
        self.assertEqual(get_exact_tag(pv), "1.3.4")

    def test_minor_floating(self) -> None:
        pv = parse_version("1.3")
        self.assertEqual(get_floating_tags(pv), ["1"])

    def test_minor_exact(self) -> None:
        pv = parse_version("1.3")
        self.assertEqual(get_exact_tag(pv), "1.3")

    def test_prefixed_patch_floating(self) -> None:
        pv = parse_version("v1.3.4")
        self.assertEqual(get_floating_tags(pv), ["v1", "v1.3"])

    def test_prefixed_patch_exact(self) -> None:
        pv = parse_version("v1.3.4")
        self.assertEqual(get_exact_tag(pv), "v1.3.4")


class TestIsManagedVersionTag(unittest.TestCase):
    """is_managed_version_tag() correctly classifies tag names."""

    _managed = ["1", "1.3", "1.3.4", "v1", "v1.3", "v1.3.4", "10", "0.0.0"]
    _not_managed = [
        "latest",
        "stable",
        "release-1.3",
        "1.3.4-alpha",
        "1.3.4+build",
        "v",
        "",
        "1.2.3.4",
        "v1.2.3.4",
        "my-tag",
    ]

    def test_managed(self) -> None:
        for name in self._managed:
            with self.subTest(name=name):
                self.assertTrue(is_managed_version_tag(name))

    def test_not_managed(self) -> None:
        for name in self._not_managed:
            with self.subTest(name=name):
                self.assertFalse(is_managed_version_tag(name))


class TestGetTagPrefix(unittest.TestCase):
    def test_prefixed(self) -> None:
        self.assertEqual(get_tag_prefix("v1.3"), "v")

    def test_unprefixed(self) -> None:
        self.assertEqual(get_tag_prefix("1.3"), "")


class TestSwitchTagPrefix(unittest.TestCase):
    def test_unprefixed_to_prefixed(self) -> None:
        self.assertEqual(switch_tag_prefix("1.3.4", "v"), "v1.3.4")

    def test_prefixed_to_unprefixed(self) -> None:
        self.assertEqual(switch_tag_prefix("v1.3.4", ""), "1.3.4")

    def test_major_only(self) -> None:
        self.assertEqual(switch_tag_prefix("1", "v"), "v1")

    def test_already_same_prefix(self) -> None:
        self.assertEqual(switch_tag_prefix("v1.3", "v"), "v1.3")


class TestClassifyTagRole(unittest.TestCase):
    """classify_tag_role() classifies tags as 'exact' or 'floating'."""

    # Helpers
    def _inv(self, *names: str) -> dict[str, object]:
        """Build a minimal managed-tag dict from bare names."""
        return {n: object() for n in names}

    # ---- MAJOR.MINOR.PATCH is always exact ----

    def test_patch_unprefixed_exact(self) -> None:
        inv = self._inv("1", "1.3", "1.3.4")
        self.assertEqual(classify_tag_role("1.3.4", inv), "exact")

    def test_patch_prefixed_exact(self) -> None:
        inv = self._inv("v1", "v1.3", "v1.3.4")
        self.assertEqual(classify_tag_role("v1.3.4", inv), "exact")

    def test_patch_zero_exact(self) -> None:
        inv = self._inv("2", "2.0", "2.0.0")
        self.assertEqual(classify_tag_role("2.0.0", inv), "exact")

    # ---- MAJOR only is always floating ----

    def test_major_unprefixed_floating(self) -> None:
        inv = self._inv("1", "1.3", "1.3.4")
        self.assertEqual(classify_tag_role("1", inv), "floating")

    def test_major_prefixed_floating(self) -> None:
        inv = self._inv("v1", "v1.3", "v1.3.4")
        self.assertEqual(classify_tag_role("v1", inv), "floating")

    def test_major_alone_floating(self) -> None:
        """MAJOR alone with no MINOR siblings is still floating."""
        inv = self._inv("1")
        self.assertEqual(classify_tag_role("1", inv), "floating")

    # ---- MAJOR.MINOR — exact when no patch sibling exists ----

    def test_minor_alone_exact(self) -> None:
        inv = self._inv("1", "1.3")
        self.assertEqual(classify_tag_role("1.3", inv), "exact")

    def test_minor_prefixed_alone_exact(self) -> None:
        inv = self._inv("v1", "v1.3")
        self.assertEqual(classify_tag_role("v1.3", inv), "exact")

    # ---- MAJOR.MINOR — floating when same-prefix patch sibling exists ----

    def test_minor_becomes_floating_with_patch_sibling(self) -> None:
        inv = self._inv("1", "1.3", "1.3.0")
        self.assertEqual(classify_tag_role("1.3", inv), "floating")

    def test_minor_prefixed_becomes_floating_with_patch_sibling(self) -> None:
        inv = self._inv("v1", "v1.3", "v1.3.4")
        self.assertEqual(classify_tag_role("v1.3", inv), "floating")

    def test_minor_floating_with_multi_patch_siblings(self) -> None:
        inv = self._inv("1", "1.3", "1.3.0", "1.3.1", "1.3.2")
        self.assertEqual(classify_tag_role("1.3", inv), "floating")

    # ---- Cross-prefix isolation ----

    def test_cross_prefix_isolation_unprefixed_not_affected_by_prefixed(self) -> None:
        """Unprefixed '1.3' must NOT be made floating by prefixed 'v1.3.4'."""
        inv = self._inv("1", "1.3", "v1", "v1.3", "v1.3.4")
        self.assertEqual(classify_tag_role("1.3", inv), "exact")

    def test_cross_prefix_isolation_prefixed_not_affected_by_unprefixed(self) -> None:
        """Prefixed 'v1.3' must NOT be made floating by unprefixed '1.3.4'."""
        inv = self._inv("v1", "v1.3", "1", "1.3", "1.3.4")
        self.assertEqual(classify_tag_role("v1.3", inv), "exact")

    # ---- Invalid input raises ValueError ----

    def test_invalid_name_raises(self) -> None:
        with self.assertRaises(ValueError):
            classify_tag_role("not-a-version", {})


if __name__ == "__main__":
    unittest.main()
