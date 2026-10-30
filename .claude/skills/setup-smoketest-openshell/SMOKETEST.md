# Smoke test: checks and pass criteria

`smoketest.py` implements everything here; this file is the source of truth for what each check means. Run a check by hand only when the script fails or you are investigating a finding: `openshell sandbox exec trial -- <command>` (Linux guest). Do not ask the user to run checks you can run, and do not start an interactive agent session.

## Judging results

- **PASS and FAIL** are expectations this skill has verified. **SKIP** means the check could not run (the reason is in the detail). **INFO** items are observations nobody has classified: read them and decide whether each is a finding.
- A FAIL or SKIP never stops the run. Everything else still runs, and every FAIL and SKIP is reported to the user at the end.
- Judge a network block by the client's output, not an exit code: `BLOCKED EACCES` (node), `HTTP 000` (curl). Allowed means `HTTP 2xx/3xx`.
- Only network policy hot-reloads; filesystem and process policy are fixed at creation.

## Checks with pass criteria

| # | Check | PASS when |
|---|-------|-----------|
| 1 | Fetch `https://example.com` before any rule | blocked (`BLOCKED EACCES`; log `NET:REFUSE`) |
| 2-dry | `openshell policy update trial --add-endpoint example.com:443 --binary <client> --dry-run` | exits 0 and the host stays blocked (nothing applied) |
| 2a | Same command with `--wait`, then retry | reachable within 15 s, no restart; the script reports the seconds |
| 2b | Fetch `https://example.org` | still blocked |
| 2c | Fetch `example.com` with a different client (curl) | blocked: the rule is scoped to the listed binary. SKIP when the image has no second client |
| 2d | `--remove-endpoint example.com:443 --wait`, then retry | blocked again within 15 s, no restart |
| 3a | Create a file in the sandbox project copy | not in the host project directory (upload is a copy) |
| 3b | `openshell sandbox download` of that file | the file arrives with the right content (deliberate handoff works) |
| 10 | **Pull script on a temp branch.** Upload a throwaway dir, make a baseline commit and an agent commit in the sandbox (needs `git` in the image: SKIP and report if missing). On branch `trial/pull-test` of a throwaway host repo run [`scripts/pull_openshell_changes.py`](../../../scripts/pull_openshell_changes.py)` trial --workdir /sandbox/<dir> --merge` | exits 0, prints `mode=commits` and `merged=true`, and the agent's file is in the host tree on the temp branch |
| 10b | After resetting the temp branch, add an uncommitted file in the sandbox and run with `--mode diff --dry-run` | exits 0, prints `RESULT: dry-run`, and no `agent/*` branch is left (the combined patch applies) |
| 10c | `test ! -e /sandbox/.sandbox-pull` in the sandbox | the script removed its scratch directory |
| 10d | Switch back and delete the temp and `agent/*` branches | the starting branch is at the same commit as before check 10 |
| 4 | `openshell sandbox upload trial <dir> /sandbox/` | lands at `/sandbox/<dir>/...`, not `/sandbox/<dir>/<dir>/...` |
| 5a | `ls /mnt/c` in the guest | absent (no Windows drive mounts) |
| 5b | List the host home directory path in the guest | exits non-zero or shares no entry with the host home; no `.ssh`, `.aws`, `.gnupg`, `.claude` |
| 5c | `touch /usr/probe` | fails (read-only path). A success means Landlock `best_effort` did not enforce the filesystem policy: report it |
| 5d | `touch /tmp/probe` | succeeds (sanity: the writable path works) |
| 8a | `<agent> --version` (`claude` or `pi`) | exits 0 |
| 8b | Provider credential variable in the guest (e.g. `OPENROUTER_API_KEY`) | set, but not key-shaped (`sk-...`) and not equal to the host's value by hash; length and an 8-hex-char hash are reported, never the value |
| 8c | **LLM inference** through the attached provider | `HTTP 200` with a non-empty reply from the last attempt. For `openrouter`, a node request tries up to three free models (they can be empty or rate-limited; pass `--model` to pin one). For an `anthropic` provider, `claude -p "Reply with the single word OK"` replies `OK` |
| 8e | **REQUIRED: agent task.** The agent itself (`claude`, or `pi` with `--agent pi`) reads a file and replies (with an `openrouter` provider it needs the L7 rule and `ANTHROPIC_*` mapping below; with an `anthropic` provider it runs as is) | `claude -p` / `pi -p` replies with a random token that exists only in the file, so the Read tool ran and the model answered (one retry for transient errors). The overall verdict is NOT VERIFIED, and the exit code non-zero, unless this PASSes; a SKIP counts as not verified |
| 8d | Search guest env and work dirs for `sk-...` strings | none found (a hit may be a placeholder: check length and hash before concluding) |

