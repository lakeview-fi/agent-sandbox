# Docker Sandboxes (`sbx`) how-to

Commands checked against `sbx` v0.50 (`sbx <cmd> --help`). `sbx env` is experimental. Install and first run: `setup-smoketest-docker-sandbox` skill. File syntax: [config file reference](config-file-reference.md).

## 1. One-time network default

```sh
sbx policy init balanced     # or deny-all (least access) / allow-all
```

`deny-all` blocks everything until you allow it. `balanced` allows typical dev traffic (AI services, package registries). Init runs once; `sbx policy reset` starts over.

## 2. Start a session

**From committed definitions (recommended for a project).** The `develop-sandbox` templates use two env files:
- The global `~/.sbxenv.yaml` holds what all your repos share: agent, tool-data and agent mounts, sizing.
- The repo-root `sbxenv.yaml` holds the name, the workspace and the venv path.

`sbx` merges them only when you pass **no PATH**, so run it from the repo root:

```sh
cd path/to/repo
sbx env plan                                  # dry run: shows both files, mounts, env
sbx env create --force                        # provision (add --clone for clone mode)
sbx env run                                   # attach to the agent
```

The template's `sandbox/start.ps1` wraps this. It also applies `sandbox/allowed-hosts.txt` (env files have no network field) and runs the in-sandbox setup. `sandbox/stop.ps1` ends a session.

With explicit paths (`sbx env create sandbox/`), `~/.sbxenv.yaml` is skipped. Pass `--name` to every `sbx env` command, or set `name:` in the repo file; the global file cannot set it. The default name is `<agent>-<directory>`.

Where the env file may live: outside every mounted directory, or at the root of a direct-mounted workspace, which sbx mounts read-only. Not in a subfolder of a mount: the agent could swap it by renaming the folder.

**Ad hoc, without a file:**

```sh
sbx run --clone --name myproj claude .        # host repo read-only, agent edits a private clone
sbx run --name myproj claude .                # direct mount: agent edits the host working tree
sbx run --name myproj claude . ../docs:ro     # extra read-only workspace (":ro")
sbx create --name scratch claude              # no workspace; agent works inside the sandbox
```

Clone mode adds a `sandbox-<name>` git remote to the host repository. Prefer `:ro` mounts when you do not want that.

