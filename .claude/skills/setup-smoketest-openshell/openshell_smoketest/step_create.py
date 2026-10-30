"""Create the kept-alive sandbox (with the chosen provider) and detect the guest HTTP client."""
import os
import re
import signal
import subprocess
import tempfile
import time

from .config import CLIENTS
from .helpers import wait_until
from .model import FAIL, INFO, PASS, SKIP, Check, Ctx
from .process import osh, phases, gsh


def step_create(ctx: Ctx) -> list[Check]:
    a, n = ctx.args, ctx.name
    providers = osh("provider", "list")
    rows = [re.split(r"\s{2,}", ln.strip()) for ln in providers.stdout.splitlines()[1:] if ln.strip()]
    chosen = a.provider or (rows[0][0] if rows else "")
    types = {r[0]: r[1] for r in rows if len(r) > 1}
    ctx.provider, ctx.provider_type = chosen, types.get(chosen, "")
    cmd = ["sandbox", "create", "--name", n]
    if a.image != "default":
        cmd += ["--from", a.image]
    if chosen:
        cmd += ["--provider", chosen]
    cmd += ["--", "sleep", "infinity"]
    log = tempfile.TemporaryFile(mode="w+")
    proc = subprocess.Popen(["openshell", *cmd], stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
    secs = wait_until(lambda: phases().get(n) == "Ready" or proc.poll() is not None, timeout=a.create_timeout, step=3)
    ready = phases().get(n) == "Ready"
    if proc.poll() is None:  # `create ... -- sleep infinity` never returns; the sandbox outlives it
        os.killpg(proc.pid, signal.SIGTERM)
    time.sleep(3)
    log.seek(0)
    tail = log.read()[-400:]
    still = phases().get(n) == "Ready"
    if not (ready and still):
        return [Check("sandbox create (kept alive)", FAIL, f"phase {phases().get(n)!r}; create output: {tail}")]
    ctx.created = True
    out = [Check("sandbox create (kept alive)", PASS, f"Ready after {secs:.0f}s; survives the create process ending"),
           Check("provider attached", INFO if chosen else SKIP,
                 f"{chosen} ({ctx.provider_type})" if chosen else "no provider configured; inference will SKIP and must be reported"),
           Check("effective network policy (base)", INFO, osh("policy", "get", n, "--base").text),
           Check("effective network policy (full, incl. provider-added rules)", INFO, osh("policy", "get", n, "--full").text)]
    for c in CLIENTS:
        path = gsh(n, f"readlink -f \"$(command -v {c})\"").stdout.strip()
        if path.startswith("/") and not ctx.client:
            ctx.client, ctx.client_path = c, path
    out.append(Check("guest HTTP client", PASS if ctx.client else FAIL, f"{ctx.client} at {ctx.client_path}" if ctx.client else "none of node, curl, python3 in the image; network checks will SKIP"))
    return out
