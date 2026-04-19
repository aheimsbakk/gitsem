"""Unit tests for gitsem.versioning."""

import unittest

from gitsem.errors import InvalidVersionError
from gitsem.versioning import (
    ParsedVersion,
    classify_tag_role,
    compute_floating_tag_targets,
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


class TestComputeFloatingTagTargets(unittest.TestCase):
    """compute_floating_tag_targets() computes the correct floating tag → commit map."""

    # ------------------------------------------------------------------
    # Edge cases
    # ------------------------------------------------------------------

    def test_empty_inventory_returns_empty(self) -> None:
        self.assertEqual(compute_floating_tag_targets({}), {})

    def test_only_major_floating_tag_no_exact(self) -> None:
        """A MAJOR-only inventory has no exact tags → nothing to derive from."""
        self.assertEqual(compute_floating_tag_targets({"1": "aaa"}), {})

    # ------------------------------------------------------------------
    # Single patch release (full inventory including existing floats)
    # ------------------------------------------------------------------

    def test_single_patch_release_creates_two_floats(self) -> None:
        targets = compute_floating_tag_targets(
            {"1": "aaa", "1.3": "bbb", "1.3.4": "ccc"}
        )
        self.assertEqual(targets["1"], "ccc")
        self.assertEqual(targets["1.3"], "ccc")
        self.assertNotIn("1.3.4", targets)  # exact — must not appear

    def test_single_patch_release_prefixed(self) -> None:
        targets = compute_floating_tag_targets(
            {"v1": "aaa", "v1.3": "bbb", "v1.3.4": "ccc"}
        )
        self.assertEqual(targets["v1"], "ccc")
        self.assertEqual(targets["v1.3"], "ccc")

    # ------------------------------------------------------------------
    # Multiple patches — highest wins MAJOR.MINOR float
    # ------------------------------------------------------------------

    def test_highest_patch_wins_minor_float(self) -> None:
        targets = compute_floating_tag_targets(
            {
                "1": "a",
                "1.3": "b",
                "1.3.0": "c00",
                "1.3.1": "c01",
                "1.3.5": "c05",
            }
        )
        self.assertEqual(targets["1.3"], "c05")
        self.assertEqual(targets["1"], "c05")

    # ------------------------------------------------------------------
    # Multiple minor lines — highest minor wins MAJOR float
    # ------------------------------------------------------------------

    def test_highest_minor_wins_major_float(self) -> None:
        targets = compute_floating_tag_targets(
            {
                "1": "a",
                "1.2": "b",
                "1.2.3": "c23",
                "1.3": "d",
                "1.3.5": "c35",
            }
        )
        self.assertEqual(targets["1"], "c35")   # 1.3.5 is the newest overall
        self.assertEqual(targets["1.2"], "c23")  # highest patch in 1.2.x family
        self.assertEqual(targets["1.3"], "c35")  # highest patch in 1.3.x family

    # ------------------------------------------------------------------
    # MAJOR.MINOR-only repo (no patch children → MAJOR.MINOR is exact)
    # ------------------------------------------------------------------

    def test_minor_only_repo_only_major_float_derived(self) -> None:
        """With only MAJOR.MINOR exact tags, only MAJOR floating is needed."""
        targets = compute_floating_tag_targets(
            {"1": "a", "1.2": "b12", "1.3": "b13"}
        )
        self.assertEqual(targets["1"], "b13")   # minor=3 > minor=2
        self.assertNotIn("1.2", targets)         # exact — no floating above it
        self.assertNotIn("1.3", targets)         # exact — no floating above it

    def test_minor_only_single_entry(self) -> None:
        targets = compute_floating_tag_targets({"1": "a", "1.3": "b13"})
        self.assertEqual(targets["1"], "b13")
        self.assertNotIn("1.3", targets)

    # ------------------------------------------------------------------
    # Mixed transition: some MAJOR.MINOR exact, some MAJOR.MINOR.PATCH
    # ------------------------------------------------------------------

    def test_transition_patch_outranks_same_minor_exact(self) -> None:
        """MAJOR.MINOR.PATCH sort key (minor, patch=N) beats MAJOR.MINOR sort key
        (minor, patch=-1) only when the patch version is higher."""
        targets = compute_floating_tag_targets(
            {
                "1": "a",
                "1.2": "old",   # was exact; now floating (has 1.2.0 sibling)
                "1.2.0": "new",
                "1.3": "mid",   # still exact (no 1.3.x siblings)
            }
        )
        # 1.3 exact: sort_key (3, -1); 1.2.0 exact: sort_key (2, 0)
        # (3, -1) > (2, 0) → 1.3 wins → MAJOR float → "mid"
        self.assertEqual(targets["1"], "mid")
        # 1.2 is floating → points to 1.2.0's commit
        self.assertEqual(targets["1.2"], "new")
        # 1.3 is exact with no patch sibling → not a floating target
        self.assertNotIn("1.3", targets)

    def test_patch_beats_lower_minor_exact(self) -> None:
        """A MAJOR.MINOR.PATCH version beats a MAJOR.MINOR exact of lower minor."""
        targets = compute_floating_tag_targets(
            {
                "1": "a",
                "1.2": "b12",   # exact (no patch sibling)
                "1.1": "b11",   # exact (no patch sibling)
                "1.3": "b13",   # exact (no patch sibling)
            }
        )
        self.assertEqual(targets["1"], "b13")  # minor=3 is highest

    # ------------------------------------------------------------------
    # Multiple MAJOR families
    # ------------------------------------------------------------------

    def test_multiple_major_families(self) -> None:
        targets = compute_floating_tag_targets(
            {
                "1": "a1", "1.2": "b12", "1.2.0": "c120",
                "2": "a2", "2.0": "b20", "2.0.1": "c201",
            }
        )
        self.assertEqual(targets["1"], "c120")
        self.assertEqual(targets["1.2"], "c120")
        self.assertEqual(targets["2"], "c201")
        self.assertEqual(targets["2.0"], "c201")

    # ------------------------------------------------------------------
    # Cross-prefix isolation
    # ------------------------------------------------------------------

    def test_cross_prefix_isolation(self) -> None:
        """Prefixed and unprefixed families are fully independent."""
        targets = compute_floating_tag_targets(
            {
                "1": "a", "1.3": "b", "1.3.4": "c34",
                "v1": "d", "v1.3": "e", "v1.3.5": "c35",
            }
        )
        self.assertEqual(targets["1"], "c34")
        self.assertEqual(targets["1.3"], "c34")
        self.assertEqual(targets["v1"], "c35")
        self.assertEqual(targets["v1.3"], "c35")

    # ------------------------------------------------------------------
    # Exact tags only (no pre-existing floating tags in inventory)
    # ------------------------------------------------------------------

    def test_derives_floats_even_without_existing_float_tags(self) -> None:
        """Works correctly even if the inventory only has exact tags."""
        targets = compute_floating_tag_targets({"1.3.4": "ccc"})
        self.assertEqual(targets["1"], "ccc")
        self.assertEqual(targets["1.3"], "ccc")


if __name__ == "__main__":
    unittest.main()
