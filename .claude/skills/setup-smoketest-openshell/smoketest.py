#!/usr/bin/env python3
"""NVIDIA OpenShell smoke test: create a kept-alive sandbox, run the checks, tear down.

Run (in the shell where `openshell` works: Linux, macOS or WSL2):
       python3 -I smoketest.py [--record] [--keep] [--provider NAME] [--no-inference]
Exit:  0 = no FAIL, 1 = at least one FAIL, 2 = could not start (nothing to test against).

Failure policy: a check that fails or cannot run is recorded (FAIL, or SKIP with the reason)
and the remaining checks still run. Only a missing/unreachable openshell, a missing image or
a failed sandbox create stops the tests, because nothing exists to test. The run ends with a
list to report to the user. Checks and pass criteria: SMOKETEST.md; preflight and teardown:
CHECKS.md. Structure mirrors the Docker Sandboxes skill's smoketest.py on purpose; the two
scripts are self-contained so each skill can be copied alone.
Only the sandbox this script creates is ever deleted. No installs, no credentials handled;
credential values are never printed (names, lengths, hashes only).
"""
import argparse
import datetime
import hashlib
import os
import platform
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent
REPO_ROOT = SKILL_DIR.parents[2]  # <repo>/.claude/skills/<skill>
PULL_SCRIPT = REPO_ROOT / "scripts" / "pull_openshell_changes.py"
GIT_ID = "-c user.name=trial -c user.email=trial@example.invalid"
PASS, FAIL, INFO, SKIP = "PASS", "FAIL", "INFO", "SKIP"
CLIENTS = {  # guest HTTP clients, preferred first: name -> command builder taking a host
    "node": lambda h: ["node", "-e", f"fetch('https://{h}').then(r=>console.log('HTTP',r.status)).catch(e=>console.log('BLOCKED',e.cause?.code||e.message))"],
    "curl": lambda h: ["sh", "-c", f"curl -s -m 15 -o /dev/null -w 'HTTP %{{http_code}}' https://{h} || echo BLOCKED"],
    "python3": lambda h: ["python3", "-c", f"import urllib.request as u\ntry: print('HTTP',u.urlopen('https://{h}',timeout=15).status)\nexcept Exception as e: print('BLOCKED',type(e).__name__)"],
}
OPENROUTER_JS = r"""
const H={authorization:'Bearer '+process.env.OPENROUTER_API_KEY,'content-type':'application/json'};
(async()=>{
 let models=['MODEL_PLACEHOLDER'].filter(Boolean);
 if(!models.length){const m=await (await fetch('https://openrouter.ai/api/v1/models')).json();
  models=(m.data||[]).filter(x=>String(x.id).endsWith(':free')).slice(0,3).map(x=>x.id);}  // free models can be empty or rate-limited: try three
 if(!models.length){console.log('NOMODEL');return;}
 for(const model of models){
  const r=await fetch('https://openrouter.ai/api/v1/chat/completions',{method:'POST',headers:H,
   body:JSON.stringify({model,max_tokens:128,messages:[{role:'user',content:'Reply with the single word OK'}]})});
  const j=await r.json().catch(()=>({}));
  const c=(j.choices&&j.choices[0]&&j.choices[0].message&&j.choices[0].message.content)||'';
  console.log('HTTP',r.status,'model',model,'reply',JSON.stringify(c).slice(0,60),'error',JSON.stringify((j.error&&j.error.message)||'').slice(0,120));
  if(r.status===200&&c.trim())return;
 }
})().catch(e=>console.log('BLOCKED',(e.cause&&e.cause.code)||e.message));
"""


@dataclass
class Out:
    code: int
    stdout: str
    stderr: str

    @property
    def text(self) -> str:
        return (self.stdout + self.stderr).strip()


@dataclass
class Check:
    name: str
    status: str
    detail: str = ""


@dataclass
class Ctx:
    name: str
    base: dict
    args: argparse.Namespace
    proj: Path
    created: bool = False
    client: str = ""
    client_path: str = ""
    provider: str = ""
    provider_type: str = ""
    tmp_dirs: list = field(default_factory=list)


