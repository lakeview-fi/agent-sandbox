"""The throwaway git repo the sandbox is cloned from."""
import os
import shutil
import stat
import tempfile
from pathlib import Path

from .config import GIT_ID
from .process import run


def make_repo() -> Path:
    repo = Path(tempfile.mkdtemp(prefix="sbx-trial-")).resolve()
    run(["git", "init", "-q"], cwd=repo)
    (repo / "README.md").write_text("# throwaway repo for sbx smoke test\n")
    run(["git", "add", "README.md"], cwd=repo)
    run(["git", *GIT_ID, "commit", "-q", "-m", "init"], cwd=repo)
    return repo


def rmtree(path: Path) -> None:
    def _writable(func, p, _exc):
        os.chmod(p, stat.S_IWRITE)
        func(p)
    shutil.rmtree(path, onerror=_writable)
