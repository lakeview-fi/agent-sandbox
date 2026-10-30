#!/usr/bin/env python3
"""Docker Sandboxes smoke test: create a clone-mode sandbox, run the checks, tear down.

Run:   python -I smoketest.py [--record] [--keep] [--no-inference]
Exit:  0 = no FAIL, 1 = at least one FAIL, 2 = could not start (sbx unusable or name taken).

Failure policy: a check that fails or cannot run is recorded (FAIL or SKIP with the reason)
and the remaining checks still run. Only a missing/unusable sbx or a failed `sbx create`
stops the tests, because nothing exists to test. The run ends with a list to report to
the user. Checks and pass criteria: SMOKETEST.md; preflight and teardown: CHECKS.md.
Only the sandbox this script creates is ever stopped or removed. No installs, no login,
no credential handling; credential values are never printed (names, lengths, hashes only).
"""
import argparse
import datetime
import os
import platform
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent
REPO_ROOT = SKILL_DIR.parents[2]  # <repo>/.claude/skills/<skill>
PULL_SCRIPT = REPO_ROOT / "scripts" / "pull_docker_commits.py"
PASS, FAIL, INFO, SKIP = "PASS", "FAIL", "INFO", "SKIP"
GIT_ID = ["-c", "user.name=trial", "-c", "user.email=trial@example.invalid"]
AGENT_CLI = {  # agent -> (version command, one-shot prompt command)
    "claude": (["claude", "--version"], ["claude", "-p", "Reply with the single word OK"]),
    "codex": (["codex", "--version"], ["codex", "exec", "Reply with the single word OK"]),
    "pi": (["pi", "--version"], ["pi", "--provider", "anthropic", "-p", "Reply with the single word OK"]),  # not an sbx built-in: needs --kit
}
# Extra `sbx exec` flags per agent (e.g. ["-e", "VAR=placeholder"]); none needed so far (pi gets its sentinel auth file from the kit).
AGENT_EXEC_ENV: dict[str, list[str]] = {}


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
    repo: Path
    base: dict
    args: argparse.Namespace
    created: bool = False
    gws: str = ""
    head_before: str = ""
    remotes_before: set = field(default_factory=set)
    approvals_before: set = field(default_factory=set)


def run(cmd: list[str], timeout: int = 120, cwd: Path | None = None) -> Out:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=timeout, stdin=subprocess.DEVNULL, cwd=cwd)
    except subprocess.TimeoutExpired:
        return Out(124, "", f"timeout after {timeout}s: {' '.join(cmd)}")
    return Out(p.returncode, p.stdout, p.stderr)


def sbx(*args: str, timeout: int = 120) -> Out:
    return run(["sbx", *args], timeout)


def guest(name: str, script: str, timeout: int = 60) -> Out:
    """Run a shell snippet inside the sandbox (Linux guest) in its default workdir."""
    return sbx("exec", name, "sh", "-c", script, timeout=timeout)


def git(repo: Path, *args: str) -> Out:
    return run(["git", "-C", str(repo), *args])


def guest_path(p: Path) -> str:
    """Host path -> path as mirrored inside the guest (observed on Windows: C:\\a\\b -> /c/a/b)."""
    s = str(p)
    if os.name == "nt":
        drive, rest = os.path.splitdrive(s)
        return "/" + drive[0].lower() + rest.replace("\\", "/")
    return s


def is_blocked(text: str) -> bool:
    return ("Approval required" in text or "403" in text) and "Example Domain" not in text


def fetch(name: str, host: str) -> Out:
    return guest(name, f"curl -s -m 15 https://{host}")


def wait_until(pred, timeout: float = 10.0, step: float = 1.0) -> float | None:
    """Seconds until pred() is true, or None on timeout. Measures how fast a policy change applies."""
    start = time.monotonic()
    while True:
        if pred():
            return time.monotonic() - start
        if time.monotonic() - start >= timeout:
            return None
        time.sleep(step)


def pending_titles(name: str) -> list[str]:
    titles = []
    for line in sbx("policy", "approval", "ls").text.splitlines():
        fields = re.split(r"\s{2,}", line.strip())
        if len(fields) >= 3 and fields[1] == name:
            titles.append(fields[2])
    return titles


