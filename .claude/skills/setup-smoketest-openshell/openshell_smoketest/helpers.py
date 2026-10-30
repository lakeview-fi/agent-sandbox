"""Small pure helpers: polling, allowed-response detection, short hash, host label."""
import hashlib
import re
import sys
import time
from pathlib import Path


def wait_until(pred, timeout: float = 10.0, step: float = 1.0) -> float | None:
    """Seconds until pred() is true, or None on timeout. Measures how fast a change applies."""
    start = time.monotonic()
    while True:
        if pred():
            return time.monotonic() - start
        if time.monotonic() - start >= timeout:
            return None
        time.sleep(step)


def allowed(text: str) -> bool:
    return re.search(r"HTTP [23]\d\d", text) is not None


def sha12(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:12]


def host_label() -> str:
    if sys.platform == "darwin":
        return "macos"
    try:
        if "microsoft" in Path("/proc/version").read_text().lower():
            return "windows-wsl2"
    except OSError:
        pass
    return "linux"
