"""Shared git helpers for the sandbox pull scripts (standard library only).

Used by pull_docker_commits.py and pull_openshell_changes.py. Rules both scripts follow:
- Never touch the user's working tree unless asked (--merge, fast-forward only).
- Run git hooks off whenever incoming, untrusted content is checked out or applied:
  a committed hook script must not run on the host as a side effect of a pull.
- Report files that execute later on the host (CI, build, hook and sandbox-definition
  files) so the user reviews them first.
"""
from __future__ import annotations

import fnmatch
import os
import subprocess
from pathlib import Path, PurePosixPath

NO_HOOKS = ("-c", f"core.hooksPath={os.devnull}")

REVIEW_DIRS = {".git", ".github", ".gitlab", ".githooks", ".husky", ".vscode", ".idea", ".claude", "hooks", "sandbox"}
REVIEW_NAMES = {
    ".gitattributes", ".gitmodules", ".envrc", ".pre-commit-config.yaml", "makefile", "justfile",
    "package.json", "pyproject.toml", "setup.py", "setup.cfg", "noxfile.py", "tox.ini", "conftest.py",
    "docker-compose.yml", "sbxenv.yaml", "policy.yaml", "boundary.yaml", "claude.md", "agents.md",
}
REVIEW_GLOBS = ("*.sh", "*.ps1", "*.cmd", "*.bat", "dockerfile*", "*.dockerfile")


class Fail(Exception):
    """A user-facing error. `code` is the process exit code."""

    def __init__(self, message: str, code: int = 1):
        super().__init__(message)
        self.code = code


def git(repo: Path, *args: str, hooks: bool = True, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run `git -C repo args`. hooks=False disables all hooks for this call."""
    cmd = ["git", *(() if hooks else NO_HOOKS), "-C", str(repo), *args]
    done = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL)
    if check and done.returncode != 0:
        raise Fail(f"git {' '.join(args)} failed: {(done.stderr or done.stdout).strip()}")
    return done


def repo_root(path: str | Path) -> Path:
    done = subprocess.run(["git", "-C", str(path), "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    if done.returncode != 0:
        raise Fail(f"{path} is not inside a git repository")
    return Path(done.stdout.strip())


def current_branch(repo: Path) -> str:
    name = git(repo, "branch", "--show-current").stdout.strip()
    if not name:
        raise Fail("HEAD is detached; check out a branch first")
    return name


def require_clean(repo: Path) -> None:
    """Refuse to continue when tracked files have uncommitted changes."""
    if git(repo, "status", "--porcelain", "--untracked-files=no").stdout.strip():
        raise Fail("the working tree has uncommitted changes to tracked files; commit or stash them first")


def branch_sha(repo: Path, name: str) -> str | None:
    done = git(repo, "rev-parse", "--verify", "--quiet", f"refs/heads/{name}", check=False)
    return done.stdout.strip() or None


def identity_args(repo: Path) -> tuple[str, ...]:
    """Committer identity for `git am` / `git commit`: the repo's own, else a placeholder."""
    have = all(git(repo, "config", key, check=False).stdout.strip() for key in ("user.name", "user.email"))
    return () if have else ("-c", "user.name=sandbox-pull", "-c", "user.email=sandbox-pull@localhost.invalid")


def needs_review(path: str) -> bool:
    p = PurePosixPath(path)
    name = p.name.lower()
    return (
        any(part.lower() in REVIEW_DIRS for part in p.parts[:-1])
        or name in REVIEW_NAMES
        or any(fnmatch.fnmatch(name, pattern) for pattern in REVIEW_GLOBS)
    )


def show_new_work(repo: Path, base: str, tip: str) -> list[str]:
    """Print the commits and file stats in base..tip and return the paths that need a careful review."""
    print(git(repo, "log", "--oneline", "--stat", f"{base}..{tip}").stdout.rstrip())
    changed = git(repo, "-c", "core.quotepath=off", "diff", "--name-only", f"{base}...{tip}").stdout.splitlines()
    flagged = [p for p in changed if needs_review(p)]
    if flagged:
        print("\nReview these before running anything from the pulled work (they execute or configure things later):")
        for p in flagged:
            print(f"  {p}")
    return flagged


def fast_forward(repo: Path, branch: str) -> None:
    """Fast-forward the current branch to `branch` with hooks off. Fail(code=3) when it is not a fast-forward."""
    require_clean(repo)
    done = git(repo, "merge", "--ff-only", branch, hooks=False, check=False)
    if done.returncode != 0:
        raise Fail(f"cannot fast-forward {current_branch(repo)} to {branch}; merge or rebase {branch} by hand.\n{done.stderr.strip()}", code=3)