def run(cmd: list[str], timeout: int = 120) -> Out:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=timeout, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return Out(124, "", f"timeout after {timeout}s: {' '.join(cmd)}")
    return Out(p.returncode, p.stdout, p.stderr)


def osh(*args: str, timeout: int = 120) -> Out:
    return run(["openshell", *args], timeout)


def gx(name: str, *cmd: str, timeout: int = 60) -> Out:
    """Run a command inside the sandbox."""
    return osh("sandbox", "exec", name, "--timeout", str(timeout), "--no-tty", "--", *cmd, timeout=timeout + 30)


def gsh(name: str, script: str, timeout: int = 60) -> Out:
    return gx(name, "sh", "-c", script, timeout=timeout)


def phases() -> dict[str, str]:
    """Sandbox name -> phase. Rows look like: NAME  2026-10-29 06:03:32  Ready."""
    out = {}
    for line in osh("sandbox", "list").stdout.splitlines()[1:]:
        parts = re.split(r"\s{2,}", line.strip())
        if len(parts) >= 3:
            out[parts[0]] = parts[-1]
    return out


def wait_until(pred, timeout: float = 10.0, step: float = 1.0) -> float | None:
    """Seconds until pred() is true, or None on timeout. Measures how fast a change applies."""
    start = time.monotonic()
    while True:
        if pred():
            return time.monotonic() - start
        if time.monotonic() - start >= timeout:
            return None
        time.sleep(step)


def allowed(text: str) -> bool:
    return re.search(r"HTTP [23]\d\d", text) is not None


def fetch(ctx: Ctx, host: str, client: str | None = None) -> str:
    return gx(ctx.name, *CLIENTS[client or ctx.client](host), timeout=40).text


def sha12(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:12]


def host_label() -> str:
    if sys.platform == "darwin":
        return "macos"
    try:
        if "microsoft" in Path("/proc/version").read_text().lower():
            return "windows-wsl2"
    except OSError:
        pass
    return "linux"


# --- preflight ---------------------------------------------------------------------------

def preflight(name: str, args) -> tuple[list[Check], dict, bool]:
    checks, base = [], {}
    if not shutil.which("openshell"):
        return [Check("openshell on PATH", FAIL, "install per the platform file (ask the user first), then re-run")], base, False
    ver = osh("--version")
    base["version"] = ver.text.splitlines()[0] if ver.text else "unknown"
    checks.append(Check("openshell version", PASS if ver.code == 0 else FAIL, base["version"]))
    status = osh("status")
    connected = "Connected" in status.text
    checks.append(Check("gateway connected", PASS if connected else FAIL,
                        "Connected" if connected else f"{status.text[:300]} (see the platform file; may need the bash-sandbox bypass)"))
    base["phases"] = phases() if connected else {}
    free = name not in base["phases"]
    checks.append(Check("sandbox name free", PASS if free else FAIL, name))
    checks.append(Check("/dev/kvm (MicroVM possible?)", INFO, "present" if Path("/dev/kvm").exists() else "absent: Docker/Podman driver only, a weaker (shared-kernel) boundary; record this"))
    image_ok = True
    if args.image != "default":
        if shutil.which("docker"):
            image_ok = run(["docker", "image", "inspect", args.image]).code == 0
            checks.append(Check(f"image {args.image} present", PASS if image_ok else FAIL,
                                "found" if image_ok else "build it per SANDBOX-IMAGE.md, or use --image default (agent/node checks will SKIP)"))
        else:
            image_ok = False
            checks.append(Check("docker on PATH", FAIL, "needed to find the image; may be blocked by the agent's bash sandbox"))
    return checks, base, connected and free and image_ok


# --- check groups (each returns a list of Check; a crash in one never stops the others) --------

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


