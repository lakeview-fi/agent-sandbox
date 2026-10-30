"""Unit tests for the shared helpers: review-path detection and the clean-tree guard."""
import tempfile
import unittest
from pathlib import Path

from tests.scripts import gitfixtures as fx

import sandbox_git_common as sg  # noqa: E402  (scripts/ is put on sys.path by gitfixtures)


class NeedsReviewTest(unittest.TestCase):
    def test_flags_files_that_execute_or_configure_later(self):
        for path in (".github/workflows/ci.yml", ".githooks/pre-commit", "sandbox/policy.yaml", "scripts/run.sh",
                     "Makefile", "pyproject.toml", "deploy/Dockerfile.prod", "AGENTS.md", "tools/setup.ps1"):
            self.assertTrue(sg.needs_review(path), path)

    def test_ignores_ordinary_source_files(self):
        for path in ("src/app.py", "docs/index.md", "tests/test_app.py", "README.md"):
            self.assertFalse(sg.needs_review(path), path)


class RepoGuardsTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = fx.make_repo(Path(self._tmp.name) / "r", {"a.txt": "a\n"})

    def tearDown(self):
        self._tmp.cleanup()

    def test_require_clean_rejects_modified_tracked_file(self):
        (self.repo / "a.txt").write_text("changed\n")
        with self.assertRaises(sg.Fail):
            sg.require_clean(self.repo)

    def test_require_clean_allows_untracked_files(self):
        (self.repo / "new.txt").write_text("new\n")
        sg.require_clean(self.repo)

    def test_repo_root_outside_a_repo_fails(self):
        with tempfile.TemporaryDirectory() as plain, self.assertRaises(sg.Fail):
            sg.repo_root(plain)


if __name__ == "__main__":
    unittest.main()