def sandbox_names() -> set[str]:
    lines = sbx("ls").stdout.splitlines()[1:]
    return {ln.split()[0] for ln in lines if ln.strip()}


def make_repo() -> Path:
    repo = Path(tempfile.mkdtemp(prefix="sbx-trial-")).resolve()
    run(["git", "init", "-q"], cwd=repo)
    (repo / "README.md").write_text("# throwaway repo for sbx smoke test\n")
    run(["git", "add", "README.md"], cwd=repo)
    run(["git", *GIT_ID, "commit", "-q", "-m", "init"], cwd=repo)
    return repo


def rmtree(path: Path) -> None:
    def _writable(func, p, _exc):
        os.chmod(p, stat.S_IWRITE)
        func(p)
    shutil.rmtree(path, onerror=_writable)


# --- preflight ---------------------------------------------------------------------------

def preflight(name: str) -> tuple[list[Check], dict, bool]:
    """Returns checks, baseline, and whether it is possible to continue."""
    checks, base = [], {}
    if not shutil.which("sbx") or not shutil.which("git"):
        return [Check("sbx and git on PATH", FAIL, "install sbx (see the platform file) and git")], base, False
    version = sbx("version")
    base["version"] = version.text.splitlines()[0] if version.text else "unknown"
    checks.append(Check("sbx version", PASS if version.code == 0 else FAIL, base["version"]))
    ls, pol = sbx("ls"), sbx("policy", "ls")
    base["sandboxes"] = sandbox_names()
    usable = ls.code == 0 and pol.code == 0
    checks.append(Check("sbx usable (signed in, daemon up)", PASS if usable else FAIL,
                        f"{len(base['sandboxes'])} existing sandboxes left alone" if usable else f"{ls.text}\n{pol.text}"))
    has_deny = "default-deny-all" in pol.text
    checks.append(Check("deny-all policy present", PASS if has_deny else FAIL,
                        "default-deny-all listed" if has_deny else "missing: ask the user to run sbx policy init deny-all; later checks will show the effect"))
    free = name not in base["sandboxes"]
    checks.append(Check("sandbox name free", PASS if free else FAIL, name))
    diag = sbx("diagnose", "--format", "json", timeout=180)
    checks.append(Check("sbx diagnose", INFO, f"exit {diag.code}; {len(diag.text)} chars of report (read it if anything fails)"))
    return checks, base, usable and free


# --- check groups (each returns a list of Check; a crash in one never stops the others) --------

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


def step_network(ctx: Ctx) -> list[Check]:
    a, n = ctx.args, ctx.name
    out = []
    t1 = fetch(n, a.allow_host)
    out.append(Check(f"1 {a.allow_host} blocked under deny-all", PASS if is_blocked(t1.text) else FAIL, t1.text[:300]))
    allow = sbx("policy", "allow", "network", "--sandbox", n, a.allow_host)
    secs = wait_until(lambda: "Example Domain" in fetch(n, a.allow_host).text, timeout=10)
    out.append(Check(f"2a {a.allow_host} reachable after allow (live, no restart)", PASS if allow.code == 0 and secs is not None else FAIL,
                     f"allow exit {allow.code}; reachable after {secs:.1f}s" if secs is not None else f"allow exit {allow.code}; still blocked after 10s: {allow.text[:200]}"))
    t2b = fetch(n, a.other_host)
    out.append(Check(f"2b {a.other_host} still blocked", PASS if is_blocked(t2b.text) else FAIL, t2b.text[:300]))
    rm = sbx("policy", "rm", "network", "--sandbox", n, "--resource", a.allow_host, "--force")  # --force: no terminal to confirm
    secs = wait_until(lambda: is_blocked(fetch(n, a.allow_host).text), timeout=10)
    out.append(Check(f"2c {a.allow_host} blocked again after rule removal (live)", PASS if rm.code == 0 and secs is not None else FAIL,
                     f"rm exit {rm.code}; blocked after {secs:.1f}s" if secs is not None else f"rm exit {rm.code}; still reachable after 10s: {rm.text[:200]}"))
    return out


