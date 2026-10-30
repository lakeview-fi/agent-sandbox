"""Running host commands, `sbx` and commands inside the sandbox; sandbox and approval listings."""
import re
import subprocess
from pathlib import Path

from .model import Out


def run(cmd: list[str], timeout: int = 120, cwd: Path | None = None) -> Out:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=timeout, stdin=subprocess.DEVNULL, cwd=cwd)
    except subprocess.TimeoutExpired:
        return Out(124, "", f"timeout after {timeout}s: {' '.join(cmd)}")
    return Out(p.returncode, p.stdout, p.stderr)


def sbx(*args: str, timeout: int = 120) -> Out:
    return run(["sbx", *args], timeout)


def guest(name: str, script: str, timeout: int = 60) -> Out:
    """Run a shell snippet inside the sandbox (Linux guest) in its default workdir."""
    return sbx("exec", name, "sh", "-c", script, timeout=timeout)


def git(repo: Path, *args: str) -> Out:
    return run(["git", "-C", str(repo), *args])


def fetch(name: str, host: str) -> Out:
    return guest(name, f"curl -s -m 15 https://{host}")


def pending_titles(name: str) -> list[str]:
    titles = []
    for line in sbx("policy", "approval", "ls").text.splitlines():
        fields = re.split(r"\s{2,}", line.strip())
        if len(fields) >= 3 and fields[1] == name:
            titles.append(fields[2])
    return titles


def sandbox_names() -> set[str]:
    lines = sbx("ls").stdout.splitlines()[1:]
    return {ln.split()[0] for ln in lines if ln.strip()}
