"""Integration tests: real Git repositories via temporary directories."""

import os
import subprocess
import tempfile
import unittest


def _git(args: list[str], cwd: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=check,
    )


def _setup_repo(path: str) -> str:
    """Initialise a bare-minimum Git repo and return the initial commit hash."""
    _git(["init", "-b", "main"], cwd=path)
    _git(["config", "user.email", "test@example.com"], cwd=path)
    _git(["config", "user.name", "Test User"], cwd=path)
    # Create an initial commit so HEAD is valid.
    (os.path.join(path, "README.md"))
    with open(os.path.join(path, "README.md"), "w") as fh:
        fh.write("init\n")
    _git(["add", "README.md"], cwd=path)
    _git(["commit", "-m", "init"], cwd=path)
    result = _git(["rev-parse", "HEAD"], cwd=path)
    return result.stdout.strip()


def _make_commit(path: str, msg: str = "bump") -> str:
    """Create a new commit and return its hash."""
    readme = os.path.join(path, "README.md")
    with open(readme, "a") as fh:
        fh.write(f"{msg}\n")
    _git(["add", "README.md"], cwd=path)
    _git(["commit", "-m", msg], cwd=path)
    result = _git(["rev-parse", "HEAD"], cwd=path)
    return result.stdout.strip()


def _tag_commit(path: str) -> str:
    """Return the commit hash that a tag points to."""
    return ""  # replaced per-use


def _get_tag_commit(path: str, tag: str) -> str:
    result = _git(["rev-parse", f"{tag}^{{}}"], cwd=path)
    return result.stdout.strip()


def _list_tags(path: str) -> list[str]:
    result = _git(["tag", "-l"], cwd=path)
    return [t for t in result.stdout.splitlines() if t]


