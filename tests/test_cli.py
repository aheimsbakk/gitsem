"""Unit tests for gitsem.cli — argument parsing and exit-code mapping."""

import sys
import unittest
from io import StringIO
from unittest.mock import MagicMock, patch

from gitsem.errors import (
    GitExecutionError,
    InvalidVersionError,
    RemoteConflictError,
    RemotePermissionError,
    StyleMismatchError,
    TagConflictError,
    UnhealthyRepositoryError,
)


class TestExitCodes(unittest.TestCase):
    """main() maps each GitsemError subclass to the correct exit code."""

    _CASES = [
        (InvalidVersionError("bad version"), 1),
        (UnhealthyRepositoryError("no repo"), 2),
        (StyleMismatchError("wrong style"), 3),
        (TagConflictError("tag conflict"), 4),
        (RemoteConflictError("remote conflict"), 5),
        (RemotePermissionError("permission denied"), 6),
        (GitExecutionError("git failed"), 7),
    ]

    def _run_main(self, exc: Exception) -> int:
        from gitsem.cli import main

        with patch("gitsem.tag_service.apply", side_effect=exc):
            with self.assertRaises(SystemExit) as ctx:
                main(["1.3.4"])
        return ctx.exception.code  # type: ignore[return-value]

    def test_exit_codes(self) -> None:
        for exc, expected_code in self._CASES:
            with self.subTest(exc=type(exc).__name__):
                code = self._run_main(exc)
                self.assertEqual(code, expected_code)

    def test_success_exits_zero(self) -> None:
        from gitsem.cli import main
        from gitsem.tag_service import ApplyResult

        with patch(
            "gitsem.tag_service.apply",
            return_value=ApplyResult(created=["1", "1.3", "1.3.4"]),
        ):
            with self.assertRaises(SystemExit) as ctx:
                main(["1.3.4"])
        self.assertEqual(ctx.exception.code, 0)


class TestArgParsing(unittest.TestCase):
    """CLI arguments are forwarded correctly to tag_service.apply()."""

    def _capture_apply_kwargs(self, argv: list[str]) -> dict:
        from gitsem.cli import main
        from gitsem.tag_service import ApplyResult

        captured: dict = {}

        def fake_apply(version_str: str, **kwargs: object) -> ApplyResult:
            captured["version_str"] = version_str
            captured.update(kwargs)
            return ApplyResult()

        with patch("gitsem.tag_service.apply", side_effect=fake_apply):
            with self.assertRaises(SystemExit):
                main(argv)

        return captured

    def test_push_flag(self) -> None:
        kw = self._capture_apply_kwargs(["--push", "1.3.4"])
        self.assertTrue(kw["push"])

    def test_force_flag(self) -> None:
        kw = self._capture_apply_kwargs(["--force", "1.3.4"])
        self.assertTrue(kw["force"])

    def test_switch_flag(self) -> None:
        kw = self._capture_apply_kwargs(["--switch", "v1.3.4"])
        self.assertTrue(kw["switch"])

    def test_verbose_flag(self) -> None:
        kw = self._capture_apply_kwargs(["-v", "1.3.4"])
        self.assertTrue(kw["verbose"])

    def test_dry_run_flag(self) -> None:
        kw = self._capture_apply_kwargs(["--dry-run", "1.3.4"])
        self.assertTrue(kw["dry_run"])

    def test_version_string_forwarded(self) -> None:
        kw = self._capture_apply_kwargs(["v2.1.0"])
        self.assertEqual(kw["version_str"], "v2.1.0")

    def test_defaults_all_false(self) -> None:
        kw = self._capture_apply_kwargs(["1.0.0"])
        self.assertFalse(kw["push"])
        self.assertFalse(kw["force"])
        self.assertFalse(kw["switch"])
        self.assertFalse(kw["verbose"])
        self.assertFalse(kw["dry_run"])


class TestVersionFlag(unittest.TestCase):
    """-V / --version prints version and exits 0."""

    def test_version_flag(self) -> None:
        from gitsem.cli import main

        buf = StringIO()
        with patch("sys.stdout", buf):
            with self.assertRaises(SystemExit) as ctx:
                main(["--version"])
        self.assertEqual(ctx.exception.code, 0)
        self.assertIn("gitsem", buf.getvalue())


