"""Checks 1-2: deny-all blocks, live allow and removal of a network rule."""
from .helpers import is_blocked, wait_until
from .model import FAIL, PASS, Check, Ctx
from .process import fetch, sbx


def step_network(ctx: Ctx) -> list[Check]:
    a, n = ctx.args, ctx.name
    out = []
    t1 = fetch(n, a.allow_host)
    out.append(Check(f"1 {a.allow_host} blocked under deny-all", PASS if is_blocked(t1.text) else FAIL, t1.text[:300]))
    allow = sbx("policy", "allow", "network", "--sandbox", n, a.allow_host)
    secs = wait_until(lambda: "Example Domain" in fetch(n, a.allow_host).text, timeout=10)
    out.append(Check(f"2a {a.allow_host} reachable after allow (live, no restart)", PASS if allow.code == 0 and secs is not None else FAIL,
                     f"allow exit {allow.code}; reachable after {secs:.1f}s" if secs is not None else f"allow exit {allow.code}; still blocked after 10s: {allow.text[:200]}"))
    t2b = fetch(n, a.other_host)
    out.append(Check(f"2b {a.other_host} still blocked", PASS if is_blocked(t2b.text) else FAIL, t2b.text[:300]))
    rm = sbx("policy", "rm", "network", "--sandbox", n, "--resource", a.allow_host, "--force")  # --force: no terminal to confirm
    secs = wait_until(lambda: is_blocked(fetch(n, a.allow_host).text), timeout=10)
    out.append(Check(f"2c {a.allow_host} blocked again after rule removal (live)", PASS if rm.code == 0 and secs is not None else FAIL,
                     f"rm exit {rm.code}; blocked after {secs:.1f}s" if secs is not None else f"rm exit {rm.code}; still reachable after 10s: {rm.text[:200]}"))
    return out
