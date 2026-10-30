---
name: setup-smoketest-docker-sandbox
description: Set up and run Claude Code, Codex or pi inside a local Docker Sandbox (sbx microVM) on Windows, macOS or Linux in a reproducible way, with a least-access network and workspace policy and a smoke test. Use when the user wants to try, set up, reproduce, or tear down Docker Sandboxes (sbx), or run a coding agent in a Docker microVM.
---

# Docker Sandboxes: reproducible local trial

Background: [docker-sandbox-local-agent-guide.md](../../../docs/analysis/execution/docker-sandbox-local-agent-guide.md). Why Docker Sandboxes: [executive-summary.md](../../../docs/analysis/executive-summary.md). This skill is the runnable checklist; if it disagrees with Docker's live docs (https://docs.docker.com/ai/sandboxes/), say so and follow the live docs.

| File | Holds |
|------|-------|
| [PLATFORM-WINDOWS.md](PLATFORM-WINDOWS.md), [PLATFORM-MACOS-LINUX.md](PLATFORM-MACOS-LINUX.md) | install, preflight, host shell and path syntax |
| [CHECKS.md](CHECKS.md) | what to check before, right after, and after the sandbox exists |
| [SMOKETEST.md](SMOKETEST.md) | each smoke test, its pass criteria, open observations |
| [RECORD.md](RECORD.md) | where and how to write the trial record |
| `smoketest.py` | automates preflight, create, tests, teardown, record |
| [`scripts/pull_docker_commits.py`](../../../scripts/pull_docker_commits.py) | pulls the commits made in the sandbox clone into a host branch; `smoketest.py` tests it on a temp branch (check 9) |

## Ground rules

- Ask the user before installing software, enabling OS features, or running `sbx login`.
- Never type or paste credentials, and never print secret values. The user runs `sbx login` and `sbx secret set ...`; tell them the command.
- Start with least access: `deny-all` network, clone mode, no SSH agent forwarding unless needed.
- **You run steps 5-8 yourself.** `sbx run` opens an interactive agent session and needs a terminal, which your shell tool lacks. `sbx create` and `sbx exec` do not, and the smoke test needs no agent and no agent login. Before handing any command to the user, check `sbx --help` for a verb that works without a terminal. Hand over only the logins, secrets and the agent's own `/login`, or a command that failed.
- **A failed or impossible check never stops the run.** Record it as FAIL (it ran and gave the wrong result) or SKIP (it could not run, with the reason), carry on with every remaining step, and list all FAIL and SKIP items for the user at the end ("report to the user"). Stop early only when nothing exists to test (`sbx` unusable, sandbox name taken, `sbx create` failed), or when continuing needs consent you do not have (install, login, deleting something this run did not create). Never fix a failure by weakening the check or by putting a credential into the sandbox.
- **A successful task by the agent itself inside the sandbox is a hard requirement.** A sandbox whose agent cannot authenticate and finish work is not a working setup, however well the isolation checks pass. Check 8e has the real agent (`claude -p`) read a file in the workspace and reply with a random token, using a credential the guest never holds; it must PASS. The script ends with `SETUP VERIFIED` or `SETUP NOT VERIFIED` and exits non-zero unless 8e passed; a SKIP or `--no-inference` counts as not verified. Report "not verified" to the user, never "working". `sbx secret ls` showing `(stored)` does not prove the key is valid: a rejected key is found by the fast probe in 8c. For a subscription, use the sandbox login described in step 4 (no API-key secret stored); for an API key, the user re-stores it with `sbx secret set anthropic` (`--force` matters only with `--token`). Then create the sandbox again and re-run. The user does this; you never read or handle the key or token.
- Only ever stop or remove the sandbox this run created. Other sandboxes on the machine are the user's. Never run `sbx diagnose --upload`.

## Pick your platform first

Detect the host OS, then read the matching file **before step 1** and the live docs it links. Check for WSL before concluding "Linux": `uname -r` containing `microsoft`, or `grep -qi microsoft /proc/version`, means the shell is WSL on a Windows host. `sbx` runs on the Windows host, so the Windows file applies even from a WSL shell.