def step_clone_isolation(ctx: Ctx) -> list[Check]:
    n, repo = ctx.name, ctx.repo
    commit = guest(n, f"cd {shlex.quote(ctx.gws)} && echo hello > from-sandbox.txt && git {' '.join(GIT_ID)} add from-sandbox.txt "
                      f"&& git {' '.join(GIT_ID)} commit -qm from-sandbox && git rev-parse HEAD")
    new_remotes = set(git(repo, "remote").stdout.split()) - ctx.remotes_before
    leaked = (repo / "from-sandbox.txt").exists() or git(repo, "rev-parse", "HEAD").stdout.strip() != ctx.head_before
    ok = commit.code == 0 and not leaked and new_remotes <= {f"sandbox-{n}"}
    return [Check("3 clone commit not in host tree", PASS if ok else FAIL,
                  f"guest commit exit {commit.code}; host file/HEAD changed: {leaked}; new host remotes: {sorted(new_remotes)}")]


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
        probe = anthropic_probe(n) if agent == "claude" else ""
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


def anthropic_probe(name: str) -> str:
    """One raw API call using whatever the sandbox's apiKeyHelper returns. Prints only the helper
    command, the value LENGTH, the HTTP status and the API's error text; never the credential."""
    script = (
        'H=$(sed -n "s/.*\\"apiKeyHelper\\"[^\\"]*\\"\\([^\\"]*\\)\\".*/\\1/p" ~/.claude/settings.json | head -1); '
        'echo "helper command: [$H]"; [ -n "$H" ] || exit 0; K=$(sh -c "$H" 2>/dev/null); echo "helper value length: ${#K}"; '
        'curl -s -m 30 -w "\\nHTTP %{http_code}\\n" https://api.anthropic.com/v1/messages -H "x-api-key: $K" '
        '-H "anthropic-version: 2023-06-01" -H "content-type: application/json" '
        '-d \'{"model":"claude-haiku-5-5","max_tokens":8,"messages":[{"role":"user","content":"Reply with the single word OK"}]}\' | cut -c1-300'
    )
    return guest(name, script, timeout=90).text


def step_observations(ctx: Ctx) -> list[Check]:
    n = ctx.name
    tcp = guest(n, 'timeout 5 bash -c "exec 3<>/dev/tcp/1.1.1.1/443" && echo CONNECTED || echo FAILED')
    flow = guest(n, "curl --noproxy '*' -sk -m 8 -o /dev/null -w '%{http_code}' https://1.1.1.1; true")
    env = guest(n, "env | grep -Ei '^[^=]*(key|token|secret|passw|ssh_auth|credential)' "
                   "| awk -F= '{print $1\" (value length \"length($0)-length($1)-1\")\"}' || echo none")
    new_titles = sorted(set(pending_titles(n)) - ctx.approvals_before)
    return [
        Check("5 raw TCP to 1.1.1.1:443 (connect / HTTP status, 000 = no data)", INFO, f"{tcp.text[-100:]} / {flow.text[-100:]}"),
        Check("6 secret-like env vars (names and value lengths only)", INFO, env.text or "none"),
        Check("7 approvals queued during tests", INFO, ", ".join(new_titles) or "none"),
    ]


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


# --- teardown and output -----------------------------------------------------------------

def teardown(name: str, repo: Path | None, base: dict) -> list[Check]:
    checks = []
    if name not in sandbox_names():
        checks.append(Check("teardown: sandbox existed", INFO, "never created"))
    else:
        sbx("stop", name)
        rm = sbx("rm", "--force", name, timeout=180)
        checks.append(Check("teardown: sbx rm --force", PASS if rm.code == 0 else FAIL, "removed" if rm.code == 0 else rm.text[-200:]))
    left = sandbox_names()
    checks.append(Check("teardown: sandbox gone", PASS if name not in left else FAIL, name))
    vanished = sorted(base["sandboxes"] - left)  # only a sandbox that existed before this run and is gone is a finding
    appeared = sorted(left - base["sandboxes"])  # created by someone else while this run was going (concurrent sessions)
    checks.append(Check("teardown: other sandboxes untouched", FAIL if vanished else PASS,
                        f"vanished since the start: {vanished}" if vanished else "all sandboxes that existed before are still there"))
    if appeared:
        checks.append(Check("teardown: sandboxes created by others during this run (not touched)", INFO, ", ".join(appeared)))
    checks.append(Check("teardown: no policy left for sandbox", PASS if f"sandbox:{name}" not in sbx("policy", "ls").text else FAIL, ""))
    checks.append(Check("teardown: no pending approvals for sandbox", PASS if not pending_titles(name) else FAIL, ""))
    if repo and repo.exists():
        rmtree(repo)
    return checks


