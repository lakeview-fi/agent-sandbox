"""Check 8e (REQUIRED): the agent itself completes a file-reading task. AgentSpec/AGENTS say how to run each agent."""
import uuid
from dataclasses import dataclass

from .model import FAIL, PASS, SKIP, Check, Ctx
from .process import gsh, osh


@dataclass(frozen=True)
class AgentSpec:
    """How to run one coding agent for check 8e. Add an entry to AGENTS to support another agent."""
    binaries: list[str]   # processes that call openrouter.ai; the L7 rule is scoped to exactly these
    openrouter_env: str   # env prefix mapping the agent onto the provider's placeholder credential
    openrouter_model: str  # model flag for the openrouter provider
    command: str          # one-shot command; {model} is replaced, the prompt is appended
    needs_rule: bool      # the provider rule allows only node; native agents need their own L7 rule
    setup: str = ""       # shell run in the guest before the task (agent config), e.g. an output-token cap


AGENTS = {
    "claude": AgentSpec(
        ["/usr/local/lib/node_modules/@anthropic-ai/claude-code/bin/claude.exe", "/usr/local/bin/claude", "/usr/local/bin/node"],
        "CLAUDE_CODE_MAX_OUTPUT_TOKENS=4000 ANTHROPIC_BASE_URL=https://openrouter.ai/api "
        "ANTHROPIC_AUTH_TOKEN=$OPENROUTER_API_KEY ANTHROPIC_API_KEY= ",
        "--model anthropic/claude-haiku-4.5", "claude -p {model} --dangerously-skip-permissions", True),
    # pi is a node script: the network client is /usr/local/bin/node, which the provider rule already allows.
    # pi reads OPENROUTER_API_KEY itself (the guest value is the placeholder) and defaults to openrouter.ai/api/v1.
    "pi": AgentSpec(
        ["/usr/local/bin/node"], "PI_OFFLINE=1 ",
        "--provider openrouter --model anthropic/claude-haiku-4.5", "pi -p {model} --no-session", False,
        # Output-token cap: a spend-limited OpenRouter key otherwise fails with 402 (pi asks for 64000 by default).
        # Config goes in pi's agent dir, ~/.pi/agent/models.json; it holds no credential.
        setup="mkdir -p ~/.pi/agent && echo '{\"providers\":{\"openrouter\":{\"modelOverrides\":"
              "{\"anthropic/claude-haiku-4.5\":{\"maxTokens\":4000}}}}}' > ~/.pi/agent/models.json"),
}


def agent_task(ctx: Ctx, has_agent: bool) -> Check:
    """8e (REQUIRED): the agent itself completes a tool-using task (reads a file) inside the sandbox.

    This is the end-to-end proof that the sandboxed agent authenticates and works; without a PASS here the setup is
    reported as NOT VERIFIED (see agent_verified). With an openrouter provider the agent is mapped onto the provider's
    placeholder credential (AGENTS[...].openrouter_env); native agents (claude) also need an L7 rule for their binaries
    because the provider rule allows only node. With an anthropic provider claude is run as is (pi is not supported).
    """
    n, agent = ctx.name, ctx.args.agent
    name = f"8e {agent} agent completes a file-reading task"
    spec = AGENTS.get(agent)
    if spec is None:
        return Check(name, SKIP, f"no AgentSpec for {agent!r} in AGENTS; the setup is NOT verified")
    if ctx.args.no_inference:
        return Check(name, SKIP, "--no-inference given; the setup is NOT verified until this passes")
    if not has_agent:
        return Check(name, SKIP, f"{agent} is not in this image; the setup is NOT verified")
    if not ctx.provider:
        return Check(name, SKIP, "no provider in the gateway; the user must add one (openshell provider create). The setup is NOT verified")
    env, model = "", ""
    if ctx.provider_type == "openrouter":
        if spec.needs_rule:
            bins = [x for b in spec.binaries for x in ("--binary", b)]
            pol = osh("policy", "update", n, "--add-endpoint", "openrouter.ai:443:read-write:rest:enforce", *bins, "--wait", timeout=120)
            if pol.code != 0:
                return Check(name + " (policy rule for agent binary)", FAIL, pol.text[-300:])
        env, model = spec.openrouter_env, spec.openrouter_model
    elif ctx.provider_type != "anthropic" or agent != "claude":
        return Check(name, SKIP, f"no way to run {agent} with provider type {ctx.provider_type!r}; the setup is NOT verified")
    token = "tok-" + uuid.uuid4().hex[:8]  # only in the file, never in the prompt: a correct reply proves the Read tool ran
    script = (f'cd /sandbox && echo "{token}" > note.txt && {spec.setup + " && " if spec.setup else ""}{env}timeout 150 {spec.command.format(model=model)} '
              '"Read /sandbox/note.txt and reply with its content in uppercase, nothing else."')
    for attempt in (1, 2):  # one retry for transient model/provider errors; failing twice is a FAIL
        r = gsh(n, script, timeout=180)
        reply = r.stdout.strip()
        ok = r.code == 0 and token.upper() in reply.upper()
        if ok:
            break
    return Check(name + f" through {ctx.provider_type}", PASS if ok else FAIL,
                 f"attempt {attempt}; exit {r.code}; reply: {reply[-120:]!r}; stderr: {r.stderr.strip()[-200:]!r}; expected {token.upper()}")