> **Clone mode protects only the first (primary) workspace.** Every extra path is mounted directly, and is writable unless you add `:ro` (or `readOnly: true`). `sbx run --clone claude . ~/notes` leaves `~/notes` fully writable by the agent. Add `:ro` to every extra path, and make a path writable only on purpose, one directory at a time. Details: [file sharing analysis](../../analysis/synthesis/host-guest-file-sharing-and-version-control.md#4-scenario-files-and-folders-scattered-over-the-host).

## 3. Work in the session

```sh
sbx ls                                        # list sandboxes
sbx run --name myproj                         # re-attach (agent is read from the sandbox spec)
sbx exec -it myproj bash                      # shell inside
sbx exec myproj -- claude -p "run the tests"  # one-off non-interactive agent run
sbx stop myproj                               # keeps state; `sbx run --name myproj` restarts it
```

Docker starts agents with their own permission prompts off. The microVM, mounts and network policy are the boundary, so keep them tight.

## 4. Change permissions

Scope of `sbx policy allow`: **global by default**, so add `--sandbox <name>` unless you mean every sandbox.

| Need | Command | Applies |
|---|---|---|
| See current rules | `sbx policy ls [myproj]`, `--wide` for rule IDs | n/a |
| See what was blocked | `sbx policy log myproj` | n/a |
| Test a host without running anything | `sbx policy check network <host>` | n/a |
| Allow a host | `sbx policy allow network --sandbox myproj registry.npmjs.org` | Immediately |
| Allow only some requests | add `--method GET,HEAD --path '/v1/**'` | Immediately |
| Block a host | `sbx policy deny network --sandbox myproj ads.example.com` | Immediately |
| Remove a rule | `sbx policy rm network --id <RULE_ID>` | Immediately |
| Answer a held request (Balanced / Locked Down) | `sbx policy approval ls`, then `sbx policy approval respond ...` | Immediately |
| Add or change a mount | edit `additionalWorkspaces` in `sbxenv.yaml`, recreate | Recreate |
| Add or change a credential | `sbx secret set ...` in your own shell, recreate | Recreate |

Prefer exact hosts over wildcards. Avoid `**` (allow all hosts).

## 5. Make a live change permanent

**How the definition files change.** No `sbx` command edits `sbxenv.yaml`: you edit it in an editor (`sbx env` has `create`, `exec`, `plan`, `rm` and `run`, and none of them writes the file). The same is true of `~/.sbxenv.yaml`, which supplies defaults only when you pass no path. Editing a file does **not** change a running sandbox. Mounts, secrets, bindings and kits are applied when the sandbox is created: `sbx env run` on an existing sandbox starts and re-attaches it without re-provisioning. To apply an edit, preview it with `sbx env plan` from the repo root, then recreate (`sandbox/start.ps1 -Recreate`, or `sbx env rm` and `sbx env create`). Only network rules added with `sbx policy allow/deny` take effect immediately.

Rules added with `sbx policy allow` live in the local policy store, not in your repository. To keep a rule with the project, add the host to the kit's `network-policy` capability in `sandbox/kit/kit.yaml`, then recreate and confirm:

```sh
cd path/to/repo                               # no PATH below, so ~/.sbxenv.yaml is merged in
sbx env rm --name myproj                      # also deletes secrets scoped to this sandbox
sbx env create
sbx policy ls myproj                          # the rule appears, from the kit
```

Add a line to `sandbox/DECISIONS.md` for each widening.

`sbx` has no export or import for local rules, so the kit is the only way to share hosts through git. The per-machine `sbx policy init` choice is not shared: state it in `sandbox/README.md`. Background: [sharing policy through version control](../../analysis/execution/docker-agent-sandbox.md#sharing-policy-with-a-team-through-version-control).

## 6. Get results out, and git workflows

Pick the workflow when you create the sandbox. It cannot be changed afterwards (clone mode is fixed at creation).

| Workflow | Where the agent works | Who commits | How changes reach your repo |
|---|---|---|---|
| **Direct mount** (`sbx run claude .`) | Your real working tree | You (the agent can too, so agree who) | Already there. Review with `git diff`, then `git add -p`, `git commit`, `git push` |
| **Clone** (`--clone`) | A private copy inside the VM; your repo is read-only at `/run/sandbox/source` | The agent commits in its copy | `git fetch sandbox-myproj`, then review and merge or push |
| **Mountless** (`sbx create` with no path) | Files inside the VM only | The agent, after cloning from a remote | The agent pushes to a remote; or `sbx cp` |

The `develop-sandbox` templates default to **direct mount** and offer clone with `start.ps1 -Clone`. Direct mount on a Windows host, verified 2026-10-30 with `sbx` v0.50.1:
- The repo appears at the same path (`/c/Users/...`), and git sees the same status as the host (no line-ending noise). `.git/config`, including `core.hooksPath`, is shared, and the mount shows the hooks as executable.
- The sandbox does not see your global or system git config. Set identity and `core.autocrlf=input` in the sandbox user's `~/.gitconfig`, never in the repo's `.git/config`.
- The host's Windows `.venv` is in the mount. Set `UV_PROJECT_ENVIRONMENT` to a path in the sandbox home, or `uv sync` replaces it. Tests ran noticeably slower on the mount than on a clone's local disk (about 2x in one project).
- Do not run git on the host while the agent commits (shared index and locks).

Clone workflow, step by step. [`scripts/pull_docker_commits.py`](../../../scripts/pull_docker_commits.py) does the fetch and review for you:

```sh
git checkout -b feat/x                            # host: branch you will review against
sbx run --clone --name myproj claude .            # tell the agent to create its own branch before editing
python scripts/pull_docker_commits.py myproj --repo .            # fetch, show commits and files to review, create branch agent/myproj/<branch>
git log --stat HEAD..agent/myproj/feat/y                         # review further with git
git merge --ff-only agent/myproj/feat/y                          # or rerun the script with --merge; or push that branch to origin
```

The script finds the one sandbox branch with commits your HEAD lacks (`--branch` to choose), never touches your working tree unless you pass `--merge` (fast-forward only, git hooks disabled), and lists CI, build, hook and `sandbox/` files the commits changed. Options and exit codes: [scripts/README.md](../../../scripts/README.md). By hand, the same is `git fetch sandbox-myproj` followed by `git log` and `git diff main..sandbox-myproj/<branch>`.

- No branch is created for the agent automatically, and the clone starts from the ref your host has checked out.
- The `sandbox-<name>` remote works only while the sandbox runs. After `sbx stop`, fetch fails until you start it again.
- `sbx rm` deletes the clone and the remote. **Fetch or push first.**
- Clone mode must be started from the main checkout, not from another git worktree. Mounting a host worktree gives the agent files but no git.
- For parallel tasks, ask the agent to create one worktree per task inside the clone.
- If the agent should push itself, it needs a network rule for the git host and a credential. SSH agent forwarding is on when `SSH_AUTH_SOCK` is set and exposes every key in that agent: decide that on purpose.

Other ways out: `sbx cp myproj:/path/out.log ./` (absolute sandbox path; one direction per call). Always review generated scripts, hooks (`ls -la .git/hooks/`), CI and build files before running them on the host; a direct mount lets the agent rewrite them.

## 7. Stop and delete

```sh
sbx stop myproj
sbx rm myproj                                 # ad hoc sandboxes
sbx env rm --name myproj                      # file-defined, from the repo root; add --prune-bindings to drop its credential bindings
```

A stopped sandbox keeps its disk: installed tools, the agent's `~/.claude` state, and a clone with its commits. It survives host reboots (verified with `sbx` v0.50.1: sandboxes were still listed after a host reboot, and a clone's commit survived stop and start). Closing the computer has the same effect as `sbx stop`. Only `sbx rm` deletes it. So stopping at the end of a session is enough; remove it when you want a fresh one. In clone mode, pull first. The template's `stop.ps1` pulls and then stops, and `stop.ps1 -Remove` pulls and then removes.

## 8. Credentials

The user runs these in their own shell; an agent must not read the values. `sbx secret set <service>` (global) or `--sandbox <name>` (deleted with the sandbox). Check with `sbx secret ls`. For Claude Code with a subscription, log in inside the sandbox. Full procedure and trade-offs: [develop-sandbox/docker/CREDENTIALS.md](../../../.claude/skills/develop-sandbox/docker/CREDENTIALS.md).

## 9. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Download or API call fails | Host not allowed | `sbx policy log myproj`, then allow the narrowest host (section 4), then persist (section 5) |
| Rule works in one sandbox, not another | Rule was scoped with `--sandbox` | Add it to the kit, or scope it again |
| Path not visible in the sandbox | Not mounted | Add `additionalWorkspaces` (read-only first), recreate |
| Agent edited a folder you thought was protected | Clone mode protects only the primary workspace | Add `:ro` / `readOnly: true` to every extra path |
| `git fetch sandbox-myproj` fails | Sandbox is stopped or removed | `sbx run --name myproj`, then fetch again |
| Agent lost its login after recreate | Sandbox-scoped secret was deleted | Re-enter it, or use a global secret (user decides) |
| Script fails with `\r` or `bad interpreter` | CRLF line endings from Windows | `.gitattributes`: `*.sh text eol=lf`, same for kit files |
| `sbx env` rejects the directory form | CLI version differs | `sbx env --help`; pass the file path instead |
| Permission errors on a mounted file | Host and sandbox user differ | Check ownership before widening policy |
| SQLite `disk I/O error` or `database is locked` on a mounted DB | Writers in two VMs, or a VM and the host: locks do not cross the VM boundary | One writer side at a time; long term, a single-writer service on the host |
| `uv sync` in the sandbox breaks the host's `.venv` | Direct mount shares the venv folder | Set `UV_PROJECT_ENVIRONMENT` to a path in the sandbox home |
| `pull_docker_commits.py`: no git remote `sandbox-<name>` | Sandbox runs in direct mode (nothing to pull), or the remote is gone | `sbx inspect <name>`: `Clone source: -` means direct; pulled commits stay under `refs/sandboxes/<name>/*` |
| `sbx exec` warns "runs on an in-container clone" in direct mode | Stale record from a same-name clone sandbox | Check `mount` inside; harmless |
| Unsure what is wrong | | `sbx diagnose` |
