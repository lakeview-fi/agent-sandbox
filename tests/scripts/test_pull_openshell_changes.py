"""pull_openshell_changes.py against a local directory standing in for the sandbox."""
import contextlib
import io
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.scripts import gitfixtures as fx

import pull_openshell_changes as poc  # noqa: E402  (scripts/ is put on sys.path by gitfixtures)

HAVE_SH = shutil.which("sh") is not None


class LocalSandbox:
    """Runs the script's sandbox commands in a local directory; `/sandbox` maps to `root`."""

    def __init__(self, root: Path):
        self.root = root

    def _map(self, text: str) -> str:
        return text.replace("/sandbox", self.root.as_posix())

    def exec(self, script: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["sh", "-c", self._map(script)], cwd=self.root / "src", capture_output=True, text=True, env={**fx.os.environ, **fx.IDENTITY})

    def download(self, remote: str, local_dir: Path) -> None:
        src = Path(self._map(remote))
        shutil.copytree(src, local_dir / src.name)


def run(box, *argv: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = poc.main(list(argv), box=box)
    return code, out.getvalue(), err.getvalue()


@unittest.skipUnless(HAVE_SH, "needs a POSIX sh")
class PullOpenShellChangesTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.host = fx.make_repo(root / "host", {"app.txt": "line one\n", "keep.txt": "keep\n"})
        self.root = root / "sandbox"
        shutil.copytree(self.host, self.root / "src", ignore=shutil.ignore_patterns(".git"))  # the upload: files, no .git
        self.src = self.root / "src"
        fx.git(self.src, "init", "-q", "-b", "main")
        fx.git(self.src, "add", "-A")
        fx.git(self.src, "commit", "-q", "-m", "baseline")
        fx.git(self.src, "tag", "baseline")
        self.box = LocalSandbox(self.root)

    def tearDown(self):
        self._tmp.cleanup()

    def pull(self, *extra: str):
        return run(self.box, "t", "--repo", str(self.host), *extra)

    def test_nothing_new(self):
        code, out, _ = self.pull()
        self.assertEqual(code, 0)
        self.assertIn("RESULT: nothing-new", out)

    def test_commits_mode_keeps_agent_commits(self):
        fx.commit_files(self.src, {"new.txt": "agent\n"}, "agent commit one")
        fx.commit_files(self.src, {"app.txt": "line one\nline two\n"}, "agent commit two")
        head = fx.git(self.host, "rev-parse", "HEAD")
        code, out, err = self.pull()
        self.assertEqual(code, 0, out + err)
        self.assertIn("mode=commits", out)
        self.assertEqual(fx.git(self.host, "log", "--format=%s", "main..agent/t"), "agent commit two\nagent commit one")
        self.assertEqual(fx.git(self.host, "show", "agent/t:app.txt"), "line one\nline two")
        self.assertEqual(fx.git(self.host, "rev-parse", "HEAD"), head)
        self.assertFalse((self.host / "new.txt").exists(), "working tree must stay untouched")
        self.assertEqual(len(fx.git(self.host, "worktree", "list").splitlines()), 1, "temporary worktree left behind")

    def test_diff_mode_collects_uncommitted_and_new_files_in_one_commit(self):
        (self.src / "app.txt").write_text("line one\nedited\n")
        (self.src / "fresh.txt").write_text("untracked\n")
        code, out, err = self.pull()
        self.assertEqual(code, 0, out + err)
        self.assertIn("mode=diff", out)
        self.assertEqual(fx.git(self.host, "rev-list", "--count", "main..agent/t"), "1")
        self.assertEqual(fx.git(self.host, "show", "agent/t:fresh.txt"), "untracked")
        self.assertEqual(fx.git(self.host, "show", "agent/t:app.txt"), "line one\nedited")

    def test_diff_mode_carries_binary_files(self):
        data = bytes(range(256))
        (self.src / "blob.bin").write_bytes(data)
        code, out, err = self.pull("--mode", "diff")
        self.assertEqual(code, 0, out + err)
        shown = subprocess.run(["git", "-C", str(self.host), "show", "agent/t:blob.bin"], capture_output=True).stdout
        self.assertEqual(shown, data)

    def test_conflicting_host_change_removes_branch_and_worktree(self):
        (self.src / "app.txt").write_text("line one\nagent edit\n")
        fx.commit_files(self.host, {"app.txt": "line one\nhost edit\n"}, "host moved on")
        code, _, err = self.pull("--mode", "diff")
        self.assertEqual(code, 3, err)
        self.assertEqual(fx.git(self.host, "branch", "--list", "agent/*"), "")
        self.assertEqual(len(fx.git(self.host, "worktree", "list").splitlines()), 1)

    def test_missing_baseline_is_an_error(self):
        fx.git(self.src, "tag", "-d", "baseline")
        code, _, err = self.pull()
        self.assertEqual(code, 1)
        self.assertIn("baseline", err)

    def test_dry_run_leaves_no_branch(self):
        (self.src / "x.txt").write_text("x\n")
        code, out, _ = self.pull("--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("RESULT: dry-run", out)
        self.assertEqual(fx.git(self.host, "branch", "--list", "agent/*"), "")

    def test_refuses_dirty_host_tree(self):
        (self.host / "app.txt").write_text("local edit\n")
        (self.src / "x.txt").write_text("x\n")
        code, _, err = self.pull()
        self.assertEqual(code, 1)
        self.assertIn("uncommitted", err)

    def test_merge_fast_forwards_current_branch(self):
        (self.src / "x.txt").write_text("x\n")
        code, out, err = self.pull("--merge")
        self.assertEqual(code, 0, out + err)
        self.assertTrue((self.host / "x.txt").exists())

    def test_scratch_dir_is_removed_from_the_sandbox(self):
        (self.src / "x.txt").write_text("x\n")
        self.pull()
        self.assertFalse((self.root / ".sandbox-pull").exists())


if __name__ == "__main__":
    unittest.main()