def _run_gitsem(args: list[str], cwd: str) -> subprocess.CompletedProcess[str]:
    """Run the gitsem CLI inside *cwd* (as a module so no install required)."""
    env = os.environ.copy()
    # Ensure src/ is on PYTHONPATH so gitsem package is importable.
    src_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src")
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{src_dir}:{existing}" if existing else src_dir
    return subprocess.run(
        ["python3", "-m", "gitsem"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


class TestCreateTags(unittest.TestCase):
    """Create tags in a fresh repository."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.repo = self._tmpdir.name
        self.head = _setup_repo(self.repo)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_create_patch_tags_unprefixed(self) -> None:
        result = _run_gitsem(["1.3.4"], self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)
        tags = _list_tags(self.repo)
        self.assertIn("1", tags)
        self.assertIn("1.3", tags)
        self.assertIn("1.3.4", tags)
        for tag in ("1", "1.3", "1.3.4"):
            self.assertEqual(_get_tag_commit(self.repo, tag), self.head)

    def test_create_patch_tags_prefixed(self) -> None:
        result = _run_gitsem(["v1.3.4"], self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)
        tags = _list_tags(self.repo)
        self.assertIn("v1", tags)
        self.assertIn("v1.3", tags)
        self.assertIn("v1.3.4", tags)

    def test_create_minor_tags(self) -> None:
        result = _run_gitsem(["1.3"], self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)
        tags = _list_tags(self.repo)
        self.assertIn("1", tags)
        self.assertIn("1.3", tags)
        self.assertNotIn("1.3.0", tags)

    def test_create_prefixed_minor_tags(self) -> None:
        result = _run_gitsem(["v2.1"], self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)
        tags = _list_tags(self.repo)
        self.assertIn("v2", tags)
        self.assertIn("v2.1", tags)


class TestMoveFloatingTags(unittest.TestCase):
    """Floating tags are moved to the latest HEAD."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.repo = self._tmpdir.name
        self.commit1 = _setup_repo(self.repo)
        # Tag the first commit as 1.3.4.
        _run_gitsem(["1.3.4"], self.repo)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_floating_tags_moved_to_new_head(self) -> None:
        commit2 = _make_commit(self.repo, "release 1.3.5")
        result = _run_gitsem(["1.3.5"], self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)

        # Floating tags must be at commit2.
        self.assertEqual(_get_tag_commit(self.repo, "1"), commit2)
        self.assertEqual(_get_tag_commit(self.repo, "1.3"), commit2)
        # Exact tags must be pinned.
        self.assertEqual(_get_tag_commit(self.repo, "1.3.4"), self.commit1)
        self.assertEqual(_get_tag_commit(self.repo, "1.3.5"), commit2)

    def test_major_floating_tag_follows_latest_minor(self) -> None:
        _make_commit(self.repo, "release 1.4.0")
        _run_gitsem(["1.4.0"], self.repo)
        commit3 = _make_commit(self.repo, "release 2.0.0")
        _run_gitsem(["2.0.0"], self.repo)

        # v2 must be at the 2.0.0 commit.
        self.assertEqual(_get_tag_commit(self.repo, "2"), commit3)
        # v1 must still be at the 1.4.0 commit (not overwritten).
        commit_140 = _get_tag_commit(self.repo, "1.4.0")
        self.assertEqual(_get_tag_commit(self.repo, "1"), commit_140)


class TestIdempotent(unittest.TestCase):
    """Running gitsem twice with the same version is idempotent."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.repo = self._tmpdir.name
        self.head = _setup_repo(self.repo)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_idempotent_patch(self) -> None:
        _run_gitsem(["1.3.4"], self.repo)
        result = _run_gitsem(["1.3.4"], self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)
        for tag in ("1", "1.3", "1.3.4"):
            self.assertEqual(_get_tag_commit(self.repo, tag), self.head)

    def test_idempotent_minor(self) -> None:
        _run_gitsem(["1.3"], self.repo)
        result = _run_gitsem(["1.3"], self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)


class TestExactTagConflict(unittest.TestCase):
    """Exact release tags on a different commit must be rejected."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.repo = self._tmpdir.name
        _setup_repo(self.repo)
        _run_gitsem(["1.3.4"], self.repo)
        _make_commit(self.repo, "second commit")

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_exact_conflict_exits_nonzero(self) -> None:
        result = _run_gitsem(["1.3.4"], self.repo)
        self.assertEqual(result.returncode, 4, result.stderr)
        self.assertIn("1.3.4", result.stderr)


class TestStyleMismatch(unittest.TestCase):
    """Style-mismatch detection and --migrate migration."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.repo = self._tmpdir.name
        _setup_repo(self.repo)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_mismatch_rejected_without_switch(self) -> None:
        _run_gitsem(["1.3.4"], self.repo)
        result = _run_gitsem(["v1.3.5"], self.repo)
        self.assertEqual(result.returncode, 3, result.stderr)

    def test_mismatch_allowed_with_migrate(self) -> None:
        _run_gitsem(["1.3.4"], self.repo)
        _make_commit(self.repo, "next")
        result = _run_gitsem(["--migrate", "v1.3.5"], self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)
        tags = _list_tags(self.repo)
        # New-style tags must exist.
        for tag in ("v1", "v1.3", "v1.3.5"):
            self.assertIn(tag, tags)
        # Old-style tags must be gone.
        for tag in ("1", "1.3", "1.3.4"):
            self.assertNotIn(tag, tags)

    def test_migrate_migrates_all_historical_tags(self) -> None:
        """--migrate must rename ALL historical managed tags, not just the current family."""
        _run_gitsem(["1.2.3"], self.repo)
        _make_commit(self.repo, "bump")
        _run_gitsem(["1.3.4"], self.repo)
        _make_commit(self.repo, "new")
        result = _run_gitsem(["--migrate", "v1.3.5"], self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)
        tags = _list_tags(self.repo)
        for tag in ("v1.2.3", "v1.3.4"):
            self.assertIn(tag, tags, f"expected migrated tag {tag!r} not found")
        for tag in ("1.2.3", "1.3.4"):
            self.assertNotIn(tag, tags, f"old-style tag {tag!r} should have been removed")

    def test_prefixed_repo_rejects_unprefixed(self) -> None:
        _run_gitsem(["v1.3.4"], self.repo)
        result = _run_gitsem(["1.3.5"], self.repo)
        self.assertEqual(result.returncode, 3, result.stderr)


class TestMinorToPathDepthTransition(unittest.TestCase):
    """Repositories can upgrade from MAJOR.MINOR to MAJOR.MINOR.PATCH releases."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.repo = self._tmpdir.name
        _setup_repo(self.repo)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_transition_from_minor_to_patch(self) -> None:
        commit1 = _get_tag_commit(self.repo, "HEAD") if False else None
        # Release 1.3 with minor-only style.
        _run_gitsem(["1.3"], self.repo)
        commit_13 = _get_tag_commit(self.repo, "1.3")

        # Now make a second commit and release 1.3.0 — 1.3 becomes floating.
        commit2 = _make_commit(self.repo, "patch release")
        result = _run_gitsem(["1.3.0"], self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)

        tags = _list_tags(self.repo)
        self.assertIn("1.3.0", tags)
        # 1.3 (floating) must now point to the new commit.
        self.assertEqual(_get_tag_commit(self.repo, "1.3"), commit2)
        # 1 (floating) must also be at the new commit.
        self.assertEqual(_get_tag_commit(self.repo, "1"), commit2)

    def test_minor_only_repository(self) -> None:
        _run_gitsem(["1.3"], self.repo)
        _make_commit(self.repo, "next minor")
        result = _run_gitsem(["1.4"], self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)
        tags = _list_tags(self.repo)
        self.assertIn("1.4", tags)
        # 1 (floating) must be at 1.4.
        commit_14 = _get_tag_commit(self.repo, "1.4")
        self.assertEqual(_get_tag_commit(self.repo, "1"), commit_14)

    def test_historical_minor_tag_preserved_after_transition(self) -> None:
        _run_gitsem(["1.2"], self.repo)
        commit_12 = _get_tag_commit(self.repo, "1.2")
        _make_commit(self.repo, "next")
        _run_gitsem(["1.3.0"], self.repo)
        # 1.2 was an exact tag for the MAJOR.MINOR release; it must still exist.
        self.assertIn("1.2", _list_tags(self.repo))
        self.assertEqual(_get_tag_commit(self.repo, "1.2"), commit_12)


class TestAnnotatedTagRejection(unittest.TestCase):
    """Annotated managed tags must be rejected."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.repo = self._tmpdir.name
        _setup_repo(self.repo)
        # Create an annotated tag manually.
        _git(["tag", "-a", "1.3.4", "-m", "annotated release"], cwd=self.repo)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_annotated_exact_rejected(self) -> None:
        result = _run_gitsem(["1.3.4"], self.repo)
        self.assertEqual(result.returncode, 4, result.stderr)

    def test_annotated_floating_rejected(self) -> None:
        _git(["tag", "-a", "1", "-m", "annotated major"], cwd=self.repo)
        result = _run_gitsem(["1.3.5"], self.repo)
        self.assertEqual(result.returncode, 4, result.stderr)


class TestRemotePush(unittest.TestCase):
    """Push tests using a local bare repository as 'origin'."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        root = self._tmpdir.name
        self.repo = os.path.join(root, "repo")
        self.remote = os.path.join(root, "remote.git")
        os.makedirs(self.repo)
        os.makedirs(self.remote)

        # Initialise bare remote.
        _git(["init", "--bare", "-b", "main"], cwd=self.remote)
        # Initialise working repo.
        self.head = _setup_repo(self.repo)
        _git(["remote", "add", "origin", self.remote], cwd=self.repo)
        # Push the initial commit so the remote has the same history.
        _git(["push", "origin", "main"], cwd=self.repo)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _remote_tags(self) -> list[str]:
        result = _git(["ls-remote", "--tags", "origin"], cwd=self.repo)
        tags = []
        for line in result.stdout.splitlines():
            parts = line.split("\t", 1)
            if len(parts) == 2:
                ref = parts[1]
                if not ref.endswith("^{}") and ref.startswith("refs/tags/"):
                    tags.append(ref[len("refs/tags/"):])
        return tags

    def _remote_tag_commit(self, tag: str) -> str:
        result = _git(["ls-remote", "origin", f"refs/tags/{tag}"], cwd=self.repo)
        return result.stdout.split("\t")[0].strip() if result.stdout else ""

    def test_push_creates_remote_tags(self) -> None:
        result = _run_gitsem(["--push", "1.3.4"], self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)
        remote = self._remote_tags()
        for tag in ("1", "1.3", "1.3.4"):
            self.assertIn(tag, remote)

    def test_push_idempotent(self) -> None:
        _run_gitsem(["--push", "1.3.4"], self.repo)
        result = _run_gitsem(["--push", "1.3.4"], self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_push_missing_origin_exits_nonzero(self) -> None:
        # Remove origin and push.
        _git(["remote", "remove", "origin"], cwd=self.repo)
        result = _run_gitsem(["--push", "1.3.4"], self.repo)
        self.assertNotEqual(result.returncode, 0)

    def test_push_moves_remote_floating_tags(self) -> None:
        _run_gitsem(["--push", "1.3.4"], self.repo)
        commit2 = _make_commit(self.repo, "next release")
        _git(["push", "origin", "main"], cwd=self.repo)
        result = _run_gitsem(["--push", "1.3.5"], self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)
        # Remote floating tag '1' must now be at commit2.
        self.assertEqual(self._remote_tag_commit("1"), commit2)
        self.assertEqual(self._remote_tag_commit("1.3"), commit2)

    def test_remote_exact_conflict_rejected_without_force(self) -> None:
        """Remote exact tag on a different commit → rejected unless --force."""
        # Push 1.3.4 to remote.
        _run_gitsem(["--push", "1.3.4"], self.repo)
        # Make a new commit and try to push 1.3.4 again (conflict on exact).
        _make_commit(self.repo, "second")
        _git(["push", "origin", "main"], cwd=self.repo)
        # Delete local exact tag and recreate on new HEAD.
        _git(["tag", "-d", "1.3.4"], cwd=self.repo)
        _git(["tag", "1.3.4"], cwd=self.repo)
        result = _run_gitsem(["--push", "1.3.4"], self.repo)
        self.assertEqual(result.returncode, 5, result.stderr)

    def test_remote_conflict_repaired_with_force(self) -> None:
        """Remote conflicting managed tags are repaired when --force is supplied."""
        _run_gitsem(["--push", "1.3.4"], self.repo)
        commit2 = _make_commit(self.repo, "second")
        _git(["push", "origin", "main"], cwd=self.repo)
        # Delete local exact tag and recreate on new HEAD.
        _git(["tag", "-d", "1.3.4"], cwd=self.repo)
        _git(["tag", "1.3.4"], cwd=self.repo)
        result = _run_gitsem(["--push", "--force", "1.3.4"], self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self._remote_tag_commit("1.3.4"), commit2)

    def test_remote_annotated_tag_rejected(self) -> None:
        """Remote annotated managed tag → rejected even with --force."""
        # Create an annotated tag on the remote directly.
        _git(["tag", "-a", "1.3.4", "-m", "annotated"], cwd=self.repo)
        _git(["push", "origin", "refs/tags/1.3.4"], cwd=self.repo)
        # Delete local annotated tag so we can recreate as lightweight.
        _git(["tag", "-d", "1.3.4"], cwd=self.repo)
        commit2 = _make_commit(self.repo, "second")
        _git(["push", "origin", "main"], cwd=self.repo)
        _git(["tag", "1.3.4"], cwd=self.repo)
        result = _run_gitsem(["--push", "--force", "1.3.4"], self.repo)
        self.assertEqual(result.returncode, 5, result.stderr)


class TestInvalidInput(unittest.TestCase):
    """Invalid version strings exit with code 1."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.repo = self._tmpdir.name
        _setup_repo(self.repo)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_invalid_version_exit_1(self) -> None:
        for bad in ("1", "1.2.3.4", "1.2.3-alpha", "latest", ""):
            with self.subTest(version=bad):
                result = _run_gitsem([bad] if bad else ["--help"], self.repo)
                # --help exits 0, everything else invalid exits non-zero.
                if bad:
                    self.assertNotEqual(result.returncode, 0)


class TestUnhealthyRepository(unittest.TestCase):
    """Operations outside a Git repository exit with code 2."""

    def test_not_in_repo_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _run_gitsem(["1.3.4"], tmpdir)
            self.assertEqual(result.returncode, 2, result.stderr)


class TestDryRun(unittest.TestCase):
    """--dry-run validates and plans without making any mutations."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.repo = self._tmpdir.name
        self.head = _setup_repo(self.repo)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_dry_run_creates_no_tags(self) -> None:
        result = _run_gitsem(["--dry-run", "1.3.4"], self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(_list_tags(self.repo), [])

    def test_dry_run_exits_zero_on_clean_repo(self) -> None:
        result = _run_gitsem(["--dry-run", "1.3.4"], self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_dry_run_still_detects_exact_tag_conflict(self) -> None:
        _run_gitsem(["1.3.4"], self.repo)
        _make_commit(self.repo, "second")
        # Conflict on exact tag must still be detected in dry-run.
        result = _run_gitsem(["--dry-run", "1.3.4"], self.repo)
        self.assertEqual(result.returncode, 4, result.stderr)

    def test_dry_run_still_detects_style_mismatch(self) -> None:
        _run_gitsem(["1.3.4"], self.repo)
        result = _run_gitsem(["--dry-run", "v1.3.5"], self.repo)
        self.assertEqual(result.returncode, 3, result.stderr)

    def test_dry_run_output_contains_would_phrasing(self) -> None:
        result = _run_gitsem(["--dry-run", "1.3.4"], self.repo)
        self.assertIn("would", result.stdout)

    def test_dry_run_output_contains_dry_run_suffix(self) -> None:
        result = _run_gitsem(["--dry-run", "1.3.4"], self.repo)
        self.assertIn("dry run", result.stdout)


class TestPorcelainOutput(unittest.TestCase):
    """--porcelain emits machine-readable output parseable by scripts."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.repo = self._tmpdir.name
        self.head = _setup_repo(self.repo)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    @staticmethod
    def _parse(output: str) -> dict:
        """Parse porcelain output into a dict with a 'tags' sub-dict."""
        parsed: dict = {"tags": {}}
        for line in output.splitlines():
            parts = line.split(None, 1)
            if not parts:
                continue
            key = parts[0]
            value = parts[1] if len(parts) > 1 else ""
            if key in ("head", "status", "dry-run"):
                parsed[key] = value
            else:
                parsed["tags"].setdefault(key, []).append(value)
        return parsed

    def test_porcelain_create(self) -> None:
        result = _run_gitsem(["--porcelain", "1.3.4"], self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)
        parsed = self._parse(result.stdout)
        self.assertEqual(parsed.get("head"), self.head)
        self.assertEqual(parsed.get("status"), "ok")
        self.assertIn("1.3.4", parsed["tags"].get("created", []))
        self.assertIn("1.3", parsed["tags"].get("created", []))
        self.assertIn("1", parsed["tags"].get("created", []))

    def test_porcelain_status_ok_always_last(self) -> None:
        result = _run_gitsem(["--porcelain", "1.3.4"], self.repo)
        self.assertTrue(result.stdout.strip().endswith("status ok"))

    def test_porcelain_dry_run_line(self) -> None:
        result = _run_gitsem(["--porcelain", "--dry-run", "1.3.4"], self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)
        parsed = self._parse(result.stdout)
        self.assertEqual(parsed.get("dry-run"), "true")
        # No actual tags created.
        self.assertEqual(_list_tags(self.repo), [])

    def test_porcelain_no_dry_run_line_when_not_set(self) -> None:
        result = _run_gitsem(["--porcelain", "1.3.4"], self.repo)
        self.assertNotIn("dry-run", result.stdout)

    def test_porcelain_skipped_when_idempotent(self) -> None:
        _run_gitsem(["1.3.4"], self.repo)
        result = _run_gitsem(["--porcelain", "1.3.4"], self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)
        parsed = self._parse(result.stdout)
        skipped = parsed["tags"].get("skipped", [])
        self.assertIn("1.3.4", skipped)
        self.assertIn("1.3", skipped)
        self.assertIn("1", skipped)

    def test_porcelain_moved_tags(self) -> None:
        _run_gitsem(["1.3.4"], self.repo)
        _make_commit(self.repo, "release 1.3.5")
        result = _run_gitsem(["--porcelain", "1.3.5"], self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)
        parsed = self._parse(result.stdout)
        self.assertIn("1", parsed["tags"].get("moved", []))
        self.assertIn("1.3", parsed["tags"].get("moved", []))
        self.assertIn("1.3.5", parsed["tags"].get("created", []))


class TestErrorFormat(unittest.TestCase):
    """Errors are emitted as error[token]: message with optional hint: line."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.repo = self._tmpdir.name
        _setup_repo(self.repo)
        _run_gitsem(["1.3.4"], self.repo)
        _make_commit(self.repo, "second commit")

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_error_token_format_on_conflict(self) -> None:
        result = _run_gitsem(["1.3.4"], self.repo)
        self.assertEqual(result.returncode, 4)
        self.assertIn("error[tag-conflict]:", result.stderr)

    def test_hint_line_on_conflict(self) -> None:
        result = _run_gitsem(["1.3.4"], self.repo)
        self.assertEqual(result.returncode, 4)
        self.assertIn("hint:", result.stderr)

    def test_style_mismatch_token(self) -> None:
        result = _run_gitsem(["v1.3.5"], self.repo)
        self.assertEqual(result.returncode, 3)
        self.assertIn("error[style-mismatch]:", result.stderr)


class TestSyncAllIntegration(unittest.TestCase):
    """Integration tests for `gitsem --push` (no version) using a real bare remote."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        root = self._tmpdir.name
        self.repo = os.path.join(root, "repo")
        self.remote = os.path.join(root, "remote.git")
        os.makedirs(self.repo)
        os.makedirs(self.remote)

        _git(["init", "--bare", "-b", "main"], cwd=self.remote)
        self.head = _setup_repo(self.repo)
        _git(["remote", "add", "origin", self.remote], cwd=self.repo)
        _git(["push", "origin", "main"], cwd=self.repo)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _remote_tags(self) -> list[str]:
        result = _git(["ls-remote", "--tags", "origin"], cwd=self.repo)
        tags = []
        for line in result.stdout.splitlines():
            parts = line.split("\t", 1)
            if len(parts) == 2:
                ref = parts[1]
                if not ref.endswith("^{}") and ref.startswith("refs/tags/"):
                    tags.append(ref[len("refs/tags/"):])
        return tags

    def _remote_tag_commit(self, tag: str) -> str:
        result = _git(["ls-remote", "origin", f"refs/tags/{tag}"], cwd=self.repo)
        return result.stdout.split("\t")[0].strip() if result.stdout else ""

    def test_local_tags_exist_none_on_remote_synced(self) -> None:
        """Local tags present, none on remote → all pushed by --push (no version)."""
        _run_gitsem(["1.3.4"], self.repo)
        result = _run_gitsem(["--push"], self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)
        remote = self._remote_tags()
        for tag in ("1", "1.3", "1.3.4"):
            self.assertIn(tag, remote)

    def test_idempotent_all_already_synced(self) -> None:
        """Running --push again when remote is already up to date exits 0."""
        _run_gitsem(["--push", "1.3.4"], self.repo)
        result = _run_gitsem(["--push"], self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_no_local_managed_tags_no_op(self) -> None:
        """Repository with no managed tags → exit 0, nothing pushed."""
        result = _run_gitsem(["--push"], self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self._remote_tags(), [])

    def test_dry_run_push_no_remote_mutations(self) -> None:
        """--dry-run --push must not push anything to the remote."""
        _run_gitsem(["1.3.4"], self.repo)
        result = _run_gitsem(["--dry-run", "--push"], self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self._remote_tags(), [])

    def test_porcelain_push_machine_readable(self) -> None:
        """--porcelain --push emits pushed lines and status ok."""
        _run_gitsem(["1.3.4"], self.repo)
        result = _run_gitsem(["--porcelain", "--push"], self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = result.stdout.splitlines()
        self.assertIn("pushed 1", lines)
        self.assertIn("pushed 1.3", lines)
        self.assertIn("pushed 1.3.4", lines)
        self.assertTrue(result.stdout.strip().endswith("status ok"))

    def test_exact_tag_conflict_without_force_exits_5(self) -> None:
        """Remote exact tag at a different commit → exit 5 without --force."""
        _run_gitsem(["--push", "1.3.4"], self.repo)
        commit2 = _make_commit(self.repo, "second")
        _git(["push", "origin", "main"], cwd=self.repo)
        # Recreate local exact tag on new HEAD.
        _git(["tag", "-d", "1.3.4"], cwd=self.repo)
        _git(["tag", "1.3.4"], cwd=self.repo)
        result = _run_gitsem(["--push"], self.repo)
        self.assertEqual(result.returncode, 5, result.stderr)

    def test_exact_tag_conflict_repaired_with_force(self) -> None:
        """Remote exact tag conflict is repaired when --force is supplied."""
        _run_gitsem(["--push", "1.3.4"], self.repo)
        commit2 = _make_commit(self.repo, "second")
        _git(["push", "origin", "main"], cwd=self.repo)
        _git(["tag", "-d", "1.3.4"], cwd=self.repo)
        _git(["tag", "1.3.4"], cwd=self.repo)
        result = _run_gitsem(["--push", "--force"], self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self._remote_tag_commit("1.3.4"), commit2)

    def test_floating_tag_out_of_sync_moved_without_force(self) -> None:
        """Floating remote tags out of sync are updated without --force."""
        _run_gitsem(["--push", "1.3.4"], self.repo)
        commit2 = _make_commit(self.repo, "next")
        _git(["push", "origin", "main"], cwd=self.repo)
        _run_gitsem(["1.3.5"], self.repo)
        result = _run_gitsem(["--push"], self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)
        # Floating tag '1' must now point to commit2.
        self.assertEqual(self._remote_tag_commit("1"), commit2)
        self.assertEqual(self._remote_tag_commit("1.3"), commit2)


if __name__ == "__main__":
    unittest.main()
