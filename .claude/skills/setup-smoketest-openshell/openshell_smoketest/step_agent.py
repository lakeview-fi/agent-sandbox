"""Check 8: agent CLI, credential placeholder (8b), LLM inference (8c), 8e via agent_task, raw-key search (8d)."""
import os
import re
import shlex

from .agent_task import agent_task
from .config import OPENROUTER_JS
from .helpers import sha12
from .model import FAIL, PASS, SKIP, Check, Ctx
from .process import gsh, gx, osh


def step_agent_and_inference(ctx: Ctx) -> list[Check]:
    a, n = ctx.args, ctx.name
    out = []
    ver = gx(n, ctx.args.agent, "--version")
    has_agent = ver.code == 0
    out.append(Check(f"8a {a.agent} CLI runs in the sandbox", PASS if has_agent else SKIP, ver.text[:200] if has_agent else f"{a.agent} not in this image (expected with --image default); report this"))
    cred_keys = []
    if ctx.provider:
        got = osh("provider", "get", ctx.provider).text
        m = re.search(r"Credential keys:\s*(.*)", got)
        cred_keys = [k.strip() for k in m.group(1).split(",")] if m else []
    for k in cred_keys:
        val = gsh(n, f"printenv {shlex.quote(k)} || true").stdout.strip()
        host = os.environ.get(k, "")
        real_shaped = val.startswith(("sk-", "ghp_", "github_pat_")) or (host != "" and sha12(val) == sha12(host))
        out.append(Check(f"8b provider credential {k} in the guest is a placeholder", PASS if val and not real_shaped else (SKIP if not val else FAIL),
                         f"present, length {len(val)}, hash {sha12(val)[:8]}" if val else "variable not set in the guest"))
    if a.no_inference:
        out.append(Check("8c LLM inference", SKIP, "--no-inference given; report this gap to the user"))
    elif not ctx.provider:
        out.append(Check("8c LLM inference", SKIP, "no provider configured in the gateway (the user must add one with openshell provider create; do not handle the key); report this"))
    elif ctx.provider_type == "openrouter":
        if "node" not in (ctx.client, ) and gsh(n, "command -v node").code != 0:
            out.append(Check("8c LLM inference via provider openrouter", SKIP, "node not in the image; provider rules allow only node"))
        else:
            r = gx(n, "node", "-e", OPENROUTER_JS.replace("MODEL_PLACEHOLDER", a.model), timeout=90)
            last = r.text.splitlines()[-1] if r.text else ""
            ok = "HTTP 200" in last and 'reply ""' not in last  # judge the last attempt; earlier ones may be empty or rate-limited
            out.append(Check("8c LLM inference via provider openrouter (credential held by the gateway)", PASS if ok else FAIL, r.text[:300]))
    elif ctx.provider_type == "anthropic" and has_agent and a.agent == "claude":
        r = gx(n, "claude", "-p", "Reply with the single word OK", timeout=120)
        out.append(Check("8c LLM inference through claude -p", PASS if r.code == 0 and re.search(r"\bOK\b", r.text) else FAIL, f"exit {r.code}; {r.text[:200]}"))
    else:
        out.append(Check("8c LLM inference", SKIP, f"no test for provider type {ctx.provider_type!r}; report this"))
    out.append(agent_task(ctx, has_agent))  # always present: a missing agent task must never look like a pass
    leak = gsh(n, "env | grep -c 'sk-' ; grep -rIl 'sk-or-\\|sk-ant-' /sandbox /tmp 2>/dev/null | head -5; true")
    found = [ln for ln in leak.stdout.splitlines() if ln.strip() not in ("", "0")]
    out.append(Check("8d no raw API key string (sk-...) in guest env or work dirs", PASS if not found else FAIL,
                     "none found" if not found else f"matches (env count / files): {found}; may be a placeholder, check length and hash"))
    return out
