"""Unit tests for gitsem.tag_service (logic-only, no real Git)."""

import unittest
from unittest.mock import MagicMock, patch

from gitsem.errors import RemoteConflictError, StyleMismatchError, TagConflictError
from gitsem.git_ops import TagInfo
from gitsem.tag_service import detect_style
class TestDetectStyle(unittest.TestCase):
    """detect_style() infers prefix style from managed tag dict."""

    def _ti(self, commit: str = "abc123", annotated: bool = False) -> TagInfo:
        return TagInfo(commit=commit, annotated=annotated)

    def test_empty_returns_none(self) -> None:
        self.assertIsNone(detect_style({}))

    def test_all_prefixed(self) -> None:
        tags = {"v1": self._ti(), "v1.3": self._ti(), "v1.3.4": self._ti()}
        self.assertEqual(detect_style(tags), "v")

    def test_all_unprefixed(self) -> None:
        tags = {"1": self._ti(), "1.3": self._ti(), "1.3.4": self._ti()}
        self.assertEqual(detect_style(tags), "")

    def test_mixed_raises(self) -> None:
        tags = {"v1": self._ti(), "1.3": self._ti()}
        with self.assertRaises(TagConflictError):
            detect_style(tags)

    def test_single_prefixed(self) -> None:
        self.assertEqual(detect_style({"v2": self._ti()}), "v")

    def test_single_unprefixed(self) -> None:
        self.assertEqual(detect_style({"2": self._ti()}), "")


class TestApplyStyleMismatch(unittest.TestCase):
    """apply() raises StyleMismatchError on prefix conflict without --migrate."""

    def _make_tags(self, names: list[str]) -> dict[str, TagInfo]:
        return {n: TagInfo(commit="dead" * 10, annotated=False) for n in names}

    @patch("gitsem.tag_service.git_ops.list_local_tags")
    @patch("gitsem.tag_service.git_ops.health_check", return_value="a" * 40)
    def test_mismatch_unprefixed_repo_prefixed_request(
        self, mock_health: MagicMock, mock_list: MagicMock
    ) -> None:
        mock_list.return_value = self._make_tags(["1", "1.3", "1.3.4"])
        from gitsem.tag_service import apply

        with self.assertRaises(StyleMismatchError):
            apply("v1.3.5", migrate=False, push=False, force=False, verbose=False)

    @patch("gitsem.tag_service.git_ops.list_local_tags")
    @patch("gitsem.tag_service.git_ops.health_check", return_value="a" * 40)
    def test_mismatch_prefixed_repo_unprefixed_request(
        self, mock_health: MagicMock, mock_list: MagicMock
    ) -> None:
        mock_list.return_value = self._make_tags(["v1", "v1.3", "v1.3.4"])
        from gitsem.tag_service import apply

        with self.assertRaises(StyleMismatchError):
            apply("1.3.5", migrate=False, push=False, force=False, verbose=False)


class TestApplyAnnotatedTagRejected(unittest.TestCase):
    """apply() refuses to touch annotated managed tags."""

    @patch("gitsem.tag_service.git_ops.list_local_tags")
    @patch("gitsem.tag_service.git_ops.health_check", return_value="b" * 40)
    def test_annotated_floating_raises(
        self, mock_health: MagicMock, mock_list: MagicMock
    ) -> None:
        mock_list.return_value = {
            "1": TagInfo(commit="b" * 40, annotated=True),
        }
        from gitsem.tag_service import apply

        with self.assertRaises(TagConflictError):
            apply("1.3.5", migrate=False, push=False, force=False, verbose=False)

    @patch("gitsem.tag_service.git_ops.list_local_tags")
    @patch("gitsem.tag_service.git_ops.health_check", return_value="c" * 40)
    def test_annotated_exact_raises(
        self, mock_health: MagicMock, mock_list: MagicMock
    ) -> None:
        mock_list.return_value = {
            "1.3.5": TagInfo(commit="old" + "0" * 37, annotated=True),
        }
        from gitsem.tag_service import apply

        with self.assertRaises(TagConflictError):
            apply("1.3.5", migrate=False, push=False, force=False, verbose=False)


class TestApplyExactTagConflict(unittest.TestCase):
    """apply() refuses to move an exact release tag that exists on a different commit."""

    @patch("gitsem.tag_service.git_ops.list_local_tags")
    @patch("gitsem.tag_service.git_ops.health_check", return_value="new" + "0" * 37)
    def test_exact_tag_on_different_commit_raises(
        self, mock_health: MagicMock, mock_list: MagicMock
    ) -> None:
        mock_list.return_value = {
            "1.3.5": TagInfo(commit="old" + "0" * 37, annotated=False),
        }
        from gitsem.tag_service import apply

        with self.assertRaises(TagConflictError):
            apply("1.3.5", migrate=False, push=False, force=False, verbose=False)


