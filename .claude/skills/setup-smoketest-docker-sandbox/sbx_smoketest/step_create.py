"""Create the clone-mode sandbox and record the baseline the later checks compare against."""
from .helpers import guest_path
from .model import FAIL, INFO, PASS, Check, Ctx
from .process import git, guest, pending_titles, sbx


def step_create(ctx: Ctx) -> list[Check]:
    create = sbx("create", "--clone", "--name", ctx.name, ctx.args.kit or ctx.args.agent, str(ctx.repo), timeout=600)
    if create.code != 0:
        return [Check("sbx create --clone", FAIL, create.text)]
    ctx.created = True
    ctx.remotes_before = set(git(ctx.repo, "remote").stdout.split())
    ctx.head_before = git(ctx.repo, "rev-parse", "HEAD").stdout.strip()
    ctx.approvals_before = set(pending_titles(ctx.name))
    pwd = guest(ctx.name, "pwd").stdout.strip()
    ctx.gws = pwd or guest_path(ctx.repo)
    return [
        Check("sbx create --clone", PASS, "created"),
        Check("workspace mounted read-only", PASS if "(ro)" in create.text else FAIL,
              "clone mode source mount shows (ro)" if "(ro)" in create.text else create.text[-400:]),
        Check("kit policy hosts (record these)", INFO, sbx("policy", "ls", ctx.name, "--wide").text),
        Check("guest workdir mirrors host path", PASS if pwd == guest_path(ctx.repo) else INFO,
              f"guest {pwd!r}, expected {guest_path(ctx.repo)!r}"),
    ]