def step_network(ctx: Ctx) -> list[Check]:
    a, n = ctx.args, ctx.name
    if not ctx.client:
        return [Check("1-2 network checks", SKIP, "no HTTP client in the sandbox; report this to the user")]
    out = []
    t1 = fetch(ctx, a.allow_host)
    out.append(Check(f"1 {a.allow_host} blocked by default", PASS if not allowed(t1) else FAIL, t1[:300]))
    ep = f"{a.allow_host}:443"
    dry = osh("policy", "update", n, "--add-endpoint", ep, "--binary", ctx.client_path, "--dry-run")
    out.append(Check("2-dry dry-run previews the rule without applying", PASS if dry.code == 0 and not allowed(fetch(ctx, a.allow_host)) else FAIL, dry.text[:200]))
    upd = osh("policy", "update", n, "--add-endpoint", ep, "--binary", ctx.client_path, "--wait")
    secs = wait_until(lambda: allowed(fetch(ctx, a.allow_host)), timeout=15)
    out.append(Check(f"2a {a.allow_host} reachable after update (live, no restart)", PASS if upd.code == 0 and secs is not None else FAIL,
                     f"update exit {upd.code}; reachable after {secs:.1f}s" if secs is not None else f"update exit {upd.code}; still blocked after 15s: {upd.text[:200]}"))
    t2b = fetch(ctx, a.other_host)
    out.append(Check(f"2b {a.other_host} still blocked", PASS if not allowed(t2b) else FAIL, t2b[:300]))
    others = [c for c in CLIENTS if c != ctx.client and gsh(n, f"command -v {c}").code == 0]
    if others:
        t2c = fetch(ctx, a.allow_host, others[0])
        out.append(Check(f"2c rule is binary-scoped: {others[0]} still blocked for {a.allow_host}", PASS if not allowed(t2c) else FAIL, t2c[:300]))
    else:
        out.append(Check("2c rule is binary-scoped", SKIP, "no second HTTP client in the image"))
    rm = osh("policy", "update", n, "--remove-endpoint", ep, "--wait")
    secs = wait_until(lambda: not allowed(fetch(ctx, a.allow_host)), timeout=15)
    out.append(Check(f"2d {a.allow_host} blocked again after rule removal (live)", PASS if rm.code == 0 and secs is not None else FAIL,
                     f"remove exit {rm.code}; blocked after {secs:.1f}s" if secs is not None else f"remove exit {rm.code}; still reachable after 15s: {rm.text[:200]}"))
    return out


def step_host_visibility(ctx: Ctx) -> list[Check]:
    n = ctx.name
    home = Path.home()
    mnt = gsh(n, "ls /mnt/c 2>&1; ls /mnt 2>&1")
    out = [Check("5a host drive mounts (/mnt/c) not visible", PASS if "Users" not in mnt.text and "Windows" not in mnt.text else FAIL, mnt.text[:200] or "absent")]
    listing = gsh(n, f"ls -A {shlex.quote(str(home))} 2>&1")
    host_names = {p.name for p in home.iterdir() if not p.name.startswith(".")} if home.exists() else set()
    overlap = host_names & set(listing.stdout.split()) if listing.code == 0 else set()
    sensitive = gsh(n, f"for d in .ssh .aws .gnupg .claude; do [ -e {shlex.quote(str(home))}/$d ] && echo $d; done; true").stdout.split()
    out.append(Check("5b host home contents not visible", PASS if not overlap and not sensitive else FAIL,
                     f"guest {home}: exit {listing.code}; overlap with host: {sorted(overlap)}; sensitive dirs: {sensitive}"))
    ro = gsh(n, "touch /usr/probe 2>&1")
    rw = gsh(n, "touch /tmp/probe 2>&1 && echo writable")
    out.append(Check("5c read-only paths (/usr) not writable (filesystem policy enforced)", PASS if ro.code != 0 else FAIL,
                     ro.text[:200] or "write to /usr succeeded: Landlock best_effort may not have been enforced; report"))
    out.append(Check("5d /tmp writable (sanity)", PASS if "writable" in rw.text else FAIL, rw.text[:200]))
    return out


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