- Windows 11 host, native or WSL → [PLATFORM-WINDOWS.md](PLATFORM-WINDOWS.md)
- macOS, or native Linux (not WSL) → [PLATFORM-MACOS-LINUX.md](PLATFORM-MACOS-LINUX.md)

Do not conclude from `/etc/os-release` alone that the host is plain Ubuntu: under WSL it reports the distro, not the Windows host.

## Workflow

```
- [ ] 1. Preflight (platform file, CHECKS.md)
- [ ] 2. Install sbx (platform file; ask first)
- [ ] 3. Sign in and init policy (skip if already done; user runs)
- [ ] 4. Authenticate the agent (only if the agent itself will be used; user runs)
- [ ] 5-8. Run smoketest.py: create, test, teardown, record
- [ ] 9. Read the output and write up findings
```

1. **Preflight.** Follow the platform file and [CHECKS.md](CHECKS.md), including the live-docs comparison.
2. **Install** only after asking, per the platform file. Skip when `sbx version` works.
3. **Sign in and policy.** If `sbx ls` and `sbx policy ls` succeed the user is signed in; if `default-deny-all` is listed the policy exists. Otherwise the user runs:
   ```sh
   sbx login
   sbx policy init deny-all
   ```
4. **Agent auth is needed for the inference check.** For a Claude subscription the user logs in inside a built-in `claude` sandbox: `sbx run --name <sb> -- auth login --claudeai`, with no `anthropic` API-key secret stored (a stored key forces API-key mode and wins); `sbx secret ls` then shows `(oauth configured)`; see develop-sandbox/docker/CREDENTIALS.md. For an API key the user stores it with `sbx secret set anthropic` (or `sbx secret set openai --oauth` for Codex); `sbx secret ls` should show it as `(stored)`. If none is stored, still run the script: the inference check will FAIL or SKIP and you report that. Do not ask the user to paste a secret into chat, and do not put a token into the sandbox environment as a workaround.
5. **Run the script** from the repo that holds this skill:
   ```sh
   python -I .claude/skills/setup-smoketest-docker-sandbox/smoketest.py --record
   ```
   It creates a throwaway repo, runs `sbx create --clone --name trial-<HHMMSS> claude <repo>`, runs the checks in [SMOKETEST.md](SMOKETEST.md) with `sbx exec`, tears down in a `finally`, and appends a Run section to the trial record ([RECORD.md](RECORD.md)). Exit 0 = no FAIL, 1 = a FAIL, 2 = could not start. It prints a "REPORT TO THE USER" list of every FAIL and SKIP at the end: relay it. Flags: `--agent codex|pi` (pi needs `--kit`, see the last section), `--keep` (skip teardown; you must then run `sbx rm --force <name>` yourself, and any manual debug sandbox too), `--name`, `--model` (model for the raw API probe; default `claude-haiku-5-5`), `--no-inference`. Omit `--record` for a dry run.
6. **Interpret.** Read every FAIL and INFO line. INFO items are observations nobody has classified: decide whether each is a finding ([SMOKETEST.md](SMOKETEST.md) lists the open ones), and add them with evidence to the record. If the script itself breaks, run the checks by hand from SMOKETEST.md and fix the script.

Manual teardown, if needed: `sbx stop <name>` then `sbx rm --force <name>`. `--force` is required from a non-interactive shell; it discards unfetched commits in the clone, which is fine for the throwaway repo.

## Gotchas

