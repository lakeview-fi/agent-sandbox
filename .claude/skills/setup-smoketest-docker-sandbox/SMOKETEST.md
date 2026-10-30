# Smoke test: checks and pass criteria

`smoketest.py` implements everything here; this file is the source of truth for what each check means. Run a check by hand only when the script fails or you are investigating a finding. Run guest commands with `sbx exec trial sh -c '...'` (Linux guest on every OS). Never ask the user to run them and do not start the agent: `sbx run` needs a terminal, `sbx exec` does not.

## Judging results

- Judge a block by the text, not the exit code. `curl` exits 0 on a blocked HTTPS request, and `curl -sI` prints the proxy's `HTTP/1.1 200 OK` CONNECT reply before the real `403`. Blocked means the body says `Approval required for <host>:<port>` (or the status is `403`) and the real page content is absent.
- A blocked request also queues a pending approval (`sbx policy approval ls`). Take a baseline first: the sandbox queues its own blocked traffic while idle (`download.docker.com`, `cli.github.com`, the Ubuntu mirrors).
- PASS and FAIL are expectations the skill has verified. INFO items are observations that nobody has classified yet: read them and decide whether each is a finding.

## Checks with pass criteria

| # | Check | PASS when |
|---|-------|-----------|
| 1 | `curl -s https://example.com` before any allow rule | body contains `Approval required` or `403`, and not `Example Domain` |
| 2a | `sbx policy allow network --sandbox trial example.com`, then retry | allow exits 0 and the body contains `Example Domain` |
| 2b | Fetch `https://example.org` | still blocked as in check 1 |
| 2c | `sbx policy rm network --sandbox trial --resource example.com --force`, then retry | blocked again within 10 s, with no restart. 2a and 2c together show rules change live; the script reports the seconds it took |
| 3 | In the guest, commit a new file in the workspace clone | guest commit succeeds; the host has no such file; host `HEAD` unchanged; the only new host remote is `sandbox-<name>` |
| 9 | **Pull script on a temp branch.** On branch `trial/pull-test` of the throwaway repo, run [`scripts/pull_docker_commits.py`](../../../scripts/pull_docker_commits.py)` trial --merge` for the commit made in check 3 | exits 0, prints `merged=true`, and `from-sandbox.txt` is now in the host tree on the temp branch |
| 9b | Run the same command again | exits 0 and prints `RESULT: nothing-new` |
| 9c | Switch back and delete the temp and `agent/*` branches | the starting branch is at the same commit as before check 9 |
| 4a | List the guest copy of the host home directory | only the first path component leading to the workspace is present (on Windows: `AppData`); no `src`, `Documents`, `.ssh`, `.claude` |
| 4b | `touch /run/sandbox/source/probe` | fails (read-only) and the host has no `probe` file; SKIP when the mount does not exist |
| 8a | `<agent> --version` in the guest | exits 0 |
| 8c | **LLM inference (pre-check):** a fast probe first (one raw API call with the helper's value), then `claude -p "Reply with the single word OK"` (Codex: `codex exec ...`) | the probe is not 401/403, and the agent exits 0 within 90 s with `OK` in the reply. A 401 fails at once with the reason instead of waiting out `claude -p`'s silent retries |
| 8e | **REQUIRED: agent task.** The agent reads `note.txt` in the workspace and replies with its content in uppercase | the reply contains a random token that exists only in the file, so the Read tool ran and the model answered. Not attempted (FAIL) when 8c failed. The overall verdict is NOT VERIFIED, and the exit code non-zero, unless this PASSes; a SKIP counts as not verified |
| 8d | Search guest env and home for a raw `sk-ant-` string | none found (a hit may be a placeholder: check length and hash before concluding) |

`claude -p` retries a rejected credential silently for minutes, so a hung call (exit 124) tells you nothing by itself. That is why 8c runs the fast probe first and adds **8c-diag**: one raw API call using whatever the sandbox's `apiKeyHelper` returns, printing only the helper command, the value length, the HTTP status and the API's error text. A `401 invalid x-api-key` with helper `echo proxy-managed` means the proxy did not substitute the stored secret: the stored value is wrong, expired or the wrong type (an API key versus a `claude setup-token` value: never store a setup-token as the `anthropic` secret, it is sent as `x-api-key`), or the sandbox was created before it was stored. `sbx secret ls` showing `(stored)` proves none of that.

**Manual debug recipe** (Git Bash: use `cygpath -w` for host paths passed to `sbx`): (1) `sbx exec <name> sh -c 'cat ~/.claude/settings.json'` shows the helper command, which holds no secret. (2) Run the 8c-diag call by hand and read only the status and error text. (3) On a 401 the user either re-stores a valid Console API key with `sbx secret set anthropic`, or removes the secret (`sbx secret rm anthropic`) and logs in with `sbx run --name <sb> -- auth login --claudeai` (subscription; verify `~/.claude/.credentials.json` holds 2 `proxy-managed` sentinels, never cat it). Then you create the sandbox again (secrets apply at creation) and re-run. Never read, print or paste the key.

The create output must also show the source mount as `(ro)`, and `pwd` in the guest should equal the host workspace path (path mirrored into the VM: host usernames are visible inside it).

The OpenShell skill runs the same questions with its own check numbers; the parity table is in [its SMOKETEST.md](../setup-smoketest-openshell/SMOKETEST.md). Keep the two in step when adding a check to either.

## Observations (INFO, no verdict yet)

| # | Probe | Why it matters |
|---|-------|----------------|
| 5 | Raw TCP connect to `1.1.1.1:443`, then `curl --noproxy '*'` to it | The connect succeeds under `deny-all` but the HTTP status is `000`: only the handshake passes (consistent with a proxy accepting then dropping), no data flows. A status of `200/301` would be a hole in the network policy. HTTPS is covered; other protocols are not tested |
| 6 | Secret-like environment variable names and value lengths | The guest has `GH_TOKEN`, `SSH_AUTH_SOCK`, `SSH_AUTH_SOCK_GATEWAY`, `MCP_SENTINEL_TOKEN_NAME` and `SBX_CRED_ANTHROPIC_MODE`. **Resolved:** `GH_TOKEN` is a placeholder; its hash matched neither the host env nor `gh auth token`. **Explained:** `SSH_AUTH_SOCK` exists because the sbx setting `ssh.agentForwardingEnabled` defaults to `true`, forwarding the host SSH agent; the ground rule is no forwarding unless asked for, so suggest `sbx settings set ssh.agentForwardingEnabled false` (then restart the daemon) as a user decision. Never print values; compare by hash (first 12 hex characters) without displaying either side |
| 6b | Anthropic credential in the guest | No `ANTHROPIC_API_KEY`, `CLAUDE_CODE_OAUTH_TOKEN` or `~/.claude/.credentials.json`; `claude auth status` reports `loggedIn: true` via `apiKeyHelper` (built-in `claude` agent), and the helper is `echo proxy-managed`. With a stored API-key secret, a `401 invalid x-api-key` in check 8c means the stored value is invalid or the wrong type; use the subscription login instead (see 8c-diag above and the verification status below) |
| 7 | Approvals queued during the tests | Separates your tests' entries from the sandbox's own background traffic |

Manual extras worth adding when a project depends on them: reachability of host-local services from the guest, DNS behaviour for blocked hosts, and whether an SSH agent socket is forwarded (it must not be unless asked for).

## Verification status of this skill

Verified (Windows 11, `sbx` v0.50.1, `claude` agent): every isolation and policy check passed in the full script runs. **Agent verified (2026-10-29):** with the subscription `/login` (no API-key secret stored; guest holds only the two `proxy-managed` sentinels) 8c and 8e PASS and the run ends `SETUP VERIFIED`. A stored `anthropic` secret that is invalid or of the wrong type (API-key mode, `x-api-key`) fails with a 401. The 8d check ignores the sbx sentinels.

pi (kit-pi, 2026-10-29): isolation checks, 8a and 8d pass. 8c and 8e need the user to approve the kit's `anthropic` credential binding once (see SKILL.md) and fail with `401` until then. Not verified end to end.

Not verified: `--keep`; `--agent codex`; macOS and Linux (including the host-to-guest path mapping and the `/run/sandbox/source` mount); the comparison against Docker's live docs; any `sbx` version other than v0.50.1. A run on a new OS or version should say which of these it covered.

## Kit hosts

A new sandbox carries a kit policy that allows a few hosts (7 for `claude` on `sbx` v0.50.1), so `deny-all` is not empty. `sbx policy ls trial --wide` lists the individual hosts and rule IDs; the script puts the full text in the record. Compare against what you expect for the agent: API endpoint, package registries, telemetry. An unexpected host is a finding.

## Package installs by the agent (findings by hand, not yet scripted)

Hand-run on 2026-10-29 in a built-in `claude` sandbox (user `agent`, passwordless sudo, python3 3.14, pip, uv, apt, Ubuntu 26.04). The agent should be given these tasks once 8e passes; until then they were run as plain shell commands, which exercise the same network path.

- **Python (`pip install --target /tmp/x requests`).** Blocked at first (`No matching distribution found`; each blocked host queues an approval). It needs `pypi.org:443` and then `files.pythonhosted.org:443`, discovered one at a time. Answering the approvals with `sbx policy approval respond <id> --option allow` (rules are stored as `created via approval`, scoped to the sandbox) or `sbx policy allow network --sandbox <name> "pypi.org,files.pythonhosted.org"` both work, live; the install then succeeded.
- **Linux (`sudo apt-get install -y tree`).** Needs `archive.ubuntu.com` and `security.ubuntu.com` on port 80: `sbx policy allow network --sandbox <name> "archive.ubuntu.com,security.ubuntu.com"`. `apt-get update` still exits 100, because the image ships two third-party repos (`download.docker.com`, `cli.github.com`) that stay blocked; the Ubuntu indexes and the install itself worked. Allow those two hosts as well for a clean update, or tell the agent to ignore that exit code.
- Approvals for hosts you did not allow stay pending until the sandbox is removed. Only approve hosts you expect (check the title first).