class TestApplyIdempotent(unittest.TestCase):
    """apply() is idempotent when all managed tags already point to HEAD."""

    _HEAD = "a" * 40

    @patch("gitsem.tag_service.git_ops.list_local_tags")
    @patch("gitsem.tag_service.git_ops.health_check", return_value="a" * 40)
    def test_all_tags_already_at_head(
        self, mock_health: MagicMock, mock_list: MagicMock
    ) -> None:
        mock_list.return_value = {
            "1": TagInfo(commit=self._HEAD, annotated=False),
            "1.3": TagInfo(commit=self._HEAD, annotated=False),
            "1.3.5": TagInfo(commit=self._HEAD, annotated=False),
        }
        from gitsem.tag_service import apply

        result = apply("1.3.5", migrate=False, push=False, force=False, verbose=False)
        self.assertEqual(result.created, [])
        self.assertEqual(result.moved, [])
        self.assertEqual(sorted(result.skipped), ["1", "1.3", "1.3.5"])


class TestApplyGreenfield(unittest.TestCase):
    """apply() creates all tags when the repository has no managed tags."""

    _HEAD = "f" * 40

    @patch("gitsem.tag_service.git_ops.create_tag")
    @patch("gitsem.tag_service.git_ops.list_local_tags", return_value={})
    @patch("gitsem.tag_service.git_ops.health_check", return_value="f" * 40)
    def test_creates_all_tags(
        self,
        mock_health: MagicMock,
        mock_list: MagicMock,
        mock_create: MagicMock,
    ) -> None:
        from gitsem.tag_service import apply

        result = apply("1.3.5", migrate=False, push=False, force=False, verbose=False)
        self.assertEqual(sorted(result.created), ["1", "1.3", "1.3.5"])
        self.assertEqual(mock_create.call_count, 3)


class TestApplyMoveFloating(unittest.TestCase):
    """apply() moves floating tags that point to a different commit."""

    _HEAD = "new" + "0" * 37
    _OLD = "old" + "0" * 37

    @patch("gitsem.tag_service.git_ops.create_tag")
    @patch("gitsem.tag_service.git_ops.delete_local_tag")
    @patch("gitsem.tag_service.git_ops.list_local_tags")
    @patch("gitsem.tag_service.git_ops.health_check", return_value="new" + "0" * 37)
    def test_moves_floating_creates_exact(
        self,
        mock_health: MagicMock,
        mock_list: MagicMock,
        mock_delete: MagicMock,
        mock_create: MagicMock,
    ) -> None:
        mock_list.return_value = {
            "1": TagInfo(commit=self._OLD, annotated=False),
            "1.3": TagInfo(commit=self._OLD, annotated=False),
            "1.3.4": TagInfo(commit=self._OLD, annotated=False),
        }
        from gitsem.tag_service import apply

        result = apply("1.3.5", migrate=False, push=False, force=False, verbose=False)
        self.assertEqual(sorted(result.moved), ["1", "1.3"])
        self.assertEqual(result.created, ["1.3.5"])
        # Two deletes (floating tags) + one create (exact) + two recreates (floats).
        self.assertEqual(mock_delete.call_count, 2)
        self.assertEqual(mock_create.call_count, 3)


class TestSwitchPlanDetailed(unittest.TestCase):
    """_execute_switch() migrates all managed tags to the new prefix."""

    _HEAD = "a" * 40

    @patch("gitsem.tag_service.git_ops.create_tag")
    @patch("gitsem.tag_service.git_ops.delete_local_tag")
    @patch("gitsem.tag_service.git_ops.list_local_tags")
    @patch("gitsem.tag_service.git_ops.health_check", return_value="a" * 40)
    def test_switch_from_unprefixed_to_prefixed(
        self,
        mock_health: MagicMock,
        mock_list: MagicMock,
        mock_delete: MagicMock,
        mock_create: MagicMock,
    ) -> None:
        commit_a = "a" * 40
        commit_b = "b" * 40
        # First call: switch inventory; second call: post-switch reload.
        mock_list.side_effect = [
            {
                "1": TagInfo(commit=commit_a, annotated=False),
                "1.2": TagInfo(commit=commit_b, annotated=False),
                "1.2.3": TagInfo(commit=commit_b, annotated=False),
            },
            {
                # After switch the old tags are gone, new-style tags exist.
                "v1": TagInfo(commit=commit_a, annotated=False),
                "v1.2": TagInfo(commit=commit_b, annotated=False),
                "v1.2.3": TagInfo(commit=commit_b, annotated=False),
            },
        ]
        from gitsem.tag_service import apply

        result = apply(
            "v1.2.4", migrate=True, push=False, force=False, verbose=False
        )
        # All three old tags migrated.
        self.assertEqual(sorted(result.switched), ["v1", "v1.2", "v1.2.3"])
        self.assertEqual(sorted(result.deleted), ["1", "1.2", "1.2.3"])


