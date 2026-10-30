"""Teardown: stop and remove only the sandbox this run created, then verify nothing else changed."""
from pathlib import Path

from .model import FAIL, INFO, PASS, Check
from .process import pending_titles, sandbox_names, sbx
from .repo import rmtree


def teardown(name: str, repo: Path | None, base: dict) -> list[Check]:
    checks = []
    if name not in sandbox_names():
        checks.append(Check("teardown: sandbox existed", INFO, "never created"))
    else:
        sbx("stop", name)
        rm = sbx("rm", "--force", name, timeout=180)
        checks.append(Check("teardown: sbx rm --force", PASS if rm.code == 0 else FAIL, "removed" if rm.code == 0 else rm.text[-200:]))
    left = sandbox_names()
    checks.append(Check("teardown: sandbox gone", PASS if name not in left else FAIL, name))
    vanished = sorted(base["sandboxes"] - left)  # only a sandbox that existed before this run and is gone is a finding
    appeared = sorted(left - base["sandboxes"])  # created by someone else while this run was going (concurrent sessions)
    checks.append(Check("teardown: other sandboxes untouched", FAIL if vanished else PASS,
                        f"vanished since the start: {vanished}" if vanished else "all sandboxes that existed before are still there"))
    if appeared:
        checks.append(Check("teardown: sandboxes created by others during this run (not touched)", INFO, ", ".join(appeared)))
    checks.append(Check("teardown: no policy left for sandbox", PASS if f"sandbox:{name}" not in sbx("policy", "ls").text else FAIL, ""))
    checks.append(Check("teardown: no pending approvals for sandbox", PASS if not pending_titles(name) else FAIL, ""))
    if repo and repo.exists():
        rmtree(repo)
    return checks