**8e is the check that proves the setup works end to end**: the sandboxed agent authenticates with a credential the guest never holds and completes a task. 8c is the cheap pre-check (the provider path works without the agent). A provider must exist in the gateway; the user creates it (the key never goes through you). With none configured 8e is a SKIP: report "not verified".

## Running pi through an `openrouter` provider (check 8e, `--agent pi`)

`openrouter` is the example provider here; any provider that the gateway holds works the same way (adapt the host and environment names). Tested with pi 0.73.1, image `trial-pi:local`, model `anthropic/claude-haiku-4.5`: `SETUP VERIFIED`.

1. **No policy rule needed.** pi is a node script (`/usr/local/bin/pi` links to `.../pi-coding-agent/dist/cli.js`), so the process calling `openrouter.ai` is `/usr/local/bin/node`, already allowed by `_provider_openrouter`.
2. **No env mapping needed.** pi's built-in `openrouter` provider reads `OPENROUTER_API_KEY` (the guest's placeholder) and uses `https://openrouter.ai/api/v1`. Run `pi -p --provider openrouter --model anthropic/claude-haiku-4.5 --no-session "<prompt>"` with `PI_OFFLINE=1` (no update checks). pi runs tools without permission prompts.
3. **Output-token cap.** pi requests 64000 output tokens by default, so a spend-limited key fails with `402 ... can only afford ...`. The script writes `~/.pi/agent/models.json` in the guest with `modelOverrides` `maxTokens: 4000` for that model (no credential in it).

## Running claude through an `openrouter` provider (check 8e)

Three things are needed, and `smoketest.py` does all of them:

1. **Policy rule for the claude binary.** The provider rule `_provider_openrouter` allows only `/usr/local/bin/node`, but `claude` is a native `claude.exe`. Add an L7 rule (the plain L4 form is refused with "uses L4-only; configure L7 inspection"); `--binary` is repeatable:
   `openshell policy update <name> --add-endpoint openrouter.ai:443:read-write:rest:enforce --binary /usr/local/lib/node_modules/@anthropic-ai/claude-code/bin/claude.exe --binary /usr/local/bin/claude --binary /usr/local/bin/node --wait`