class TestDepthTransition(unittest.TestCase):
    """Repositories may move from MAJOR.MINOR to MAJOR.MINOR.PATCH releases."""

    _HEAD = "c" * 40
    _OLD = "d" * 40

    @patch("gitsem.tag_service.git_ops.create_tag")
    @patch("gitsem.tag_service.git_ops.delete_local_tag")
    @patch("gitsem.tag_service.git_ops.list_local_tags")
    @patch("gitsem.tag_service.git_ops.health_check", return_value="c" * 40)
    def test_minor_exact_becomes_floating(
        self,
        mock_health: MagicMock,
        mock_list: MagicMock,
        mock_delete: MagicMock,
        mock_create: MagicMock,
    ) -> None:
        """When 1.3.0 is released, 1.3 (previously exact) becomes floating."""
        mock_list.return_value = {
            "1": TagInfo(commit=self._OLD, annotated=False),
            "1.3": TagInfo(commit=self._OLD, annotated=False),
            # No 1.3.x tags yet — historical MAJOR.MINOR-only releases.
        }
        from gitsem.tag_service import apply

        result = apply("1.3.0", migrate=False, push=False, force=False, verbose=False)
        # 1 and 1.3 should be moved to HEAD; 1.3.0 should be created.
        self.assertEqual(sorted(result.moved), ["1", "1.3"])
        self.assertEqual(result.created, ["1.3.0"])


class TestDryRunGreenfield(unittest.TestCase):
    """dry_run=True on a fresh repo plans tags but makes no mutations."""

    _HEAD = "f" * 40

    @patch("gitsem.tag_service.git_ops.create_tag")
    @patch("gitsem.tag_service.git_ops.list_local_tags", return_value={})
    @patch("gitsem.tag_service.git_ops.health_check", return_value="f" * 40)
    def test_creates_no_actual_tags(
        self,
        mock_health: MagicMock,
        mock_list: MagicMock,
        mock_create: MagicMock,
    ) -> None:
        from gitsem.tag_service import apply

        result = apply(
            "1.3.5", migrate=False, push=False, force=False, verbose=False, dry_run=True
        )
        mock_create.assert_not_called()
        self.assertEqual(sorted(result.created), ["1", "1.3", "1.3.5"])
        self.assertTrue(result.dry_run)

    @patch("gitsem.tag_service.git_ops.list_local_tags", return_value={})
    @patch("gitsem.tag_service.git_ops.health_check", return_value="f" * 40)
    def test_head_commit_set_in_result(
        self,
        mock_health: MagicMock,
        mock_list: MagicMock,
    ) -> None:
        from gitsem.tag_service import apply

        result = apply(
            "1.3.5", migrate=False, push=False, force=False, verbose=False, dry_run=True
        )
        self.assertEqual(result.head_commit, "f" * 40)
        self.assertTrue(result.dry_run)


class TestDryRunSwitch(unittest.TestCase):
    """dry_run=True with migrate=True simulates migration in memory without mutations."""

    _HEAD = "a" * 40

    @patch("gitsem.tag_service.git_ops.create_tag")
    @patch("gitsem.tag_service.git_ops.delete_local_tag")
    @patch("gitsem.tag_service.git_ops.list_local_tags")
    @patch("gitsem.tag_service.git_ops.health_check", return_value="a" * 40)
    def test_switch_dry_run_no_mutations(
        self,
        mock_health: MagicMock,
        mock_list: MagicMock,
        mock_delete: MagicMock,
        mock_create: MagicMock,
    ) -> None:
        mock_list.return_value = {
            "1": TagInfo(commit="a" * 40, annotated=False),
            "1.2": TagInfo(commit="a" * 40, annotated=False),
            "1.2.3": TagInfo(commit="a" * 40, annotated=False),
        }
        from gitsem.tag_service import apply

        result = apply(
            "v1.2.4", migrate=True, push=False, force=False, verbose=False, dry_run=True
        )
        mock_create.assert_not_called()
        mock_delete.assert_not_called()
        # list_local_tags called only once — no post-switch reload in dry-run.
        mock_list.assert_called_once()

    @patch("gitsem.tag_service.git_ops.create_tag")
    @patch("gitsem.tag_service.git_ops.delete_local_tag")
    @patch("gitsem.tag_service.git_ops.list_local_tags")
    @patch("gitsem.tag_service.git_ops.health_check", return_value="a" * 40)
    def test_switch_dry_run_plans_migration(
        self,
        mock_health: MagicMock,
        mock_list: MagicMock,
        mock_delete: MagicMock,
        mock_create: MagicMock,
    ) -> None:
        mock_list.return_value = {
            "1": TagInfo(commit="a" * 40, annotated=False),
            "1.2": TagInfo(commit="a" * 40, annotated=False),
            "1.2.3": TagInfo(commit="a" * 40, annotated=False),
        }
        from gitsem.tag_service import apply

        result = apply(
            "v1.2.4", migrate=True, push=False, force=False, verbose=False, dry_run=True
        )
        self.assertEqual(sorted(result.switched), ["v1", "v1.2", "v1.2.3"])
        self.assertEqual(sorted(result.deleted), ["1", "1.2", "1.2.3"])
        # New version tag should be planned (in-memory simulation sees prefixed tags at HEAD).
        self.assertIn("v1.2.4", result.created)


