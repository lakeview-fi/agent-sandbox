"""Checks 10/10b/10c/10d: scripts/pull_openshell_changes.py brings a sandbox commit into a temp branch of a throwaway repo."""
import sys
import tempfile
from pathlib import Path

from .config import GIT_ID, PULL_SCRIPT
from .model import FAIL, PASS, SKIP, Check, Ctx
from .process import gsh, osh, run


def step_pull_script(ctx: Ctx) -> list[Check]:
    """Checks 10: scripts/pull_openshell_changes.py brings a sandbox commit into a temp branch of a throwaway repo."""
    n = ctx.name
    if not PULL_SCRIPT.exists():
        return [Check("10 pull script", SKIP, f"{PULL_SCRIPT} not found")]
    if gsh(n, "command -v git").code != 0:
        return [Check("10 pull script", SKIP, "no git in the sandbox image: the pull workflow needs it. Report this to the user.")]
    work = Path(tempfile.mkdtemp(prefix="osh-pull-"))
    ctx.tmp_dirs.append(work)
    files = {"README.md": "# pull script trial\n", "app.txt": "one\n"}
    upload_dir, host = work / "upload", work / "host"
    for d in (upload_dir, host):
        d.mkdir()
        for name, text in files.items():
            (d / name).write_text(text)
    h = lambda *a: run(["git", "-C", str(host), *a])  # noqa: E731
    h("init", "-q")
    h("add", "-A")
    h(*GIT_ID.split(), "commit", "-q", "-m", "init")
    start = h("branch", "--show-current").stdout.strip()
    head = h("rev-parse", "HEAD").stdout.strip()
    up = osh("sandbox", "upload", n, str(upload_dir), "/sandbox/")
    wd = f"/sandbox/{upload_dir.name}"
    prep = gsh(n, f"cd {wd} && git init -q && git add -A && git {GIT_ID} commit -qm baseline && git tag baseline "
                  f"&& echo agent > from-agent.txt && git add -A && git {GIT_ID} commit -qm agent-commit")
    if up.code != 0 or prep.code != 0:
        return [Check("10 pull script", FAIL, f"setup failed: upload exit {up.code}; sandbox git exit {prep.code}: {prep.text[-200:]}")]
    base_cmd = [sys.executable, "-I", str(PULL_SCRIPT), n, "--repo", str(host), "--workdir", wd]
    h("switch", "-q", "-c", "trial/pull-test")
    try:
        first = run([*base_cmd, "--merge"], timeout=180)
        got = (host / "from-agent.txt").exists() and "mode=commits" in first.stdout and "merged=true" in first.stdout
        gsh(n, f"cd {wd} && echo more > uncommitted.txt")
        h("reset", "-q", "--hard", head)  # temp branch only: back to the uploaded commit, so the diff applies again
        h("branch", "-D", f"agent/{n}")  # the script refuses to reuse the branch the first run created
        dry = run([*base_cmd, "--mode", "diff", "--dry-run"], timeout=180)
        cleaned = gsh(n, "test ! -e /sandbox/.sandbox-pull").code == 0
        out = [Check("10 pull script: sandbox commit fast-forwards a temp branch", PASS if first.code == 0 and got else FAIL, f"exit {first.code}; {first.text[-300:]}"),
               Check("10b pull script: diff mode dry run applies cleanly and leaves no branch", PASS if dry.code == 0 and "dry-run" in dry.stdout and not h("branch", "--list", "agent/*").stdout.strip() else FAIL,
                     f"exit {dry.code}; {dry.text[-300:]}"),
               Check("10c pull script: scratch dir removed from the sandbox", PASS if cleaned else FAIL, "/sandbox/.sandbox-pull")]
    finally:
        h("switch", "-q", start)
        h("branch", "-D", "trial/pull-test")
        for ref in h("for-each-ref", "--format=%(refname:short)", "refs/heads/agent/").stdout.split():
            h("branch", "-D", ref)
    out.append(Check("10d pull script: starting branch unchanged after the temp branch is removed", PASS if h("rev-parse", "HEAD").stdout.strip() == head else FAIL, f"branch {start}"))
    return out
