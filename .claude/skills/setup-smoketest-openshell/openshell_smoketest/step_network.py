"""Checks 1-2: default-deny egress, live binary-scoped allow and removal of a network rule."""
from .config import CLIENTS
from .helpers import allowed, wait_until
from .model import FAIL, PASS, SKIP, Check, Ctx
from .process import gsh, gx, osh


def fetch(ctx: Ctx, host: str, client: str | None = None) -> str:
    return gx(ctx.name, *CLIENTS[client or ctx.client](host), timeout=40).text


def step_network(ctx: Ctx) -> list[Check]:
    a, n = ctx.args, ctx.name
    if not ctx.client:
        return [Check("1-2 network checks", SKIP, "no HTTP client in the sandbox; report this to the user")]
    out = []
    t1 = fetch(ctx, a.allow_host)
    out.append(Check(f"1 {a.allow_host} blocked by default", PASS if not allowed(t1) else FAIL, t1[:300]))
    ep = f"{a.allow_host}:443"
    dry = osh("policy", "update", n, "--add-endpoint", ep, "--binary", ctx.client_path, "--dry-run")
    out.append(Check("2-dry dry-run previews the rule without applying", PASS if dry.code == 0 and not allowed(fetch(ctx, a.allow_host)) else FAIL, dry.text[:200]))
    upd = osh("policy", "update", n, "--add-endpoint", ep, "--binary", ctx.client_path, "--wait")
    secs = wait_until(lambda: allowed(fetch(ctx, a.allow_host)), timeout=15)
    out.append(Check(f"2a {a.allow_host} reachable after update (live, no restart)", PASS if upd.code == 0 and secs is not None else FAIL,
                     f"update exit {upd.code}; reachable after {secs:.1f}s" if secs is not None else f"update exit {upd.code}; still blocked after 15s: {upd.text[:200]}"))
    t2b = fetch(ctx, a.other_host)
    out.append(Check(f"2b {a.other_host} still blocked", PASS if not allowed(t2b) else FAIL, t2b[:300]))
    others = [c for c in CLIENTS if c != ctx.client and gsh(n, f"command -v {c}").code == 0]
    if others:
        t2c = fetch(ctx, a.allow_host, others[0])
        out.append(Check(f"2c rule is binary-scoped: {others[0]} still blocked for {a.allow_host}", PASS if not allowed(t2c) else FAIL, t2c[:300]))
    else:
        out.append(Check("2c rule is binary-scoped", SKIP, "no second HTTP client in the image"))
    rm = osh("policy", "update", n, "--remove-endpoint", ep, "--wait")
    secs = wait_until(lambda: not allowed(fetch(ctx, a.allow_host)), timeout=15)
    out.append(Check(f"2d {a.allow_host} blocked again after rule removal (live)", PASS if rm.code == 0 and secs is not None else FAIL,
                     f"remove exit {rm.code}; blocked after {secs:.1f}s" if secs is not None else f"remove exit {rm.code}; still reachable after 15s: {rm.text[:200]}"))
    return out
