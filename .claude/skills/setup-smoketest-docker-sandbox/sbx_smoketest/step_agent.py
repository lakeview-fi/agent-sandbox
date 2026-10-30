"""Check 8: agent CLI, LLM inference, agent file-reading task (8e) and the raw-key search (8d)."""
import re
import shlex
import uuid

from .config import AGENT_CLI, AGENT_EXEC_ENV
from .model import FAIL, INFO, PASS, SKIP, Check, Ctx
from .process import guest, sbx


def step_agent(ctx: Ctx) -> list[Check]:
    """Agent CLI present, logged in, and able to do LLM inference without a raw key in the guest."""
    n, agent = ctx.name, ctx.args.agent
    if agent not in AGENT_CLI:
        return [Check("8 agent inference", SKIP, f"no one-shot command known for agent {agent!r}")]
    version_cmd, prompt_cmd = AGENT_CLI[agent]
    xenv = AGENT_EXEC_ENV.get(agent, [])
    ver = sbx("exec", *xenv, n, *version_cmd, timeout=60)
    out = [Check(f"8a {agent} CLI runs in the sandbox", PASS if ver.code == 0 else FAIL, ver.text[:200])]
    if agent == "claude":
        auth = sbx("exec", n, "claude", "auth", "status", timeout=60)
        out.append(Check("8b claude auth status (no secrets in output)", INFO, auth.text[:400]))
    if ctx.args.no_inference:
        out.append(Check("8c LLM inference through the agent", SKIP, "--no-inference given; report this gap to the user"))
    elif ver.code != 0:
        out.append(Check("8c LLM inference through the agent", SKIP, f"{agent} CLI did not run, so inference cannot be tested"))
    else:
        probe = anthropic_probe(n, ctx.args.model) if agent == "claude" else ""
        status = re.search(r"HTTP (\d{3})", probe)
        if status and status.group(1) in ("401", "403"):
            # `claude -p` retries a rejected credential silently for minutes, so fail fast with the reason instead.
            out.append(Check("8c LLM inference through the agent", FAIL,
                             f"fast probe: the API rejected the sandbox's credential (HTTP {status.group(1)}); claude -p not run because it would only retry silently. "
                             "(sbx secret ls showing (stored) does not prove the key is valid.)"))
            out.append(Check("8c-diag Anthropic API response to the sandbox's own credential", INFO, probe))
        else:
            reply = sbx("exec", *xenv, n, *prompt_cmd, timeout=90)
            ok = reply.code == 0 and re.search(r"\bOK\b", reply.text) is not None
            out.append(Check("8c LLM inference through the agent", PASS if ok else FAIL,
                             f"exit {reply.code}; reply: {reply.text[:200]}"))
            if not ok and probe:
                out.append(Check("8c-diag Anthropic API response to the sandbox's own credential", INFO, probe))
    out.append(agent_task(ctx, agent, ver.code == 0, out))
    # sbx's own sentinels (sk-ant-oat01-proxy-managed, sk-ant-ort01-proxy-managed in ~/.claude/.credentials.json) are not keys
    real_key = "sk-ant-(?!(oat01|ort01)-proxy-managed)"
    leak = guest(n, f"env | grep -cP '{real_key}' ; grep -rIlP '{real_key}' \"$HOME\" 2>/dev/null | head -5; true")
    found = [ln for ln in leak.stdout.splitlines() if ln.strip() not in ("", "0")]
    out.append(Check("8d no raw Anthropic key string in guest env or home", PASS if not found else FAIL,
                     "none found" if not found else f"pattern sk-ant- (other than the sbx proxy-managed sentinels) found (env count / files): {found}; check length and hash before concluding"))
    return out


def agent_task(ctx: Ctx, agent: str, cli_ok: bool, checks: list[Check]) -> Check:
    """8e (REQUIRED): the agent itself completes a tool-using task (reads a file) inside the sandbox.

    This is the end-to-end proof that the sandboxed agent authenticates and works; without a PASS here the setup is
    reported as NOT VERIFIED (see agent_verified). The token is only in the file, never in the prompt, so a correct
    reply proves the agent's Read tool ran and the model answered.
    """
    name = "8e agent completes a file-reading task"
    if agent not in AGENT_CLI or ctx.args.no_inference:
        return Check(name, SKIP, "inference not run (--no-inference or unknown agent); the setup is NOT verified")
    if not cli_ok:
        return Check(name, SKIP, f"{agent} CLI did not run; the setup is NOT verified")
    inference = next((c for c in checks if c.name.startswith("8c LLM")), None)
    if inference is None or inference.status != PASS:
        return Check(name, FAIL, "not attempted: the one-word inference check (8c) did not pass, so the agent cannot authenticate; the setup is NOT verified")
    token = "tok-" + uuid.uuid4().hex[:8]
    guest(ctx.name, f"cd {shlex.quote(ctx.gws)} && echo {token} > note.txt")
    prompt = "Read note.txt in the current directory and reply with its content in uppercase, nothing else."
    cmd = {"claude": ["claude", "-p", "--dangerously-skip-permissions", prompt], "pi": ["pi", "--provider", "anthropic", "-p", prompt]}.get(agent, ["codex", "exec", prompt])
    r = sbx("exec", "-w", ctx.gws, *AGENT_EXEC_ENV.get(agent, []), ctx.name, *cmd, timeout=180)
    ok = r.code == 0 and token.upper() in r.text.upper()
    return Check(name, PASS if ok else FAIL, f"exit {r.code}; reply: {r.text[-120:]!r}; expected {token.upper()}")


def anthropic_probe(name: str, model: str) -> str:
    """One raw API call using whatever the sandbox's apiKeyHelper returns. Prints only the helper
    command, the value LENGTH, the HTTP status and the API's error text; never the credential."""
    script = (
        'H=$(sed -n "s/.*\\"apiKeyHelper\\"[^\\"]*\\"\\([^\\"]*\\)\\".*/\\1/p" ~/.claude/settings.json | head -1); '
        'echo "helper command: [$H]"; [ -n "$H" ] || exit 0; K=$(sh -c "$H" 2>/dev/null); echo "helper value length: ${#K}"; '
        'curl -s -m 30 -w "\\nHTTP %{http_code}\\n" https://api.anthropic.com/v1/messages -H "x-api-key: $K" '
        '-H "anthropic-version: 2023-06-01" -H "content-type: application/json" '
        f'-d \'{{"model":"{model}","max_tokens":8,"messages":[{{"role":"user","content":"Reply with the single word OK"}}]}}\' | cut -c1-300'
    )
    return guest(name, script, timeout=90).text