class TestDryRunPush(unittest.TestCase):
    """dry_run=True with push=True checks remote conflicts without pushing."""

    _HEAD = "a" * 40

    @patch("gitsem.tag_service.git_ops.push_tag")
    @patch("gitsem.tag_service.git_ops.delete_remote_tag")
    @patch("gitsem.tag_service.git_ops.list_remote_tags", return_value={})
    @patch("gitsem.tag_service.git_ops.create_tag")
    @patch("gitsem.tag_service.git_ops.list_local_tags", return_value={})
    @patch("gitsem.tag_service.git_ops.health_check", return_value="a" * 40)
    def test_push_dry_run_no_actual_push(
        self,
        mock_health: MagicMock,
        mock_list: MagicMock,
        mock_create: MagicMock,
        mock_remote_list: MagicMock,
        mock_delete_remote: MagicMock,
        mock_push: MagicMock,
    ) -> None:
        from gitsem.tag_service import apply

        result = apply(
            "1.3.5", migrate=False, push=True, force=False, verbose=False, dry_run=True
        )
        mock_push.assert_not_called()
        mock_delete_remote.assert_not_called()
        mock_create.assert_not_called()
        # All three managed tags should be planned for push.
        self.assertEqual(sorted(result.pushed), ["1", "1.3", "1.3.5"])

    @patch("gitsem.tag_service.git_ops.push_tag")
    @patch("gitsem.tag_service.git_ops.delete_remote_tag")
    @patch("gitsem.tag_service.git_ops.list_remote_tags")
    @patch("gitsem.tag_service.git_ops.create_tag")
    @patch("gitsem.tag_service.git_ops.list_local_tags", return_value={})
    @patch("gitsem.tag_service.git_ops.health_check", return_value="a" * 40)
    def test_push_dry_run_detects_remote_conflict(
        self,
        mock_health: MagicMock,
        mock_list: MagicMock,
        mock_create: MagicMock,
        mock_remote_list: MagicMock,
        mock_delete_remote: MagicMock,
        mock_push: MagicMock,
    ) -> None:
        from gitsem.errors import RemoteConflictError
        from gitsem.git_ops import TagInfo as RemoteTagInfo
        from gitsem.tag_service import apply

        # Simulate remote exact tag pointing to a different commit.
        mock_remote_list.return_value = {
            "1.3.5": RemoteTagInfo(commit="old" + "0" * 37, annotated=False),
        }
        with self.assertRaises(RemoteConflictError):
            apply(
                "1.3.5", migrate=False, push=True, force=False, verbose=False, dry_run=True
            )
        mock_push.assert_not_called()