def step_observations(ctx: Ctx) -> list[Check]:
    n = ctx.name
    tcp = gsh(n, 'timeout 5 bash -c "exec 3<>/dev/tcp/1.1.1.1/443" && echo CONNECTED || echo FAILED')
    flow = gsh(n, "curl --noproxy '*' -sk -m 8 -o /dev/null -w '%{http_code}' https://1.1.1.1 2>&1; true")
    env = gsh(n, "env | grep -Ei '^[^=]*(key|token|secret|passw|ssh_auth|credential)' | awk -F= '{print $1\" (value length \"length($0)-length($1)-1\")\"}' || echo none")
    logs = osh("logs", n, "--source", "sandbox", "--since", "15m", "-n", "400").text
    refused = len(re.findall(r"NET:REFUSE|DENIED", logs))
    proposals = re.findall(r"[^\n]*proposals?=[^\n]*", logs)[:3]
    settings = osh("settings", "get", n).text
    return [
        Check("6 raw TCP to 1.1.1.1:443 (connect / HTTP status, 000 = no data)", INFO, f"{tcp.text[-100:]} / {flow.text[-100:]}"),
        Check("7 secret-like env vars (names and value lengths only)", INFO, env.text or "none"),
        Check("9 denials in the sandbox log; Policy Advisor proposals", INFO, f"{refused} refused/denied lines; proposals: {proposals or 'none seen'}"),
        Check("10 sandbox settings (is Policy Advisor enabled?)", INFO, "\n".join(settings.splitlines()[:25])),
    ]


STEPS = [step_upload, step_pull_script, step_network, step_host_visibility, step_agent_and_inference, step_observations]


def _guarded(step, ctx: Ctx) -> list[Check]:
    try:
        return step(ctx)
    except Exception as exc:  # one broken group must not hide the others
        return [Check(step.__name__, FAIL, f"check group crashed: {exc!r}")]


def run_checks(ctx: Ctx) -> list[Check]:
    checks = _guarded(step_create, ctx)
    for step in STEPS:
        if not ctx.created:
            checks.append(Check(step.__name__, SKIP, "sandbox was not created; report this to the user"))
        else:
            checks += _guarded(step, ctx)
    return checks


# --- teardown and output -----------------------------------------------------------------

def teardown(ctx: Ctx) -> list[Check]:
    n, base = ctx.name, ctx.base
    checks = []
    if n in phases():
        d = osh("sandbox", "delete", n, timeout=180)
        gone = wait_until(lambda: n not in phases(), timeout=90, step=3)
        checks.append(Check("teardown: sandbox delete", PASS if d.code == 0 and gone is not None else FAIL,
                            f"gone after {gone:.0f}s" if gone is not None else f"exit {d.code}; still listed after 90s: {d.text[-200:]}"))
    else:
        checks.append(Check("teardown: sandbox existed", INFO, "never created"))
    left = set(phases())
    # other sessions may delete sandboxes concurrently; this script only ever deletes its own, so a vanished one is INFO, not FAIL
    vanished = set(base["phases"]) - left
    checks.append(Check("teardown: other sandboxes untouched", PASS if not vanished else INFO,
                        f"before {sorted(base['phases'])}, after {sorted(left)}" + (f"; vanished {sorted(vanished)} (concurrent run? this script only deletes {n})" if vanished else "")))
    for d in [ctx.proj, *ctx.tmp_dirs]:
        shutil.rmtree(d, ignore_errors=True)
    checks.append(Check("teardown: temp dirs removed (image left in place)", PASS if not ctx.proj.exists() else FAIL, ""))
    return checks


def render(name: str, base: dict, checks: list[Check], run_no: int, args) -> str:
    today = datetime.date.today().isoformat()
    lines = [f"## Run {run_no} ({today}, `{base['version']}`, {platform.platform()})", "",
             f"Sandbox `{name}` from image `{args.image}`, created with `openshell sandbox create ... -- sleep infinity`, checked with `openshell sandbox exec` by `smoketest.py`.", "",
             "| Check | Result | Detail |", "|---|---|---|"]
    for c in checks:
        lines.append(f"| {c.name} | {c.status} | {c.detail.replace(chr(10), '<br>').replace('|', chr(92) + '|')[:400]} |")
    lines += ["", "Full text of the policy listings:", ""]
    for c in checks:
        if c.name.startswith("effective network policy"):
            lines += [f"{c.name}:", "```", c.detail, "```"]
    return "\n".join(lines) + "\n"


