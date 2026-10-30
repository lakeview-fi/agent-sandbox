"""Checks 3-4: upload lands at /sandbox/<dir>, sandbox files do not reach the host, download is the handoff."""
import shlex
import tempfile
from pathlib import Path

from .model import FAIL, PASS, Check, Ctx
from .process import gsh, gx, osh


def step_upload(ctx: Ctx) -> list[Check]:
    n, proj = ctx.name, ctx.proj
    up = osh("sandbox", "upload", n, str(proj), "/sandbox/")
    listing = gx(n, "find", "/sandbox", "-maxdepth", "3", "-type", "f").text
    good = f"/sandbox/{proj.name}/README.md" in listing and f"/sandbox/{proj.name}/{proj.name}" not in listing
    out = [Check("4 upload to /sandbox/ lands at /sandbox/<dir> (not doubled)", PASS if up.code == 0 and good else FAIL, f"upload exit {up.code}; {listing[:300]}")]
    gsh(n, f"echo hello > /sandbox/{shlex.quote(proj.name)}/from-sandbox.txt")
    leaked = (proj / "from-sandbox.txt").exists()
    out.append(Check("3a file made in the sandbox is not in the host project", PASS if not leaked else FAIL, "upload is a copy; host dir unchanged" if not leaked else "host dir changed"))
    dest = Path(tempfile.mkdtemp(prefix="osh-dl-"))
    ctx.tmp_dirs.append(dest)
    dl = osh("sandbox", "download", n, f"/sandbox/{proj.name}/from-sandbox.txt", str(dest))
    got = [p for p in dest.rglob("from-sandbox.txt")]
    ok = dl.code == 0 and got and got[0].read_text().strip() == "hello"
    out.append(Check("3b deliberate handoff: download returns the file", PASS if ok else FAIL, f"download exit {dl.code}; found {[str(g.relative_to(dest)) for g in got]}"))
    return out
