---
name: setup-smoketest-openshell
description: Set up and run Claude Code, Codex or pi inside a local NVIDIA OpenShell sandbox on macOS, Linux or Windows (experimental) in a reproducible way, with deny-by-default egress, a chosen compute driver, and a smoke test. Use when the user wants to try, set up, reproduce, or tear down NVIDIA OpenShell, openshell gateway or sandbox commands, or policy-governed agent sandboxes.
---

# NVIDIA OpenShell: reproducible local trial

Background: [nvidia-openshell-local-agent-guide.md](../../../docs/analysis/execution/nvidia-openshell-local-agent-guide.md). Why OpenShell: [executive-summary.md](../../../docs/analysis/executive-summary.md). This skill is the runnable checklist. Where it disagrees with OpenShell's live docs (https://docs.nvidia.com/openshell/latest/), say so and follow the docs.

## Ground rules

- Ask the user before installing anything; show the installer URL and get a yes first.
- Never type or paste credentials. The user supplies them at the CLI prompt; providers hold them in the gateway.
- Filesystem and process policy is fixed at sandbox creation; only network policy hot-reloads.
- Leave sandboxes, containers and images this run did not create alone (for example a pre-existing sandbox named `pi`).
- The agent's bash sandbox can block the Docker socket and the gateway. See "Running Docker and gateway commands".

## Run mode

Once the user has asked for the trial, run the steps in order without pausing. Stop only when:

- an install, a `sudo` command, or a change to Docker Desktop or WSL settings is needed;
- a credential is needed;
- a step would delete something this run did not create;
- nothing exists to test: the gateway is unreachable, the image is missing, or `sandbox create` failed.

**A failed or impossible check never stops the run.** Record it as FAIL (it ran and gave the wrong result) or SKIP (it could not run, with the reason), carry on with every remaining step, and list all FAIL and SKIP items for the user at the end ("report to the user"). Never fix a failure by weakening the check, by loosening policy, or by putting a credential into the sandbox.

**A successful task by the agent itself inside the sandbox is a hard requirement.** A sandbox whose agent cannot authenticate and finish work is not a working setup, however well the isolation checks pass. Check 8e has the real agent (`claude`, or `pi` with `--agent pi`) read a file and reply with a random token, using a credential the guest never holds; it must PASS. The script ends with `SETUP VERIFIED` or `SETUP NOT VERIFIED` and exits non-zero unless 8e passed. A SKIP counts as not verified: no provider (the user adds one with `openshell provider create`; you never handle the key), no agent CLI in the image, or `--no-inference`. Report any of these to the user as "not verified", never as "working". Check 8c (a plain provider request) is the cheap pre-check, not a substitute.

Before step 1, ask once for approval to run `openshell` and `docker` commands with the agent's bash sandbox bypassed. Record the answer in the trial file.

**Fast path:** if `openshell status` shows Connected, the image (`docker image inspect trial-claude:local`, or `trial-pi:local` for pi) exists and `openshell provider list` shows a provider, nothing needs installing or approving: skip steps 1-3's installs and go straight to the automated run. On an `openrouter` provider the script also runs check 8e, where `claude` itself completes a task (see SMOKETEST.md, "Running claude through openrouter"). A bash-bypass approval is only needed if a command is actually blocked.

## Pick your platform first

Detect the host OS, then read the matching file **before step 1** and the live docs it links. Check for WSL before concluding "Linux": `grep -qi microsoft /proc/version` succeeds under WSL, and the Windows side is the one that matters for the support decision. `/etc/os-release` alone does not tell you the host; under WSL it reports the distro.

- macOS, or native Linux (not WSL) → [PLATFORM-MACOS-LINUX.md](PLATFORM-MACOS-LINUX.md)
- Windows 11 host, native or WSL → [PLATFORM-WINDOWS.md](PLATFORM-WINDOWS.md). Not production-qualified; Docker Sandboxes is the supported alternative. For WSL2, tell the user which route you are on and get their yes. For Docker Desktop on WSL2, follow [WSL-DOCKER-DESKTOP.md](WSL-DOCKER-DESKTOP.md).

