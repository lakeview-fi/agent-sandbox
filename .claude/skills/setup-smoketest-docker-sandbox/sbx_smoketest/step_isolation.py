"""Checks 3-4: clone commits stay out of the host tree; host home and source mount are not exposed."""
import shlex
from pathlib import Path

from .config import GIT_ID
from .helpers import guest_path
from .model import FAIL, PASS, SKIP, Check, Ctx
from .process import git, guest


def step_clone_isolation(ctx: Ctx) -> list[Check]:
    n, repo = ctx.name, ctx.repo
    commit = guest(n, f"cd {shlex.quote(ctx.gws)} && echo hello > from-sandbox.txt && git {' '.join(GIT_ID)} add from-sandbox.txt "
                      f"&& git {' '.join(GIT_ID)} commit -qm from-sandbox && git rev-parse HEAD")
    new_remotes = set(git(repo, "remote").stdout.split()) - ctx.remotes_before
    leaked = (repo / "from-sandbox.txt").exists() or git(repo, "rev-parse", "HEAD").stdout.strip() != ctx.head_before
    ok = commit.code == 0 and not leaked and new_remotes <= {f"sandbox-{n}"}
    return [Check("3 clone commit not in host tree", PASS if ok else FAIL,
                  f"guest commit exit {commit.code}; host file/HEAD changed: {leaked}; new host remotes: {sorted(new_remotes)}")]


def step_host_visibility(ctx: Ctx) -> list[Check]:
    n, repo = ctx.name, ctx.repo
    home = Path.home().resolve()
    ghome = guest_path(home)
    try:
        allowed = {repo.relative_to(home).parts[0]}
    except ValueError:
        allowed = set()
    listing = guest(n, f"ls -A {shlex.quote(ghome)} 2>&1")
    entries = set(listing.stdout.split()) if listing.code == 0 else set()
    extra = entries - allowed
    out = [Check("4a host home contents not visible", PASS if not extra else FAIL,
                 f"guest {ghome}: {sorted(entries) or 'absent'}; unexpected: {sorted(extra)}")]
    if guest(n, "test -d /run/sandbox/source").code == 0:
        touch = guest(n, "touch /run/sandbox/source/probe 2>&1")
        out.append(Check("4b host source mount not writable", PASS if touch.code != 0 and not (repo / "probe").exists() else FAIL, touch.text[:200]))
    else:
        out.append(Check("4b host source mount not writable", SKIP, "/run/sandbox/source not present"))
    return out
