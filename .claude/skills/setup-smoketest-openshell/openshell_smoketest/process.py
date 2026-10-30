"""Running host commands, `openshell`, commands inside the sandbox; sandbox phases."""
import re
import subprocess

from .model import Out


def run(cmd: list[str], timeout: int = 120) -> Out:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=timeout, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return Out(124, "", f"timeout after {timeout}s: {' '.join(cmd)}")
    return Out(p.returncode, p.stdout, p.stderr)


def osh(*args: str, timeout: int = 120) -> Out:
    return run(["openshell", *args], timeout)


def gx(name: str, *cmd: str, timeout: int = 60) -> Out:
    """Run a command inside the sandbox."""
    return osh("sandbox", "exec", name, "--timeout", str(timeout), "--no-tty", "--", *cmd, timeout=timeout + 30)


def gsh(name: str, script: str, timeout: int = 60) -> Out:
    return gx(name, "sh", "-c", script, timeout=timeout)


def phases() -> dict[str, str]:
    """Sandbox name -> phase. Rows look like: NAME  2026-10-29 06:03:32  Ready."""
    out = {}
    for line in osh("sandbox", "list").stdout.splitlines()[1:]:
        parts = re.split(r"\s{2,}", line.strip())
        if len(parts) >= 3:
            out[parts[0]] = parts[-1]
    return out
