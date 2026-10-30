#!/usr/bin/env python3
"""Pull the changes an agent made inside an OpenShell sandbox into a local git branch.

Usage:  python scripts/pull_openshell_changes.py SANDBOX [--repo PATH] [--workdir /sandbox/src]
            [--baseline baseline] [--mode auto|commits|diff] [--target-branch NAME]
            [--merge] [--dry-run] [--openshell "wsl -e openshell"]

OpenShell has no git integration: the sandbox holds an uploaded copy of the project. This script
packages the changes inside the sandbox, downloads them, and applies them on a NEW local branch
built in a temporary git worktree, so your working tree and current branch are never touched.

Prerequisite: the sandbox copy is a git repo with a commit named by --baseline (default `baseline`)
made before the agent started (see docs/guides/how-to/openshell-how-to.md, section 6), and your
repo is at the commit you uploaded.

Modes: `commits` = git format-patch baseline..HEAD, applied with git am (keeps the agent's commits);
`diff` = one patch of everything changed since baseline, committed once; `auto` = commits when the
agent committed everything, else diff.

Exit: 0 ok (or nothing new), 1 error, 3 patch does not apply or not a fast-forward.
The last line is machine-readable: `RESULT: ...`.
"""
from __future__ import annotations

import argparse
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Protocol

sys.path.insert(0, str(Path(__file__).resolve().parent))  # also works under `python -I`
import sandbox_git_common as sg  # noqa: E402


class Sandbox(Protocol):
    def exec(self, script: str) -> subprocess.CompletedProcess[str]: ...
    def download(self, remote: str, local_dir: Path) -> None: ...


class OpenShellSandbox:
    """A sandbox reached through the `openshell` CLI, directly or through `wsl -e` on Windows."""

    def __init__(self, name: str, workdir: str, command: list[str]):
        self.name, self.workdir, self.command = name, workdir, command

    @classmethod
    def detect(cls, name: str, workdir: str, override: str | None) -> "OpenShellSandbox":
        if override:
            return cls(name, workdir, shlex.split(override))
        if shutil.which("openshell"):
            return cls(name, workdir, ["openshell"])
        if shutil.which("wsl"):
            return cls(name, workdir, ["wsl", "-e", "openshell"])
        raise sg.Fail("`openshell` not found. Run this in the shell where openshell works (WSL2 on Windows) or pass --openshell.")

    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([*self.command, *args], capture_output=True, text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL)

    def exec(self, script: str) -> subprocess.CompletedProcess[str]:
        return self._run("sandbox", "exec", "-n", self.name, "--workdir", self.workdir, "--no-login-shell", "--no-tty", "--", "sh", "-c", script)

    def download(self, remote: str, local_dir: Path) -> None:
        target = str(local_dir)
        if self.command[:1] == ["wsl"]:  # openshell runs in WSL2 and needs the path as WSL sees it
            target = subprocess.run(["wsl", "-e", "wslpath", "-a", target], capture_output=True, text=True).stdout.strip()
        done = self._run("sandbox", "download", self.name, remote, target)
        if done.returncode != 0:
            raise sg.Fail(f"download of {remote} failed: {(done.stderr or done.stdout).strip()}")


def sandbox_state(box: Sandbox, baseline: str) -> tuple[int, bool]:
    """Return (commits ahead of baseline, uncommitted changes present). Scripts avoid quotes: they pass through wsl.exe."""
    if box.exec(f"git rev-parse --verify --quiet {baseline}").returncode != 0:
        raise sg.Fail(f"the sandbox repo has no commit named {baseline!r}. Make a baseline commit before the agent starts (how-to, section 6).")
    ahead = box.exec(f"git rev-list --count {baseline}..HEAD")
    dirty = box.exec("git status --porcelain")
    if ahead.returncode or dirty.returncode:
        raise sg.Fail(f"cannot read the sandbox repo state: {(ahead.stderr or dirty.stderr).strip()}")
    return int(ahead.stdout.strip() or 0), bool(dirty.stdout.strip())


def package(box: Sandbox, baseline: str, mode: str, pull_dir: str) -> None:
    prepare = f"rm -rf {pull_dir} && mkdir -p {pull_dir} && "
    script = prepare + (f"git format-patch --quiet -o {pull_dir} {baseline}..HEAD" if mode == "commits"
                        else f"git add -A && git diff --cached --binary {baseline} > {pull_dir}/changes.patch")
    done = box.exec(script)
    if done.returncode != 0:
        raise sg.Fail(f"could not package the changes in the sandbox: {(done.stderr or done.stdout).strip()}")


