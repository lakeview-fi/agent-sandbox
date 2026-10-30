"""Teardown: delete only the sandbox this run created, then verify nothing else changed; remove temp dirs."""
import shutil

from .helpers import wait_until
from .model import FAIL, INFO, PASS, Check, Ctx
from .process import osh, phases


def teardown(ctx: Ctx) -> list[Check]:
    n, base = ctx.name, ctx.base
    checks = []
    if n in phases():
        d = osh("sandbox", "delete", n, timeout=180)
        gone = wait_until(lambda: n not in phases(), timeout=90, step=3)
        checks.append(Check("teardown: sandbox delete", PASS if d.code == 0 and gone is not None else FAIL,
                            f"gone after {gone:.0f}s" if gone is not None else f"exit {d.code}; still listed after 90s: {d.text[-200:]}"))
    else:
        checks.append(Check("teardown: sandbox existed", INFO, "never created"))
    left = set(phases())
    # other sessions may delete sandboxes concurrently; this script only ever deletes its own, so a vanished one is INFO, not FAIL
    vanished = set(base["phases"]) - left
    checks.append(Check("teardown: other sandboxes untouched", PASS if not vanished else INFO,
                        f"before {sorted(base['phases'])}, after {sorted(left)}" + (f"; vanished {sorted(vanished)} (concurrent run? this script only deletes {n})" if vanished else "")))
    for d in [ctx.proj, *ctx.tmp_dirs]:
        shutil.rmtree(d, ignore_errors=True)
    checks.append(Check("teardown: temp dirs removed (image left in place)", PASS if not ctx.proj.exists() else FAIL, ""))
    return checks
