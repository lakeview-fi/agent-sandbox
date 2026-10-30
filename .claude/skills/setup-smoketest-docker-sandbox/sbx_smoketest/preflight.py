"""Preflight: sbx and git usable, deny-all policy present, name free. Returns checks, baseline, whether to continue."""
import shutil

from .model import FAIL, INFO, PASS, Check
from .process import sandbox_names, sbx


def preflight(name: str) -> tuple[list[Check], dict, bool]:
    """Returns checks, baseline, and whether it is possible to continue."""
    checks, base = [], {}
    if not shutil.which("sbx") or not shutil.which("git"):
        return [Check("sbx and git on PATH", FAIL, "install sbx (see the platform file) and git")], base, False
    version = sbx("version")
    base["version"] = version.text.splitlines()[0] if version.text else "unknown"
    checks.append(Check("sbx version", PASS if version.code == 0 else FAIL, base["version"]))
    ls, pol = sbx("ls"), sbx("policy", "ls")
    base["sandboxes"] = sandbox_names()
    usable = ls.code == 0 and pol.code == 0
    checks.append(Check("sbx usable (signed in, daemon up)", PASS if usable else FAIL,
                        f"{len(base['sandboxes'])} existing sandboxes left alone" if usable else f"{ls.text}\n{pol.text}"))
    has_deny = "default-deny-all" in pol.text
    checks.append(Check("deny-all policy present", PASS if has_deny else FAIL,
                        "default-deny-all listed" if has_deny else "missing: ask the user to run sbx policy init deny-all; later checks will show the effect"))
    free = name not in base["sandboxes"]
    checks.append(Check("sandbox name free", PASS if free else FAIL, name))
    diag = sbx("diagnose", "--format", "json", timeout=180)
    checks.append(Check("sbx diagnose", INFO, f"exit {diag.code}; {len(diag.text)} chars of report (read it if anything fails)"))
    return checks, base, usable and free
