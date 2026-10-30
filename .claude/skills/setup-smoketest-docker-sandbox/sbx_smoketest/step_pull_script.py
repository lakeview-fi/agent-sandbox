"""Check 9/9b/9c: scripts/pull_docker_commits.py brings the guest commit into a temp branch."""
import sys

from .config import PULL_SCRIPT
from .model import FAIL, PASS, SKIP, Check, Ctx
from .process import git, run


def step_pull_script(ctx: Ctx) -> list[Check]:
    """Check 9: scripts/pull_docker_commits.py brings the guest commit from check 3 into a temp branch.

    Runs on a temporary branch of the throwaway repo, so the starting branch must end up unchanged.
    """
    repo, n, temp = ctx.repo, ctx.name, "trial/pull-test"
    start = git(repo, "branch", "--show-current").stdout.strip()
    if not PULL_SCRIPT.exists():
        return [Check("9 pull script", SKIP, f"{PULL_SCRIPT} not found")]
    switched = git(repo, "switch", "-q", "-c", temp)
    if switched.code != 0:
        return [Check("9 pull script", FAIL, f"could not create temp branch: {switched.text}")]
    try:
        cmd = [sys.executable, "-I", str(PULL_SCRIPT), n, "--repo", str(repo), "--merge"]
        first = run(cmd, timeout=120)
        pulled = (repo / "from-sandbox.txt").exists() and "merged=true" in first.stdout
        again = run(cmd, timeout=120)
        out = [Check("9 pull script: guest commit fast-forwards a temp branch", PASS if first.code == 0 and pulled else FAIL,
                     f"exit {first.code}; {first.text[-300:]}"),
               Check("9b pull script: second run finds nothing new", PASS if again.code == 0 and "nothing-new" in again.stdout else FAIL,
                     f"exit {again.code}; {again.text[-200:]}")]
    finally:
        git(repo, "switch", "-q", start)
        git(repo, "branch", "-D", temp)
        for ref in git(repo, "for-each-ref", "--format=%(refname:short)", "refs/heads/agent/").stdout.split():
            git(repo, "branch", "-D", ref)
    unchanged = git(repo, "rev-parse", "HEAD").stdout.strip() == ctx.head_before
    out.append(Check("9c pull script: starting branch unchanged after the temp branch is removed", PASS if unchanged else FAIL, f"branch {start}"))
    return out