class TestErrorFormat(unittest.TestCase):
    """_err() emits structured error[token]: message and optional hint lines."""

    def _capture_stderr(self, exc: Exception) -> str:
        from gitsem.cli import _err

        buf = StringIO()
        with patch("sys.stderr", buf):
            _err(exc)
        return buf.getvalue()

    def test_gitsem_error_token_format(self) -> None:
        exc = TagConflictError("some conflict")
        output = self._capture_stderr(exc)
        self.assertIn("error[tag-conflict]:", output)
        self.assertIn("some conflict", output)

    def test_gitsem_error_hint_emitted(self) -> None:
        exc = TagConflictError("conflict msg", hint="try this fix")
        output = self._capture_stderr(exc)
        self.assertIn("hint: try this fix", output)

    def test_gitsem_error_no_hint_when_none(self) -> None:
        exc = TagConflictError("conflict msg")
        output = self._capture_stderr(exc)
        self.assertNotIn("hint:", output)

    def test_plain_exception_format(self) -> None:
        exc = ValueError("something broke")
        output = self._capture_stderr(exc)
        self.assertIn("error: something broke", output)
        self.assertNotIn("error[", output)

    def test_all_error_tokens(self) -> None:
        cases = [
            (InvalidVersionError("x"), "invalid-version"),
            (UnhealthyRepositoryError("x"), "unhealthy-repo"),
            (StyleMismatchError("x"), "style-mismatch"),
            (TagConflictError("x"), "tag-conflict"),
            (RemoteConflictError("x"), "remote-conflict"),
            (RemotePermissionError("x"), "remote-permission"),
            (GitExecutionError("x"), "git-execution"),
        ]
        for exc, expected_token in cases:
            with self.subTest(token=expected_token):
                output = self._capture_stderr(exc)
                self.assertIn(f"error[{expected_token}]:", output)


class TestPorcelainOutput(unittest.TestCase):
    """--porcelain emits machine-readable lines to stdout."""

    def _run_with_result(
        self, result: object, argv: list[str]
    ) -> str:
        from gitsem.cli import main

        buf = StringIO()
        with patch("gitsem.tag_service.apply", return_value=result):
            with patch("sys.stdout", buf):
                with self.assertRaises(SystemExit):
                    main(argv)
        return buf.getvalue()

    def test_porcelain_head_and_status(self) -> None:
        from gitsem.tag_service import ApplyResult

        result = ApplyResult(head_commit="a" * 40, created=["1", "1.3", "1.3.4"])
        output = self._run_with_result(result, ["--porcelain", "1.3.4"])
        lines = output.splitlines()
        self.assertIn(f"head {'a' * 40}", lines)
        self.assertIn("status ok", lines)
        self.assertTrue(output.strip().endswith("status ok"))

    def test_porcelain_created_lines(self) -> None:
        from gitsem.tag_service import ApplyResult

        result = ApplyResult(head_commit="a" * 40, created=["1", "1.3", "1.3.4"])
        output = self._run_with_result(result, ["--porcelain", "1.3.4"])
        lines = output.splitlines()
        self.assertIn("created 1", lines)
        self.assertIn("created 1.3", lines)
        self.assertIn("created 1.3.4", lines)

    def test_porcelain_dry_run_line_present(self) -> None:
        from gitsem.tag_service import ApplyResult

        result = ApplyResult(
            head_commit="b" * 40, created=["1.3.4"], dry_run=True
        )
        output = self._run_with_result(result, ["--porcelain", "--dry-run", "1.3.4"])
        self.assertIn("dry-run true", output.splitlines())

    def test_porcelain_no_dry_run_line_when_false(self) -> None:
        from gitsem.tag_service import ApplyResult

        result = ApplyResult(head_commit="c" * 40, created=["1.3.4"])
        output = self._run_with_result(result, ["--porcelain", "1.3.4"])
        self.assertNotIn("dry-run", output)

    def test_porcelain_skipped_always_shown(self) -> None:
        from gitsem.tag_service import ApplyResult

        result = ApplyResult(
            head_commit="d" * 40,
            skipped=["1", "1.3", "1.3.4"],
        )
        output = self._run_with_result(result, ["--porcelain", "1.3.4"])
        lines = output.splitlines()
        self.assertIn("skipped 1", lines)
        self.assertIn("skipped 1.3", lines)
        self.assertIn("skipped 1.3.4", lines)

    def test_porcelain_remote_skipped_always_shown(self) -> None:
        from gitsem.tag_service import ApplyResult

        result = ApplyResult(
            head_commit="e" * 40,
            remote_skipped=["1", "1.3", "1.3.4"],
        )
        output = self._run_with_result(result, ["--porcelain", "1.3.4"])
        lines = output.splitlines()
        self.assertIn("remote-skipped 1", lines)
        self.assertIn("remote-skipped 1.3", lines)

    def test_porcelain_moved_lines(self) -> None:
        from gitsem.tag_service import ApplyResult

        result = ApplyResult(
            head_commit="f" * 40,
            moved=["1", "1.3"],
            created=["1.3.5"],
        )
        output = self._run_with_result(result, ["--porcelain", "1.3.5"])
        lines = output.splitlines()
        self.assertIn("moved 1", lines)
        self.assertIn("moved 1.3", lines)
        self.assertIn("created 1.3.5", lines)