The platform files own preflight, driver choice, and install. The steps below are the same on every OS.

## Workflow

```
- [ ] 1. Preflight and driver (platform file)
- [ ] 2. Install CLI, check gateway
- [ ] 3. Build the agent image, create a kept-alive sandbox
- [ ] 4. Transfer a throwaway project in
- [ ] 5. Smoke test
- [ ] 6. Record versions and results
- [ ] 7. Teardown
```

### Automated run (steps 3-7)

After steps 1-2 and the image build, run the script in the shell where `openshell` works (WSL2 included; from Windows: `wsl -d <distro> -e sh -c 'cd /mnt/c/<repo> && python3 -I .claude/skills/setup-smoketest-openshell/smoketest.py --record'`; a full run takes a few minutes and prints a long table, so filter with `| grep -E "^\[(FAIL|SKIP)|8e|SETUP"` once you know the layout):

```sh
python3 -I .claude/skills/setup-smoketest-openshell/smoketest.py --record
```

It creates `trial-<HHMMSS>` kept alive with `sleep infinity`, uploads a throwaway project, runs every check in [SMOKETEST.md](SMOKETEST.md) with `openshell sandbox exec`, deletes only its own sandbox in a `finally`, and appends a Run section to the trial record ([RECORD.md](RECORD.md)). Exit 0 = no FAIL, 1 = a FAIL, 2 = could not start. It ends with a "REPORT TO THE USER" list of every FAIL and SKIP: relay it. Flags: `--agent claude|pi`, `--image default` (OpenShell's default workload; agent and node checks SKIP), `--provider NAME`, `--model ID`, `--no-inference`, `--keep`, `--name`. Omit `--record` for a dry run. Before/after checks: [CHECKS.md](CHECKS.md). The manual steps below are the fallback when the script cannot run, and they explain what it does.

### 2. CLI and gateway

1. `openshell gateway list`. A gateway may already be registered and selected (default name `openshell`, at `https://127.0.0.1:17670` in 0.1.5). Use it if so.
2. Otherwise register the URL the installer printed (on Linux/macOS, `https://127.0.0.1:17670`):
   ```sh
   openshell gateway add <printed-url> --local --name local
   openshell gateway select local
   ```
3. `openshell status` must show `Status: Connected`. If it shows `Connection refused`, the gateway is not running; see the platform file.
4. Validate config with `openshell-gateway config preflight --path ~/.config/openshell/gateway.toml`.

The live docs do not list an `openshell doctor check` command. Do not rely on it.

### 3. Build the image and create the sandbox

The default Ubuntu workload does not bundle agent CLIs. For Claude Code, build the image in [SANDBOX-IMAGE.md](SANDBOX-IMAGE.md) (`trial-claude:local`).

Create a sandbox that stays running. This form is verified: it reaches `Ready` and the image is found locally.

```sh
openshell sandbox create --name trial --from trial-claude:local -- sleep infinity
```

The command does not return while the sandbox runs. Start it in the background, or wrap it in `timeout`. Then check it with `openshell sandbox list` until the phase is `Ready`.

Check the agent inside the sandbox (verified: prints `2.1.312 (Claude Code)`):

```sh
openshell sandbox exec trial -- claude --version
```

For an interactive agent session, the user runs `openshell sandbox create ... -- claude` in a real terminal. Not verified here.

If a sandbox was created with an agent command instead of `sleep infinity`, it ends in `Completed` and cannot be used for `exec`. Delete it and recreate it.

### 4. Transfer a throwaway project

Create a throwaway folder outside any repository, for example under `$TMPDIR`, with a few harmless files. Do not upload a real project.

```sh
openshell sandbox upload trial <host-dir> /sandbox/
```

Upload to the **parent** directory. The basename is kept, so a folder named `src` lands at `/sandbox/src`. Passing `/sandbox/src` as the destination produced `/sandbox/src/src` in the observed run. Upload is a local copy through the gateway. It is not git-aware and does not apply `.gitignore`.

Verify: `openshell sandbox exec trial -- find /sandbox -maxdepth 2`.

### 5. Smoke test

The script runs these and more (full list and pass criteria: [SMOKETEST.md](SMOKETEST.md)). By hand, run the checks with `openshell sandbox exec trial -- <command>`. If the agent has no credentials, use a Node command, which the image includes. The egress check applies to it the same way.

1. External fetch must be denied:
   ```sh
   openshell sandbox exec trial -- node -e "fetch('https://example.com').then(r=>console.log('HTTP',r.status)).catch(e=>console.log('BLOCKED',e.cause?.code||e.message))"
   ```
   Expected before any rule: `BLOCKED EACCES`. The log shows `NET:REFUSE ... [reason:policy_dns_ineligible]`.
2. Add one destination as operator. Dry-run first, then apply and wait:
   ```sh
   openshell policy update trial --add-endpoint example.com:443 --binary /usr/local/bin/node --dry-run
   openshell policy update trial --add-endpoint example.com:443 --binary /usr/local/bin/node --wait
   ```
   The rule applies only to the listed binary. Retry the fetch: `HTTP 200` expected. Another host, such as `example.org`, must still be denied.
3. Inspect effective policy: `openshell policy get trial --base` and `--full`. Note any provider-added rules.
4. Confirm host files outside the uploaded project are not visible. In the trial image, `/mnt/c` is absent and `/home` is not readable.
5. Optional: enable Policy Advisor (off by default), trigger a denial, and confirm an operator must approve and the agent cannot approve its own proposal. A denial can still create a proposal at the gateway (`Flushed denial analysis to gateway proposals=...`). Record whether Advisor is enabled.

Read logs with `openshell logs trial --source sandbox --since 10m -n 60`. Do not use `--tail` from a non-interactive shell; it does not return.

### 6. Record

Write `docs/trials/openshell-<os>.md`. For WSL2 on Windows, use `openshell-windows-wsl2.md`. Include:

- date, host OS and version, WSL distro if any, `/dev/kvm` result;
- OpenShell CLI version, gateway endpoint and driver, Docker or Podman version if used;
- image tag, Node and Claude Code versions, supervisor tag;
- sandbox name and creation command;
- effective policy output;
- each smoke-test result, and each finding;
- approvals given, and what was torn down.

`docs/trials/` is created on the first `--record` run (or by hand) and is listed in `docs/index.md`. Its records are local and gitignored, so a fresh clone does not have it.

### 7. Teardown

1. Copy out any file you need: `openshell sandbox download trial ...`.
2. Delete the sandbox: `openshell sandbox delete trial`. The response is "cleanup is pending". Confirm with `openshell sandbox list`.
3. Remove the image only if asked: `docker rmi trial-claude:local`. Check that no container uses it first.
4. Record what was removed and what was left, including sandboxes this run did not create.

## Running Docker and gateway commands

The agent's bash sandbox can block the Docker socket and the gateway, even when the user's own shell works. Observed (WSL2 with Docker Desktop): `docker info` returned `permission denied` on `/var/run/docker.sock` from the agent's shell, and worked in the user's shell.

- On `permission denied` for a socket, or `Connection refused` for the gateway, try once in the sandbox, then ask the user for approval to run that command with the sandbox bypassed. Bypass only that command.
- Or the user runs it with `! <command>` and pastes the output.
- Do not `chmod`, `chown`, or `usermod` the Docker socket. Fix the Docker Desktop side; see [WSL-DOCKER-DESKTOP.md](WSL-DOCKER-DESKTOP.md).

## Gotchas

- The Docker or Podman driver is not the MicroVM boundary. Record which driver you tested. Without `/dev/kvm`, as in WSL2 without nested virtualization, Docker is the only option.
- `hard_requirement` Landlock fails closed; `best_effort` may start without filesystem rules. The trial policy uses `best_effort`.
- Effective policy includes provider-contributed rules. Inspect it, not just your own file.
- A credential placeholder hides the raw secret, but the agent can still use it at permitted endpoints. Verified: with the `openrouter` provider attached, the guest holds only a placeholder and an inference request through the gateway returns `HTTP 200`.
- `sandbox create ... -- sleep infinity` never returns. The script runs it in the background, waits for `Ready`, then ends the create process; the sandbox keeps running. Do the same by hand with `timeout`.
- The default `--tail` on `openshell logs` hangs in non-interactive shells; the script uses `--since` and `-n`.
- A stopped or failed sandbox may not restart. Observed (openshell 0.1.5): `openshell sandbox start` failed with "supervisor authentication bundle does not match runtime session", and the sandbox moved to `Error`. Deleting and recreating it worked.
- Claude Code needs Node 22 or newer. See [SANDBOX-IMAGE.md](SANDBOX-IMAGE.md).
- Docker Desktop from the Microsoft Store is a per-user install. See [WSL-DOCKER-DESKTOP.md](WSL-DOCKER-DESKTOP.md) for the hosts-file fallback.

## Files in this skill

- [PLATFORM-MACOS-LINUX.md](PLATFORM-MACOS-LINUX.md): macOS and native Linux.
- [PLATFORM-WINDOWS.md](PLATFORM-WINDOWS.md): Windows 11 routes, including WSL2.
- [WSL-DOCKER-DESKTOP.md](WSL-DOCKER-DESKTOP.md): Docker Desktop settings, hosts fallback, restart order, socket symptoms.
- [SANDBOX-IMAGE.md](SANDBOX-IMAGE.md), [Dockerfile](Dockerfile) and [Dockerfile.pi](Dockerfile.pi): the Claude Code and pi trial images (Node 22, Claude Code, git, curl).
- `smoketest.py`: entry point that automates create, checks, teardown and the record; run it as `python3 -I smoketest.py`.
- [`openshell_smoketest/`](openshell_smoketest/): the code behind it, one module per responsibility: `cli` (flow), `preflight`, `step_create`, `step_upload` (3-4), `step_pull_script` (10), `step_network` (1-2), `step_host_visibility` (5), `step_agent` (8) with `agent_task` (8e, `AgentSpec`/`AGENTS`), `step_observations`, `runner`, `teardown`, `report`, `record`, plus `process`, `helpers`, `model`, `config`.
- [`scripts/pull_openshell_changes.py`](../../../scripts/pull_openshell_changes.py): pulls the changes made in the sandbox copy into a host branch; `smoketest.py` tests it on a temp branch (check 10).
- [CHECKS.md](CHECKS.md): checks before, right after, and after the sandbox exists.
- [SMOKETEST.md](SMOKETEST.md): each check, its pass criteria, observations, verification status.
- [RECORD.md](RECORD.md): where and how to write the trial record.

## Running pi instead of claude

[pi](https://github.com/badlogic/pi-mono) (`@mariozechner/pi-coding-agent`, command `pi`, one-shot `pi -p "<prompt>"`) has its own image, [Dockerfile.pi](Dockerfile.pi) (`trial-pi:local`, see [SANDBOX-IMAGE.md](SANDBOX-IMAGE.md)). Run `smoketest.py --agent pi` (the image defaults to `trial-<agent>:local`). `--agent` selects an `AgentSpec` in `openshell_smoketest/agent_task.py` (`AGENTS`) that drives checks 8a and 8e; to support another agent, add an entry there. For pi on `openrouter`: pi reads `OPENROUTER_API_KEY` itself (the guest holds the placeholder), so no env mapping and no extra policy rule are needed (pi is a node script; the network client is `/usr/local/bin/node`, which the provider rule allows); a `models.json` override caps output tokens at 4000 (see SMOKETEST.md). Tested: `SETUP VERIFIED`. Never put a raw key in the guest.

## After setup

Tell the user the next steps: day-to-day use and permission changes are in the [OpenShell how-to](../../../docs/guides/how-to/openshell-how-to.md); a project-specific sandbox is built with `/develop-sandbox` (type OpenShell).