def append_record(base: dict, checks: list[Check], name: str, args) -> Path:
    path = REPO_ROOT / "docs" / "trials" / f"openshell-{host_label()}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    # An existing file without "## Run" headings is itself run 1.
    numbers = [int(n) for n in re.findall(r"^#{2,3} Run (\d+)", existing, re.M)]
    run_no = (max(numbers) if numbers else (1 if existing else 0)) + 1
    header = "" if existing else f"# OpenShell trial: {host_label()}\n\nRecords appended by `smoketest.py`; add findings by hand under each run.\n\n"
    path.write_text(existing + ("\n" if existing else "") + header + render(name, base, checks, run_no, args), encoding="utf-8")
    return path


def print_table(checks: list[Check]) -> None:
    for c in checks:
        rows = c.detail.splitlines()
        print(f"[{c.status:4}] {c.name}: {(rows[0] if rows else '')[:160]}")
        if c.status == INFO:  # observations: show the whole text, the agent must read it
            for row in rows[1:60]:
                print(f"         {row[:200]}")


def agent_verified(checks: list[Check]) -> bool:
    """Hard requirement: the agent itself must have completed a task in the sandbox (check 8e PASS)."""
    agent = [c for c in checks if c.name.startswith("8e")]
    return bool(agent) and all(c.status == PASS for c in agent)


def print_report(checks: list[Check]) -> None:
    bad = [c for c in checks if c.status in (FAIL, SKIP)]
    if agent_verified(checks):
        print("\n=== SETUP VERIFIED: the coding agent completed a task inside the sandbox with credentials the guest does not hold ===")
    else:
        print("\n=== SETUP NOT VERIFIED: the coding agent did NOT complete a task inside the sandbox (check 8e). "
              "Do not call this setup working; tell the user ===")
    print(f"\n=== REPORT TO THE USER: {sum(c.status == FAIL for c in checks)} FAIL, "
          f"{sum(c.status == SKIP for c in checks)} SKIP, plus INFO lines that need a decision ===")
    for c in bad:
        print(f"- {c.status} {c.name}: {c.detail.splitlines()[0][:200] if c.detail else ''}")
    if not bad:
        print("- no FAIL or SKIP; still read the INFO items above and the open items in SMOKETEST.md")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--name", default=f"trial-{datetime.datetime.now():%H%M%S}")
    ap.add_argument("--agent", default="claude", help="claude or pi (the CLI that checks 8a and 8e run)")
    ap.add_argument("--image", default="", help="local image tag (default trial-<agent>:local), or 'default' for OpenShell's default workload")
    ap.add_argument("--provider", default="", help="gateway provider to attach (default: the first one listed)")
    ap.add_argument("--model", default="", help="model for the openrouter inference check (default: first free model)")
    ap.add_argument("--allow-host", default="example.com")
    ap.add_argument("--other-host", default="example.org")
    ap.add_argument("--create-timeout", type=int, default=240)
    ap.add_argument("--no-inference", action="store_true", help="skip the LLM inference check (reported as SKIP)")
    ap.add_argument("--record", action="store_true", help="append a Run section to docs/trials/openshell-<os>.md")
    ap.add_argument("--keep", action="store_true", help="skip teardown (you must run openshell sandbox delete yourself)")
    args = ap.parse_args()
    args.image = args.image or f"trial-{args.agent}:local"

    checks, base, can_continue = preflight(args.name, args)
    if not can_continue:
        print_table(checks)
        print_report(checks)
        return 2
    proj = Path(tempfile.mkdtemp(prefix="osh-proj-"))
    (proj / "README.md").write_text("# throwaway project for openshell smoke test\n")
    (proj / "hello.py").write_text("print('hello')\n")
    ctx = Ctx(args.name, base, args, proj)
    try:
        checks += run_checks(ctx)
    finally:
        if not args.keep:
            checks += teardown(ctx)
    print_table(checks)
    print_report(checks)
    if args.record:
        print(f"\nRecord appended to {append_record(base, checks, args.name, args)}")
    return 1 if any(c.status == FAIL for c in checks) or not agent_verified(checks) else 0


if __name__ == "__main__":
    sys.exit(main())
