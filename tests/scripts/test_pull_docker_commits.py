"""pull_docker_commits.py against a local repo standing in for the sandbox's git daemon."""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from tests.scripts import gitfixtures as fx

import pull_docker_commits as pdc  # noqa: E402  (scripts/ is put on sys.path by gitfixtures)


def run(*argv: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = pdc.main(list(argv))
    return code, out.getvalue(), err.getvalue()


class PullDockerCommitsTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.host = fx.make_repo(root / "host", {"README.md": "hello\n"})
        self.clone = root / "clone"  # the agent's private clone inside the sandbox
        fx.git(root, "clone", "-q", str(self.host), str(self.clone))
        fx.git(self.host, "remote", "add", "sandbox-t", str(self.clone))

    def tearDown(self):
        self._tmp.cleanup()

    def test_nothing_new(self):
        code, out, _ = run("t", "--repo", str(self.host))
        self.assertEqual(code, 0)
        self.assertIn("RESULT: nothing-new", out)

    def test_pull_creates_branch_and_leaves_working_tree_alone(self):
        tip = fx.commit_files(self.clone, {"new.txt": "from agent\n"}, "agent work")
        head = fx.git(self.host, "rev-parse", "HEAD")
        code, out, _ = run("t", "--repo", str(self.host))
        self.assertEqual(code, 0, out)
        self.assertIn("RESULT: pulled branch=agent/t/main commits=1 merged=false", out)
        self.assertEqual(fx.git(self.host, "rev-parse", "agent/t/main"), tip)
        self.assertEqual(fx.git(self.host, "rev-parse", "HEAD"), head)
        self.assertFalse((self.host / "new.txt").exists())

    def test_merge_fast_forwards_current_branch(self):
        fx.commit_files(self.clone, {"new.txt": "from agent\n"}, "agent work")
        code, out, _ = run("t", "--repo", str(self.host), "--merge")
        self.assertEqual(code, 0, out)
        self.assertTrue((self.host / "new.txt").exists())
        self.assertIn("merged=true", out)

    def test_merge_refuses_when_history_diverged(self):
        fx.commit_files(self.clone, {"a.txt": "agent\n"}, "agent work")
        fx.commit_files(self.host, {"b.txt": "host\n"}, "host work")
        code, _, err = run("t", "--repo", str(self.host), "--merge")
        self.assertEqual(code, 3)
        self.assertIn("fast-forward", err)
        self.assertFalse((self.host / "a.txt").exists())
        self.assertTrue(fx.git(self.host, "rev-parse", "--verify", "agent/t/main"))  # branch kept for a manual merge

    def test_several_candidate_branches_need_a_choice(self):
        fx.commit_files(self.clone, {"a.txt": "x\n"}, "on main")
        fx.git(self.clone, "switch", "-q", "-c", "feat")
        fx.commit_files(self.clone, {"b.txt": "y\n"}, "on feat")
        code, _, err = run("t", "--repo", str(self.host))
        self.assertEqual(code, 2)
        self.assertIn("--branch", err)
        code, out, _ = run("t", "--repo", str(self.host), "--branch", "feat")
        self.assertEqual(code, 0, out)
        self.assertIn("agent/t/feat", out)

    def test_missing_remote_is_an_error(self):
        code, _, err = run("unknown", "--repo", str(self.host))
        self.assertEqual(code, 1)
        self.assertIn("sandbox-unknown", err)

    def test_dry_run_creates_no_branch(self):
        fx.commit_files(self.clone, {"a.txt": "x\n"}, "agent work")
        code, out, _ = run("t", "--repo", str(self.host), "--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("RESULT: dry-run", out)
        self.assertEqual(fx.git(self.host, "branch", "--list", "agent/*"), "")

    def test_review_list_flags_files_that_run_later(self):
        fx.commit_files(self.clone, {".github/workflows/ci.yml": "on: push\n", "src/app.py": "x\n"}, "agent work")
        _, out, _ = run("t", "--repo", str(self.host))
        self.assertIn(".github/workflows/ci.yml", out.split("Review these")[1])
        self.assertNotIn("src/app.py", out.split("Review these")[1])

    @staticmethod
    def _install_hook(repo: Path) -> None:
        hook = repo / ".git" / "hooks" / "post-merge"
        hook.write_text("#!/bin/sh\ntouch hook-ran\n")
        hook.chmod(0o755)

    def test_merge_does_not_run_host_hooks(self):
        control = Path(self._tmp.name) / "control"  # a plain merge must fire the hook, or this test proves nothing
        fx.git(self.clone.parent, "clone", "-q", str(self.clone), str(control))
        self._install_hook(control)
        self._install_hook(self.host)
        fx.commit_files(self.clone, {"d.txt": "d\n"}, "agent work")
        fx.git(control, "pull", "-q", "--ff-only")
        if not (control / "hook-ran").exists():
            self.skipTest("this platform does not run post-merge hooks, so the check cannot discriminate")
        code, out, _ = run("t", "--repo", str(self.host), "--merge")
        self.assertEqual(code, 0, out)
        self.assertTrue((self.host / "d.txt").exists())
        self.assertFalse((self.host / "hook-ran").exists(), "post-merge hook ran during the pull")


if __name__ == "__main__":
    unittest.main()