2. **Environment mapping** (the guest only holds the provider's placeholder, the gateway swaps in the real key): `ANTHROPIC_BASE_URL=https://openrouter.ai/api`, `ANTHROPIC_AUTH_TOKEN=$OPENROUTER_API_KEY`, `ANTHROPIC_API_KEY=` (empty), and `--model anthropic/claude-haiku-4.5`.
3. **`CLAUDE_CODE_MAX_OUTPUT_TOKENS=4000`.** A key with a spend limit otherwise fails with `402 ... requested up to 32000 tokens, can only afford ...`.

`--dangerously-skip-permissions` is acceptable here only because the sandbox is the boundary. A harmless `unrecognized_model` warning may appear.

Policy Advisor (check 10 shows `agent_policy_proposals_enabled <unset>`): enable it with `openshell settings set <name> agent_policy_proposals_enabled true` (verify the key name with `openshell settings get <name>`) before running the optional approval-flow check.

## Observations (INFO, no verdict yet)

| # | Probe | What it showed |
|---|-------|----------------|
| 6 | Raw TCP to `1.1.1.1:443` | `bash: connect: Permission denied`: blocked at the socket, stricter than the Docker Sandboxes proxy, which accepted the handshake and dropped data |
| 7 | Secret-like environment variable names and value lengths | only the provider's placeholder (`OPENROUTER_API_KEY`) |
| 9 | Denials in the sandbox log; Policy Advisor proposals | a denial was flushed to the gateway as a proposal (`proposals=1`) even with Advisor settings unset |
| 10 | `openshell settings get` | `agent_policy_proposals_enabled`, `proposal_approval_mode` unset. Whether the agent can approve its own proposal is not tested |

## Parity with the Docker Sandboxes skill

Both skills run the same questions; OpenShell has no clone mode, so work handoff is upload/download.

| Question | Docker Sandboxes check | OpenShell check |
|---|---|---|
| Blocked by default | 1 | 1 |
| Allow one host, others stay blocked | 2a, 2b | 2a, 2b |
| Rule removal applies live | 2c | 2d |
| Rule scoped finer than the host | not available (domain only) | 2c (per binary), 2-dry |
| Work does not leak to the host | 3 (clone commit) | 3a, 3b (upload copy, download handoff) |
| Host files not visible | 4a | 5a, 5b |
| Host source not writable / read-only paths | 4b | 5c, 5d |
| Agent CLI runs | 8a | 8a |
| LLM inference | 8c | 8c |
| Credential not in guest | 8d, env probes 6 | 8b, 8d, env probe 7 |
| Raw TCP, approvals/proposals | 5, 7 | 6, 9, 10 |
| Teardown leaves nothing | sandbox, policies, approvals, others untouched | sandbox, others untouched, temp dirs |

## Verification status of this skill

Tested with:

| Host | Driver | `openshell` | Agent and provider | Result |
|---|---|---|---|---|
| WSL2 on Windows 11 | Docker | 0.1.5 | Claude Code 2.1.312 (image `trial-claude:local`), `openrouter` | Every check above passes in a full script run, including inference (`HTTP 200`, reply `OK`), live add and remove of a rule, and 8e: the native `claude.exe` reads a file and replies with its random token (`SETUP VERIFIED`). |
| WSL2 on Windows 11 | Docker | 0.1.5 | pi 0.73.1 (image `trial-pi:local`), `openrouter` | `SETUP VERIFIED`. |

The teardown check "other sandboxes untouched" reports INFO instead of FAIL when a foreign sandbox vanishes during the run, because another session may be using the same gateway.

Not covered yet: MicroVM driver; an `anthropic` provider and `claude -p` inference; `--image default`; macOS and native Linux; native Windows (MXC); the Policy Advisor approval flow (that the agent cannot approve its own proposal); the failure path of the script (a failed `sandbox create`); `--record` against an existing record file; any other `openshell` version. A run on a new OS or version should say which of these it covered, and add a row above.

## Package installs by the agent (manual checks, not yet scripted)

Expected behaviour in a sandbox built from this skill's image (user `node`, no sudo, `/usr` and `/var/log` read-only by policy, python 3.11 once the image has `python3 python3-pip python3-venv`).

- **Python.** `python3 -m venv /sandbox/venv` works (the work dir is writable), but `pip install` is denied: `[Errno 13] Permission denied`, log `NET:OPEN DENIED /usr/bin/python3.11 -> pypi.org:443`. The denial line names the binary to allow. A rule needs the L7 form and both hosts, scoped to the interpreter: `openshell policy update <name> --add-endpoint pypi.org:443:read-write:rest:enforce --add-endpoint files.pythonhosted.org:443:read-write:rest:enforce --binary /usr/bin/python3.11 --wait` (untested; the form follows the openrouter rule that worked).
- **Linux packages are not possible in this sandbox profile, whatever the network policy.** `apt-get update` fails with `Permission denied` on `/var/lib/apt/lists/partial` and `/var/lib/dpkg/status`: the agent is not root, there is no sudo, and `/usr` is read-only. Installing system packages needs a different filesystem and user policy chosen at creation (`--policy`), which weakens the sandbox. Report this as a limit of the profile, not as a network failure, and prefer pip-in-venv or npm for the agent's dependencies.