class TestSyncAll(unittest.TestCase):
    """sync_all() synchronises every local managed tag to the remote."""

    _HEAD = "a" * 40
    _OLD  = "b" * 40

    def _ti(self, commit: str = "a" * 40, annotated: bool = False) -> TagInfo:
        return TagInfo(commit=commit, annotated=annotated)

    # ------------------------------------------------------------------
    # All remote tags missing → all pushed
    # ------------------------------------------------------------------

    @patch("gitsem.tag_service.git_ops.push_tag")
    @patch("gitsem.tag_service.git_ops.list_remote_tags", return_value={})
    @patch("gitsem.tag_service.git_ops.list_local_tags")
    @patch("gitsem.tag_service.git_ops.health_check", return_value="a" * 40)
    def test_all_missing_on_remote_pushed(
        self,
        mock_health: MagicMock,
        mock_local: MagicMock,
        mock_remote: MagicMock,
        mock_push: MagicMock,
    ) -> None:
        mock_local.return_value = {
            "1": self._ti(), "1.3": self._ti(), "1.3.4": self._ti(),
        }
        from gitsem.tag_service import sync_all

        result = sync_all(force=False)
        self.assertEqual(sorted(result.pushed), ["1", "1.3", "1.3.4"])
        self.assertEqual(result.remote_skipped, [])
        self.assertEqual(mock_push.call_count, 3)

    # ------------------------------------------------------------------
    # All remote tags already at correct commits → all remote_skipped
    # ------------------------------------------------------------------

    @patch("gitsem.tag_service.git_ops.push_tag")
    @patch("gitsem.tag_service.git_ops.list_remote_tags")
    @patch("gitsem.tag_service.git_ops.list_local_tags")
    @patch("gitsem.tag_service.git_ops.health_check", return_value="a" * 40)
    def test_all_in_sync_remote_skipped(
        self,
        mock_health: MagicMock,
        mock_local: MagicMock,
        mock_remote: MagicMock,
        mock_push: MagicMock,
    ) -> None:
        mock_local.return_value = {
            "1": self._ti(), "1.3": self._ti(), "1.3.4": self._ti(),
        }
        mock_remote.return_value = {
            "1": self._ti(), "1.3": self._ti(), "1.3.4": self._ti(),
        }
        from gitsem.tag_service import sync_all

        result = sync_all(force=False)
        self.assertEqual(sorted(result.remote_skipped), ["1", "1.3", "1.3.4"])
        mock_push.assert_not_called()

    # ------------------------------------------------------------------
    # Exact remote tag conflict without --force → RemoteConflictError
    # ------------------------------------------------------------------

    @patch("gitsem.tag_service.git_ops.push_tag")
    @patch("gitsem.tag_service.git_ops.list_remote_tags")
    @patch("gitsem.tag_service.git_ops.list_local_tags")
    @patch("gitsem.tag_service.git_ops.health_check", return_value="a" * 40)
    def test_exact_conflict_without_force_raises(
        self,
        mock_health: MagicMock,
        mock_local: MagicMock,
        mock_remote: MagicMock,
        mock_push: MagicMock,
    ) -> None:
        mock_local.return_value = {
            "1": self._ti(), "1.3": self._ti(), "1.3.4": self._ti(),
        }
        mock_remote.return_value = {
            "1":   self._ti(),             # floating — already in sync
            "1.3": self._ti(),             # floating — already in sync
            "1.3.4": self._ti(commit=self._OLD),  # exact tag at different commit
        }
        from gitsem.tag_service import sync_all

        with self.assertRaises(RemoteConflictError):
            sync_all(force=False)

    # ------------------------------------------------------------------
    # Exact remote tag conflict with --force → pushed
    # ------------------------------------------------------------------

    @patch("gitsem.tag_service.git_ops.push_tag")
    @patch("gitsem.tag_service.git_ops.delete_remote_tag")
    @patch("gitsem.tag_service.git_ops.list_remote_tags")
    @patch("gitsem.tag_service.git_ops.list_local_tags")
    @patch("gitsem.tag_service.git_ops.health_check", return_value="a" * 40)
    def test_exact_conflict_with_force_pushed(
        self,
        mock_health: MagicMock,
        mock_local: MagicMock,
        mock_remote: MagicMock,
        mock_delete: MagicMock,
        mock_push: MagicMock,
    ) -> None:
        mock_local.return_value = {
            "1": self._ti(), "1.3": self._ti(), "1.3.4": self._ti(),
        }
        mock_remote.return_value = {
            "1.3.4": self._ti(commit=self._OLD),
        }
        from gitsem.tag_service import sync_all

        result = sync_all(force=True)
        self.assertIn("1.3.4", result.pushed)

    # ------------------------------------------------------------------
    # Floating remote tag at different commit → pushed without --force
    # ------------------------------------------------------------------

    @patch("gitsem.tag_service.git_ops.push_tag")
    @patch("gitsem.tag_service.git_ops.delete_remote_tag")
    @patch("gitsem.tag_service.git_ops.list_remote_tags")
    @patch("gitsem.tag_service.git_ops.list_local_tags")
    @patch("gitsem.tag_service.git_ops.health_check", return_value="a" * 40)
    def test_floating_out_of_sync_pushed_without_force(
        self,
        mock_health: MagicMock,
        mock_local: MagicMock,
        mock_remote: MagicMock,
        mock_delete: MagicMock,
        mock_push: MagicMock,
    ) -> None:
        mock_local.return_value = {
            "1": self._ti(), "1.3": self._ti(), "1.3.4": self._ti(),
        }
        mock_remote.return_value = {
            "1":   self._ti(commit=self._OLD),  # floating — out of sync
            "1.3": self._ti(commit=self._OLD),  # floating — out of sync
        }
        from gitsem.tag_service import sync_all

        result = sync_all(force=False)
        # Floating tags moved, exact tag pushed (was absent on remote).
        self.assertIn("1", result.pushed)
        self.assertIn("1.3", result.pushed)
        self.assertIn("1.3.4", result.pushed)

    # ------------------------------------------------------------------
    # dry_run=True → no actual pushes; result.pushed still populated
    # ------------------------------------------------------------------

    @patch("gitsem.tag_service.git_ops.push_tag")
    @patch("gitsem.tag_service.git_ops.delete_remote_tag")
    @patch("gitsem.tag_service.git_ops.list_remote_tags", return_value={})
    @patch("gitsem.tag_service.git_ops.list_local_tags")
    @patch("gitsem.tag_service.git_ops.health_check", return_value="a" * 40)
    def test_dry_run_no_actual_push(
        self,
        mock_health: MagicMock,
        mock_local: MagicMock,
        mock_remote: MagicMock,
        mock_delete: MagicMock,
        mock_push: MagicMock,
    ) -> None:
        mock_local.return_value = {
            "1": self._ti(), "1.3": self._ti(), "1.3.4": self._ti(),
        }
        from gitsem.tag_service import sync_all

        result = sync_all(force=False, dry_run=True)
        mock_push.assert_not_called()
        mock_delete.assert_not_called()
        self.assertEqual(sorted(result.pushed), ["1", "1.3", "1.3.4"])
        self.assertTrue(result.dry_run)

    # ------------------------------------------------------------------
    # Empty local managed tags → empty result, no error
    # ------------------------------------------------------------------

    @patch("gitsem.tag_service.git_ops.list_local_tags", return_value={})
    @patch("gitsem.tag_service.git_ops.health_check", return_value="a" * 40)
    def test_empty_local_tags_no_error(
        self,
        mock_health: MagicMock,
        mock_local: MagicMock,
    ) -> None:
        from gitsem.tag_service import sync_all

        result = sync_all(force=False)
        self.assertEqual(result.pushed, [])
        self.assertEqual(result.remote_skipped, [])

    # ------------------------------------------------------------------
    # Annotated remote tag → RemoteConflictError
    # ------------------------------------------------------------------

    @patch("gitsem.tag_service.git_ops.push_tag")
    @patch("gitsem.tag_service.git_ops.list_remote_tags")
    @patch("gitsem.tag_service.git_ops.list_local_tags")
    @patch("gitsem.tag_service.git_ops.health_check", return_value="a" * 40)
    def test_annotated_remote_raises(
        self,
        mock_health: MagicMock,
        mock_local: MagicMock,
        mock_remote: MagicMock,
        mock_push: MagicMock,
    ) -> None:
        mock_local.return_value = {
            "1": self._ti(), "1.3": self._ti(), "1.3.4": self._ti(),
        }
        mock_remote.return_value = {
            "1":   self._ti(),             # floating — in sync
            "1.3": self._ti(),             # floating — in sync
            "1.3.4": self._ti(commit=self._OLD, annotated=True),  # annotated, different commit
        }
        from gitsem.tag_service import sync_all

        with self.assertRaises(RemoteConflictError):
            sync_all(force=True)  # force does not override annotated rejection
        mock_push.assert_not_called()

    # ------------------------------------------------------------------
    # head_commit populated from health_check
    # ------------------------------------------------------------------

    @patch("gitsem.tag_service.git_ops.list_remote_tags", return_value={})
    @patch("gitsem.tag_service.git_ops.list_local_tags", return_value={})
    @patch("gitsem.tag_service.git_ops.health_check", return_value="c" * 40)
    def test_head_commit_set(
        self,
        mock_health: MagicMock,
        mock_local: MagicMock,
        mock_remote: MagicMock,
    ) -> None:
        from gitsem.tag_service import sync_all

        result = sync_all(force=False)
        self.assertEqual(result.head_commit, "c" * 40)


