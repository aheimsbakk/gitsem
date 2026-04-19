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

    def test_version_string_forwarded(self) -> None:
        kw = self._capture_apply_kwargs(["v2.1.0"])
        self.assertEqual(kw["version_str"], "v2.1.0")

    def test_defaults_all_false(self) -> None:
        kw = self._capture_apply_kwargs(["1.0.0"])
        self.assertFalse(kw["push"])
        self.assertFalse(kw["force"])
        self.assertFalse(kw["switch"])
        self.assertFalse(kw["verbose"])


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


if __name__ == "__main__":
    unittest.main()
