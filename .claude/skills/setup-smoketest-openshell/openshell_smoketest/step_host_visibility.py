"""Checks 5a-5d: host mounts and home not visible in the guest; filesystem policy enforced."""
import shlex
from pathlib import Path

from .model import FAIL, PASS, Check, Ctx
from .process import gsh


def step_host_visibility(ctx: Ctx) -> list[Check]:
    n = ctx.name
    home = Path.home()
    mnt = gsh(n, "ls /mnt/c 2>&1; ls /mnt 2>&1")
    out = [Check("5a host drive mounts (/mnt/c) not visible", PASS if "Users" not in mnt.text and "Windows" not in mnt.text else FAIL, mnt.text[:200] or "absent")]
    listing = gsh(n, f"ls -A {shlex.quote(str(home))} 2>&1")
    host_names = {p.name for p in home.iterdir() if not p.name.startswith(".")} if home.exists() else set()
    overlap = host_names & set(listing.stdout.split()) if listing.code == 0 else set()
    sensitive = gsh(n, f"for d in .ssh .aws .gnupg .claude; do [ -e {shlex.quote(str(home))}/$d ] && echo $d; done; true").stdout.split()
    out.append(Check("5b host home contents not visible", PASS if not overlap and not sensitive else FAIL,
                     f"guest {home}: exit {listing.code}; overlap with host: {sorted(overlap)}; sensitive dirs: {sensitive}"))
    ro = gsh(n, "touch /usr/probe 2>&1")
    rw = gsh(n, "touch /tmp/probe 2>&1 && echo writable")
    out.append(Check("5c read-only paths (/usr) not writable (filesystem policy enforced)", PASS if ro.code != 0 else FAIL,
                     ro.text[:200] or "write to /usr succeeded: Landlock best_effort may not have been enforced; report"))
    out.append(Check("5d /tmp writable (sanity)", PASS if "writable" in rw.text else FAIL, rw.text[:200]))
    return out
