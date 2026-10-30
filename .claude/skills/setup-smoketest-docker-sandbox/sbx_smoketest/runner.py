"""Runs the check groups in order; a crash in one group never stops the others."""
from .model import FAIL, SKIP, Check, Ctx
from .step_agent import step_agent
from .step_create import step_create
from .step_isolation import step_clone_isolation, step_host_visibility
from .step_network import step_network
from .step_observations import step_observations
from .step_pull_script import step_pull_script


STEPS = [step_network, step_clone_isolation, step_pull_script, step_host_visibility, step_agent, step_observations]


def run_checks(ctx: Ctx) -> list[Check]:
    checks = _guarded(step_create, ctx)
    for step in STEPS:
        if not ctx.created:
            checks.append(Check(step.__name__, SKIP, "sandbox was not created; report this to the user"))
        else:
            checks += _guarded(step, ctx)
    return checks


def _guarded(step, ctx: Ctx) -> list[Check]:
    try:
        return step(ctx)
    except Exception as exc:  # one broken group must not hide the others
        return [Check(step.__name__, FAIL, f"check group crashed: {exc!r}")]