class TestQuietOutput(unittest.TestCase):
    """-q / --quiet suppresses per-tag lines; summary and no HEAD shown."""

    def _run_with_result(
        self, result: object, argv: list[str]
    ) -> str:
        from gitsem.cli import main

        buf = StringIO()
        with patch("gitsem.tag_service.apply", return_value=result):
            with patch("sys.stdout", buf):
                with self.assertRaises(SystemExit):
                    main(argv)
        return buf.getvalue()

    def test_quiet_no_head_shown(self) -> None:
        from gitsem.tag_service import ApplyResult

        result = ApplyResult(head_commit="a" * 40, created=["1.3.4"])
        output = self._run_with_result(result, ["-q", "1.3.4"])
        self.assertNotIn("HEAD:", output)

    def test_quiet_summary_present(self) -> None:
        from gitsem.tag_service import ApplyResult

        result = ApplyResult(head_commit="a" * 40, created=["1", "1.3", "1.3.4"])
        output = self._run_with_result(result, ["-q", "1.3.4"])
        self.assertIn("3 created", output)

    def test_quiet_no_per_tag_names(self) -> None:
        from gitsem.tag_service import ApplyResult

        # Per-tag lines would contain individual tag names; the summary does not.
        result = ApplyResult(head_commit="a" * 40, created=["1", "1.3", "1.3.4"])
        output = self._run_with_result(result, ["-q", "1.3.4"])
        # Summary says "3 created" — individual tag names are absent.
        self.assertNotIn("1.3.4", output)
        self.assertNotIn("1.3\n", output)

    def test_quiet_long_form(self) -> None:
        from gitsem.tag_service import ApplyResult

        result = ApplyResult(head_commit="b" * 40, created=["1.3.4"])
        out_short = self._run_with_result(result, ["-q", "1.3.4"])
        out_long = self._run_with_result(result, ["--quiet", "1.3.4"])
        self.assertEqual(out_short, out_long)

    def test_quiet_already_up_to_date(self) -> None:
        from gitsem.tag_service import ApplyResult

        result = ApplyResult(
            head_commit="c" * 40,
            skipped=["1", "1.3", "1.3.4"],
        )
        output = self._run_with_result(result, ["-q", "1.3.4"])
        self.assertIn("already up to date", output)
        self.assertNotIn("HEAD:", output)


class TestDryRunOutput(unittest.TestCase):
    """--dry-run output uses 'would ...' phrasing and appends (dry run) suffix."""

    def _run_with_result(
        self, result: object, argv: list[str]
    ) -> str:
        from gitsem.cli import main

        buf = StringIO()
        with patch("gitsem.tag_service.apply", return_value=result):
            with patch("sys.stdout", buf):
                with self.assertRaises(SystemExit):
                    main(argv)
        return buf.getvalue()

    def test_dry_run_would_create_in_per_tag_lines(self) -> None:
        from gitsem.tag_service import ApplyResult

        result = ApplyResult(
            head_commit="a" * 40,
            created=["1", "1.3", "1.3.4"],
            dry_run=True,
        )
        output = self._run_with_result(result, ["--dry-run", "1.3.4"])
        self.assertIn("would create", output)

    def test_dry_run_summary_dry_run_suffix(self) -> None:
        from gitsem.tag_service import ApplyResult

        result = ApplyResult(
            head_commit="a" * 40,
            created=["1", "1.3", "1.3.4"],
            dry_run=True,
        )
        output = self._run_with_result(result, ["--dry-run", "1.3.4"])
        self.assertIn("(dry run)", output)

    def test_dry_run_summary_would_be_created(self) -> None:
        from gitsem.tag_service import ApplyResult

        result = ApplyResult(
            head_commit="a" * 40,
            created=["1", "1.3", "1.3.4"],
            dry_run=True,
        )
        output = self._run_with_result(result, ["--dry-run", "1.3.4"])
        self.assertIn("would be created", output)

    def test_dry_run_forwarded_to_apply(self) -> None:
        from gitsem.cli import main
        from gitsem.tag_service import ApplyResult

        captured: dict = {}

        def fake_apply(version_str: str, **kwargs: object) -> ApplyResult:
            captured.update(kwargs)
            return ApplyResult()

        with patch("gitsem.tag_service.apply", side_effect=fake_apply):
            with self.assertRaises(SystemExit):
                main(["--dry-run", "1.3.4"])

        self.assertTrue(captured.get("dry_run"))

    def test_dry_run_moved_phrasing(self) -> None:
        from gitsem.tag_service import ApplyResult

        result = ApplyResult(
            head_commit="b" * 40,
            moved=["1", "1.3"],
            created=["1.3.5"],
            dry_run=True,
        )
        output = self._run_with_result(result, ["--dry-run", "1.3.5"])
        self.assertIn("would move", output)
        self.assertIn("would be moved", output)


if __name__ == "__main__":
    unittest.main()