class TestRepairFloating(unittest.TestCase):
    """repair_floating() creates/moves floating tags from the exact-tag inventory."""

    def _ti(self, commit: str = "a" * 40, annotated: bool = False) -> TagInfo:
        return TagInfo(commit=commit, annotated=annotated)

    # ------------------------------------------------------------------
    # Empty inventory → empty result, no error
    # ------------------------------------------------------------------

    @patch("gitsem.tag_service.git_ops.list_local_tags", return_value={})
    @patch("gitsem.tag_service.git_ops.health_check", return_value="a" * 40)
    def test_empty_inventory_no_op(
        self, mock_health: MagicMock, mock_local: MagicMock
    ) -> None:
        from gitsem.tag_service import repair_floating

        result = repair_floating(push=False)
        self.assertEqual(result.created, [])
        self.assertEqual(result.moved, [])
        self.assertEqual(result.skipped, [])

    # ------------------------------------------------------------------
    # Missing floating tags → created
    # ------------------------------------------------------------------

    @patch("gitsem.tag_service.git_ops.create_tag")
    @patch("gitsem.tag_service.git_ops.list_local_tags")
    @patch("gitsem.tag_service.git_ops.health_check", return_value="a" * 40)
    def test_creates_missing_floating_tags(
        self,
        mock_health: MagicMock,
        mock_local: MagicMock,
        mock_create: MagicMock,
    ) -> None:
        commit = "c" * 40
        # Only the exact tag exists; floating tags are absent.
        mock_local.return_value = {"1.3.4": self._ti(commit)}
        from gitsem.tag_service import repair_floating

        result = repair_floating(push=False)
        self.assertIn("1", result.created)
        self.assertIn("1.3", result.created)
        self.assertEqual(mock_create.call_count, 2)

    # ------------------------------------------------------------------
    # Floating tags at wrong commit → moved
    # ------------------------------------------------------------------

    @patch("gitsem.tag_service.git_ops.create_tag")
    @patch("gitsem.tag_service.git_ops.delete_local_tag")
    @patch("gitsem.tag_service.git_ops.list_local_tags")
    @patch("gitsem.tag_service.git_ops.health_check", return_value="a" * 40)
    def test_moves_floating_tags_to_correct_commit(
        self,
        mock_health: MagicMock,
        mock_local: MagicMock,
        mock_delete: MagicMock,
        mock_create: MagicMock,
    ) -> None:
        old = "o" * 40
        new = "n" * 40
        mock_local.return_value = {
            "1": self._ti(old),      # floating — wrong commit
            "1.3": self._ti(old),    # floating — wrong commit
            "1.3.4": self._ti(new),  # exact
        }
        from gitsem.tag_service import repair_floating

        result = repair_floating(push=False)
        self.assertIn("1", result.moved)
        self.assertIn("1.3", result.moved)
        self.assertEqual(mock_delete.call_count, 2)
        self.assertEqual(mock_create.call_count, 2)

    # ------------------------------------------------------------------
    # Floating tags already correct → skipped
    # ------------------------------------------------------------------

    @patch("gitsem.tag_service.git_ops.list_local_tags")
    @patch("gitsem.tag_service.git_ops.health_check", return_value="a" * 40)
    def test_skips_correct_floating_tags(
        self,
        mock_health: MagicMock,
        mock_local: MagicMock,
    ) -> None:
        commit = "c" * 40
        mock_local.return_value = {
            "1": self._ti(commit),
            "1.3": self._ti(commit),
            "1.3.4": self._ti(commit),
        }
        from gitsem.tag_service import repair_floating

        result = repair_floating(push=False)
        self.assertIn("1", result.skipped)
        self.assertIn("1.3", result.skipped)
        self.assertEqual(result.moved, [])
        self.assertEqual(result.created, [])

    # ------------------------------------------------------------------
    # Annotated floating tag → TagConflictError
    # ------------------------------------------------------------------

    @patch("gitsem.tag_service.git_ops.list_local_tags")
    @patch("gitsem.tag_service.git_ops.health_check", return_value="a" * 40)
    def test_annotated_floating_tag_raises(
        self,
        mock_health: MagicMock,
        mock_local: MagicMock,
    ) -> None:
        commit = "c" * 40
        mock_local.return_value = {
            "1": self._ti(commit, annotated=True),  # annotated floating
            "1.3": self._ti(commit),
            "1.3.4": self._ti(commit),
        }
        from gitsem.tag_service import repair_floating

        with self.assertRaises(TagConflictError):
            repair_floating(push=False)

    # ------------------------------------------------------------------
    # Mixed-style repo → TagConflictError (via detect_style)
    # ------------------------------------------------------------------

    @patch("gitsem.tag_service.git_ops.list_local_tags")
    @patch("gitsem.tag_service.git_ops.health_check", return_value="a" * 40)
    def test_mixed_style_raises(
        self,
        mock_health: MagicMock,
        mock_local: MagicMock,
    ) -> None:
        mock_local.return_value = {
            "1.3.4": self._ti(),
            "v1.3.5": self._ti(),
        }
        from gitsem.tag_service import repair_floating

        with self.assertRaises(TagConflictError):
            repair_floating(push=False)

    # ------------------------------------------------------------------
    # dry_run=True → no mutations, result populated
    # ------------------------------------------------------------------

    @patch("gitsem.tag_service.git_ops.create_tag")
    @patch("gitsem.tag_service.git_ops.list_local_tags")
    @patch("gitsem.tag_service.git_ops.health_check", return_value="a" * 40)
    def test_dry_run_no_mutations(
        self,
        mock_health: MagicMock,
        mock_local: MagicMock,
        mock_create: MagicMock,
    ) -> None:
        commit = "c" * 40
        mock_local.return_value = {"1.3.4": self._ti(commit)}
        from gitsem.tag_service import repair_floating

        result = repair_floating(push=False, dry_run=True)
        mock_create.assert_not_called()
        self.assertIn("1", result.created)
        self.assertIn("1.3", result.created)
        self.assertTrue(result.dry_run)

    # ------------------------------------------------------------------
    # push=True → remote floating tags pushed
    # ------------------------------------------------------------------

    @patch("gitsem.tag_service.git_ops.push_tag")
    @patch("gitsem.tag_service.git_ops.list_remote_tags", return_value={})
    @patch("gitsem.tag_service.git_ops.create_tag")
    @patch("gitsem.tag_service.git_ops.list_local_tags")
    @patch("gitsem.tag_service.git_ops.health_check", return_value="a" * 40)
    def test_push_pushes_floating_tags(
        self,
        mock_health: MagicMock,
        mock_local: MagicMock,
        mock_create: MagicMock,
        mock_remote: MagicMock,
        mock_push: MagicMock,
    ) -> None:
        commit = "c" * 40
        mock_local.return_value = {"1.3.4": self._ti(commit)}
        from gitsem.tag_service import repair_floating

        result = repair_floating(push=True)
        self.assertIn("1", result.pushed)
        self.assertIn("1.3", result.pushed)
        self.assertEqual(mock_push.call_count, 2)

    # ------------------------------------------------------------------
    # push annotated remote tag → RemoteConflictError
    # ------------------------------------------------------------------

    @patch("gitsem.tag_service.git_ops.push_tag")
    @patch("gitsem.tag_service.git_ops.list_remote_tags")
    @patch("gitsem.tag_service.git_ops.create_tag")
    @patch("gitsem.tag_service.git_ops.list_local_tags")
    @patch("gitsem.tag_service.git_ops.health_check", return_value="a" * 40)
    def test_push_annotated_remote_raises(
        self,
        mock_health: MagicMock,
        mock_local: MagicMock,
        mock_create: MagicMock,
        mock_remote: MagicMock,
        mock_push: MagicMock,
    ) -> None:
        commit = "c" * 40
        old = "o" * 40
        mock_local.return_value = {"1.3.4": self._ti(commit)}
        mock_remote.return_value = {
            "1": TagInfo(commit=old, annotated=True),
        }
        from gitsem.tag_service import repair_floating

        with self.assertRaises(RemoteConflictError):
            repair_floating(push=True)

    # ------------------------------------------------------------------
    # head_commit is set in result
    # ------------------------------------------------------------------

    @patch("gitsem.tag_service.git_ops.list_local_tags", return_value={})
    @patch("gitsem.tag_service.git_ops.health_check", return_value="d" * 40)
    def test_head_commit_set(
        self,
        mock_health: MagicMock,
        mock_local: MagicMock,
    ) -> None:
        from gitsem.tag_service import repair_floating

        result = repair_floating(push=False)
        self.assertEqual(result.head_commit, "d" * 40)

    # ------------------------------------------------------------------
    # MAJOR.MINOR-only repo → only MAJOR float created
    # ------------------------------------------------------------------

    @patch("gitsem.tag_service.git_ops.create_tag")
    @patch("gitsem.tag_service.git_ops.list_local_tags")
    @patch("gitsem.tag_service.git_ops.health_check", return_value="a" * 40)
    def test_minor_only_repo_creates_major_float_only(
        self,
        mock_health: MagicMock,
        mock_local: MagicMock,
        mock_create: MagicMock,
    ) -> None:
        c12, c13 = "1" * 40, "2" * 40
        # 1.2 and 1.3 are both exact (no patch siblings); only '1' float is needed.
        mock_local.return_value = {
            "1.2": self._ti(c12),
            "1.3": self._ti(c13),
        }
        from gitsem.tag_service import repair_floating

        result = repair_floating(push=False)
        self.assertEqual(result.created, ["1"])
        self.assertEqual(mock_create.call_count, 1)
        # Verify the MAJOR float is pointed at the highest minor's commit.
        mock_create.assert_called_once_with("1", c13)


if __name__ == "__main__":
    unittest.main()
