"""Throwaway git repositories for the pull-script tests (standard library only).

pytest would put these in conftest.py; the tests use unittest so they run with no extra install.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

IDENTITY = {
    "GIT_AUTHOR_NAME": "Test Author", "GIT_AUTHOR_EMAIL": "author@example.invalid",
    "GIT_COMMITTER_NAME": "Test Committer", "GIT_COMMITTER_EMAIL": "committer@example.invalid",
}


def git(cwd: Path, *args: str) -> str:
    done = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, env={**os.environ, **IDENTITY})
    assert done.returncode == 0, f"git {' '.join(args)}: {done.stderr}"
    return done.stdout.strip()


def make_repo(path: Path, files: dict[str, str]) -> Path:
    """Create a repo on branch `main` with one commit holding `files`."""
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init", "-q", "-b", "main")
    git(path, "config", "core.autocrlf", "false")
    commit_files(path, files, "init")
    return path


def commit_files(repo: Path, files: dict[str, str], message: str) -> str:
    for name, text in files.items():
        target = repo / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(text.encode())
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)
    return git(repo, "rev-parse", "HEAD")
