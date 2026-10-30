"""Small pure helpers: path mapping, blocked-response detection, polling, host label."""
import os
import sys
import time
from pathlib import Path


def guest_path(p: Path) -> str:
    """Host path -> path as mirrored inside the guest (observed on Windows: C:\\a\\b -> /c/a/b)."""
    s = str(p)
    if os.name == "nt":
        drive, rest = os.path.splitdrive(s)
        return "/" + drive[0].lower() + rest.replace("\\", "/")
    return s


def is_blocked(text: str) -> bool:
    return ("Approval required" in text or "403" in text) and "Example Domain" not in text


def wait_until(pred, timeout: float = 10.0, step: float = 1.0) -> float | None:
    """Seconds until pred() is true, or None on timeout. Measures how fast a policy change applies."""
    start = time.monotonic()
    while True:
        if pred():
            return time.monotonic() - start
        if time.monotonic() - start >= timeout:
            return None
        time.sleep(step)


def host_label() -> str:
    if sys.platform == "darwin":
        return "macos"
    return "windows" if os.name == "nt" else "linux"