def apply_on_branch(repo: Path, patches: list[Path], mode: str, target: str, sandbox: str) -> None:
    """Build `target` from HEAD in a temporary worktree. On failure remove the branch and raise Fail(code=3)."""
    work = Path(tempfile.mkdtemp(prefix="sandbox-pull-"))
    ident = sg.identity_args(repo)
    sg.git(repo, "worktree", "add", "-q", "-b", target, str(work), "HEAD")
    try:
        if mode == "commits":
            done = sg.git(work, *ident, "am", "--quiet", *map(str, patches), hooks=False, check=False)
            if done.returncode != 0:
                sg.git(work, "am", "--abort", hooks=False, check=False)
        else:
            done = sg.git(work, "apply", "--index", "--whitespace=nowarn", str(patches[0]), hooks=False, check=False)
            if done.returncode == 0:
                done = sg.git(work, *ident, "commit", "-q", "-m", f"Agent changes pulled from OpenShell sandbox {sandbox}", hooks=False, check=False)
        if done.returncode != 0:
            raise sg.Fail(f"the patch does not apply to {repo} at HEAD: {(done.stderr or done.stdout).strip()}\nIs the repo at the commit you uploaded?", code=3)
    except sg.Fail:
        sg.git(repo, "worktree", "remove", "--force", str(work), check=False)
        sg.git(repo, "branch", "-D", target, check=False)
        raise
    sg.git(repo, "worktree", "remove", "--force", str(work))


def pull(args: argparse.Namespace, box: Sandbox) -> str:
    repo = sg.repo_root(args.repo)
    sg.require_clean(repo)
    ahead, dirty = sandbox_state(box, args.baseline)
    mode = args.mode if args.mode != "auto" else ("commits" if ahead and not dirty else "diff")
    if mode == "commits" and dirty:
        print("note: the sandbox has uncommitted changes that --mode commits leaves out; use --mode diff to include them.")
    if ahead == 0 and not dirty:
        return "RESULT: nothing-new"
    print(f"mode {mode}: {ahead} commit(s) ahead of {args.baseline}, uncommitted changes in sandbox: {dirty}")
    package(box, args.baseline, mode, args.pull_dir)
    local = Path(tempfile.mkdtemp(prefix="sandbox-pull-dl-"))
    try:
        box.download(args.pull_dir, local)
        patches = sorted(local.rglob("*.patch"))
        if not patches:
            raise sg.Fail("the download contained no .patch files")
        target = args.target_branch or f"agent/{args.sandbox}"
        if sg.branch_sha(repo, target):
            raise sg.Fail(f"local branch {target!r} already exists; delete it or pass --target-branch")
        apply_on_branch(repo, patches, mode, target, args.sandbox)
    finally:
        shutil.rmtree(local, ignore_errors=True)
        box.exec(f"rm -rf {args.pull_dir}")
    sg.show_new_work(repo, "HEAD", target)
    if args.dry_run:
        sg.git(repo, "branch", "-D", target)
        return f"RESULT: dry-run mode={mode} patches={len(patches)}"
    merged = False
    if args.merge:
        sg.fast_forward(repo, target)
        merged = True
    print(f"\nbranch {target} holds the agent's work." + (" Current branch fast-forwarded." if merged else f" Review it, then: git merge --ff-only {target}"))
    return f"RESULT: pulled branch={target} mode={mode} patches={len(patches)} merged={str(merged).lower()}"


def main(argv: list[str] | None = None, box: Sandbox | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("sandbox", help="sandbox name (as in `openshell sandbox list`)")
    parser.add_argument("--repo", default=".", help="host repository to apply to (default: current directory)")
    parser.add_argument("--workdir", default="/sandbox/src", help="git repo inside the sandbox (default: /sandbox/src)")
    parser.add_argument("--baseline", default="baseline", help="ref in the sandbox repo made before the agent started")
    parser.add_argument("--mode", choices=("auto", "commits", "diff"), default="auto")
    parser.add_argument("--pull-dir", default="/sandbox/.sandbox-pull", help="scratch dir in the sandbox; must be inside its working directory")
    parser.add_argument("--target-branch", help="local branch to create (default: agent/<sandbox>)")
    parser.add_argument("--merge", action="store_true", help="fast-forward the current branch to the new branch")
    parser.add_argument("--dry-run", action="store_true", help="build the branch to prove the patch applies, then delete it")
    parser.add_argument("--openshell", help='openshell command, e.g. "wsl -e openshell" (default: detected)')
    args = parser.parse_args(argv)
    try:
        print(pull(args, box or OpenShellSandbox.detect(args.sandbox, args.workdir, args.openshell)))
        return 0
    except sg.Fail as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exc.code


if __name__ == "__main__":
    sys.exit(main())