def host_label() -> str:
    if sys.platform == "darwin":
        return "macos"
    return "windows" if os.name == "nt" else "linux"


def render(name: str, base: dict, checks: list[Check], run_no: int) -> str:
    today = datetime.date.today().isoformat()
    lines = [f"## Run {run_no} ({today}, `{base['version']}`, {platform.platform()})", "",
             f"Sandbox `{name}` created with `sbx create --clone`, checked with `sbx exec` by `smoketest.py`.", "",
             "| Check | Result | Detail |", "|---|---|---|"]
    for c in checks:
        detail = c.detail.replace("\n", "<br>").replace("|", "\\|")[:400]
        lines.append(f"| {c.name} | {c.status} | {detail} |")
    lines += ["", "Full text of the multi-line items (kit hosts):", ""]
    for c in checks:
        if c.name.startswith("kit policy hosts"):
            lines += ["```", c.detail, "```"]
    return "\n".join(lines) + "\n"


def append_record(base: dict, checks: list[Check], name: str) -> Path:
    path = REPO_ROOT / "docs" / "trials" / f"docker-sandboxes-{host_label()}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    # An existing file without "## Run" headings is itself run 1.
    numbers = [int(n) for n in re.findall(r"^#{2,3} Run (\d+)", existing, re.M)]
    run_no = (max(numbers) if numbers else (1 if existing else 0)) + 1
    section = render(name, base, checks, run_no)
    header = "" if existing else f"# Docker Sandboxes trial: {host_label().title()}\n\nRecords appended by `smoketest.py`; add findings by hand under each run.\n\n"
    path.write_text(existing + ("\n" if existing else "") + header + section, encoding="utf-8")
    index = REPO_ROOT / "docs" / "index.md"
    if index.exists() and "trials" not in index.read_text(encoding="utf-8"):
        print("NOTE: docs/index.md does not mention trials/; add it.")
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
        print("\n=== SETUP VERIFIED: the agent completed a task inside the sandbox with credentials the guest does not hold ===")
    else:
        print("\n=== SETUP NOT VERIFIED: the agent did NOT complete a task inside the sandbox (check 8e). "
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
    ap.add_argument("--agent", default="claude", help="claude, codex or pi (names the CLI the checks run)")
    ap.add_argument("--kit", default="", help="sandbox kit reference (e.g. ./kit) passed to sbx create instead of the agent name; required for pi")
    ap.add_argument("--allow-host", default="example.com")
    ap.add_argument("--other-host", default="example.org")
    ap.add_argument("--no-inference", action="store_true", help="skip the LLM inference check (reported as SKIP)")
    ap.add_argument("--record", action="store_true", help="append a Run section to docs/trials/docker-sandboxes-<os>.md")
    ap.add_argument("--keep", action="store_true", help="skip teardown (you must run sbx rm --force yourself)")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    checks, base, can_continue = preflight(args.name)
    if not can_continue:
        print_table(checks)
        print_report(checks)
        return 2
    repo = make_repo()
    ctx = Ctx(args.name, repo, base, args)
    try:
        checks += run_checks(ctx)
    finally:
        if not args.keep:
            checks += teardown(args.name, repo, base)
    print_table(checks)
    print_report(checks)
    if args.record:
        print(f"\nRecord appended to {append_record(base, checks, args.name)}")
    return 1 if any(c.status == FAIL for c in checks) or not agent_verified(checks) else 0


if __name__ == "__main__":
    sys.exit(main())
