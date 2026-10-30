# Docker Sandbox for this project

Runs Claude Code on this project in a Docker Sandbox (`sbx`, a microVM). Access grants and their reasons are in [DECISIONS.md](DECISIONS.md).

| File | Purpose |
|---|---|
| `../sbxenv.yaml` | This repo's sandbox: name, workspace, venv path. Merged with the global `~/.sbxenv.yaml` |
| `start.ps1` | Create the sandbox if needed, then start Claude Code (interactive or `-Prompt`) |
| `stop.ps1` | End of session: pull (clone mode) and stop; `-Remove` deletes the sandbox |
| `pull.ps1` | Clone mode only: pull the agent's commits into a local branch; `-Merge` fast-forwards (calls the agent-sandbox repo's `scripts/pull_docker_commits.py`) |
| `setup-in-sandbox.sh` | Runs inside after create: tools, agents, git identity, deps |
| `allowed-hosts.txt` | Network hosts beyond the Claude hosts |
| `watch-policy.ps1` | Background watcher (started by `start.ps1`): appends allowed and blocked network requests to `%LOCALAPPDATA%\sbx-policy-logs\<name>.jsonl` |
| `TASK.md` | Acceptance task for the sandboxed agent |
| `DECISIONS.md` | Access grants, findings, open points |

On Windows, run these from PowerShell (`sbx` is a Windows binary). The scripts are verified on Windows only; macOS and Linux (`pwsh`) are untested.

## One-time per machine

1. **Claude subscription login**, held by the sbx proxy on the host. The sandbox sees placeholders only.

   ```powershell
   sbx secret ls        # must show: (global) service anthropic (oauth configured)
   ```

   If it is missing: `sbx create --name claude-login claude`, then `sbx run --name claude-login -- auth login --claudeai`, then `sbx rm claude-login`. Do not use `claude setup-token`, and do not store an `anthropic` API-key secret.

2. **Global defaults** in `~/.sbxenv.yaml` (agent, shared mounts, sizing).

## Develop

```powershell
.\sandbox\start.ps1              # first run creates and sets up, then opens Claude Code
.\sandbox\stop.ps1               # end of session
```

Other options: `-Prompt "..."` for a non-interactive run, `-Agent <name>` for a custom agent, `-Resetup -SetupOnly` to refresh tools and agents, `-Recreate` for a fresh sandbox, and `stop.ps1 -Remove` to delete it.

## Two modes

| | Direct mount (default) | Clone (`start.ps1 -Clone -Recreate`) |
|---|---|---|
| Where the agent works | This working tree and `.git`, live | A private clone inside the sandbox |
| Your uncommitted work | Visible to the agent, and it can change it | Not in the clone, but readable through `/run/sandbox/source` |
| Getting results | Nothing to do: commits are on your branch | `pull.ps1` creates branch `agent/<name>/<branch>`; `pull.ps1 -Merge` fast-forwards |
| Risk | The agent can change files that run on the host later: `sandbox/*.ps1`, hooks, build files, `.git/config`. Review `git diff` and `git log` before running them | Changes reach you only as commits you review. `pull.ps1` turns off hooks and lists risky files |
| Don't | Run git on the host while the agent commits | `sbx rm` before pulling |

`sbxenv.yaml` is mounted read-only, so the agent cannot change what the next start creates.

## Things to know

- A stopped sandbox keeps its disk across restarts and reboots, including a clone's commits. Shutting down the computer is the same as stopping. Only `sbx rm` (or `stop.ps1 -Remove`, `start.ps1 -Recreate`) deletes it, and the scripts pull first in clone mode.
- Blocked hosts show in `sbx policy log <name>`. Add them to `allowed-hosts.txt` with a line in DECISIONS.md.
- **Network log file:** `start.ps1` starts `watch-policy.ps1` in the background (skip with `-NoWatch`). It polls `sbx policy log --json` every 5 s and writes one JSON line per host whose request count grew: `decision` (allowed or blocked), `host`, `new_requests`, `total`, `rule`, `reason`. On startup, requests made before the watcher ran get `"baseline": true`. Follow it with `Get-Content -Wait "$env:LOCALAPPDATA\sbx-policy-logs\<name>.jsonl"`. The file is outside the repo, so the agent cannot change it in direct mode. Limits come from sbx: one aggregate entry per host (no paths or methods), and no filesystem denials. The watcher exits when the sandbox is removed, and only one runs per sandbox.
- Claude Code runs with its permission prompts bypassed (sbx default). The microVM, the mounts and the network allow list are the boundary.