- Docker's default agent launch bypasses the agent's own inner sandbox (`--dangerously-skip-permissions` / `--dangerously-bypass-approvals-and-sandbox`); the microVM and network policy are the boundary.
- Direct mount (`sbx run --name x claude .`) lets the agent change the host tree immediately and read ignored files; use only after the clone trial.
- Network policy changes apply immediately; workspace choices are fixed at creation.
- Balanced and Locked Down hold unmatched requests for developer approval (`sbx policy approval ...`); the agent must retry.
- Under `deny-all` a blocked request also queues a pending approval, and `curl` exits 0 after the proxy's `403`. Judge by the response text, not the exit code.
- A new sandbox already carries a kit policy allowing a few hosts (7 for `claude`); `deny-all` is not empty. List them with `sbx policy ls <name> --wide`.
- Clone mode keeps the agent's commits only inside the VM, on its own branches (the clone starts on the host's branch name, e.g. `main`, but it is a separate copy). `git fetch sandbox-<name>` on the host never touches your local branches or working tree. It writes the guest's branches to two places: `refs/remotes/sandbox-<name>/<branch>` and `refs/sandboxes/<name>/<branch>` (the remote has both refspecs; verified). Merge or branch from either, e.g. `git merge sandbox-<name>/feature-x` or `git branch keep refs/sandboxes/<name>/feature-x`. `sbx rm` deletes the remote and `refs/remotes/...` but leaves `refs/sandboxes/<name>/*`, so fetch first. Removal also deletes the sandbox's per-sandbox policy rules and pending approvals (observed).
- Sandbox names: letters, numbers, hyphens and periods, starting with a letter or number, at least two characters; `default` is reserved.
- A sandbox defaults to the whole host (the host's full CPU count and memory); pass `--cpus`/`--memory` to `sbx create` for a lighter trial. The first `sbx create` pulls the image and can take minutes, so give it a long timeout (the script allows 600 s).
- The guest environment contains credential-like variables you did not set. `GH_TOKEN` is a placeholder (hash differs from the host's), but `SSH_AUTH_SOCK` is unreviewed until [SMOKETEST.md](SMOKETEST.md) check 6 is resolved. Never print their values; compare by hash.
- `python` is the command on Windows, `python3` on macOS and Linux; always use `-I`. Use absolute paths: the shell's working directory can change between calls, and the record belongs to this skill's repo, not the current one.
- A kit that is not a built-in agent needs a one-time credential binding approved by the user (see the pi section); look for `no binding authorizes ...` in the `sbx create` output.
- Findings are tied to the `sbx` version recorded in each run (v0.50.1 so far). Re-run after an upgrade and compare with the earlier run sections.
- Not tried, but `sbx policy check`, `sbx policy log` and `sbx policy inspect` exist and may give a cleaner allow/deny assertion than `curl` text. Verify before relying on them.

## Running pi instead of claude

[pi](https://github.com/badlogic/pi-mono) (`@mariozechner/pi-coding-agent`, command `pi`, `pi -p "<prompt>"`) is not an sbx built-in. The repo ships a v3 workload kit, [kit-pi/](kit-pi/) (`kit.yaml` + `kit.dockerfile`: the `claude-code` base image has Node 22+, npm installs pi, ENTRYPOINT `pi`). Run:

```sh
python -I .claude/skills/setup-smoketest-docker-sandbox/smoketest.py --agent pi --kit <absolute path to kit-pi> --record
```

`--kit` replaces the agent name in `sbx create`; use a native path (Git Bash: `cygpath -w`). Checks 8b and the Anthropic probe in 8c are claude-only and skipped; 8d still applies. The script passes `--provider anthropic` because pi defaults to Google.

Credentials (verified 2026-10-29, sbx v0.50.1): the kit declares a `credential@1` OAuth capability for service `anthropic` that writes pi's `~/.pi/agent/auth.json` with only the two `proxy-managed` sentinels; the real subscription token stays in the host store (same one the built-in claude login fills, see develop-sandbox/docker/CREDENTIALS.md). A third-party kit is not trusted with it by default: `sbx create` prints `no binding authorizes anthropic - the credential was not injected` and pi gets `401`. **The user must approve the binding once**, either by running `sbx create --name x <kit-pi path>` in a real terminal and answering the prompt, or by adding to `%APPDATA%\sbx\credentials.yaml` (`~/.config/sbx/credentials.yaml`; approvals only, no secrets):

```yaml
bindings:
  anthropic:
    oauth: {}
```

(The `oauth` body format is unverified; the interactive prompt writes the correct entry.) Until then 8c/8e FAIL and the run is `SETUP NOT VERIFIED`. Do not write that file yourself: it grants a kit your subscription.

## After setup

Tell the user the next steps: day-to-day use and permission changes are in the [Docker Sandboxes how-to](../../../docs/guides/how-to/docker-sandbox-how-to.md); a project-specific sandbox is built with `/develop-sandbox` (type Docker).
