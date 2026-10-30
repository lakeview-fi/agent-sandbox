# Config file reference

The files that define a sandbox so it can be committed and recreated. Single source for the formats; the `develop-sandbox` skill and the how-tos link here. Starter versions of these files, with sensible defaults, are in `.claude/skills/develop-sandbox/<type>/templates/`. Verify against the installed tool: `sbx env --help`, `openshell sandbox create --help`. Live docs win over this file: https://docs.docker.com/ai/sandboxes/configuration/environment-files/ and https://docs.nvidia.com/openshell/latest/llms.txt .

## Layout

```
~/.sbxenv.yaml       # Docker: per-machine defaults shared by all repos (agent, shared mounts, sizing)
sbxenv.yaml          # Docker: this repo's env file, at the repo ROOT (name, workspace, env)
sandbox/
  README.md          # exact create / run / teardown commands
  DECISIONS.md       # one line per access grant, with reason; host OS and driver
  # Docker Sandboxes
  start.ps1, stop.ps1, pull.ps1, setup-in-sandbox.sh, allowed-hosts.txt   # develop-sandbox templates
  kit/kit.yaml       # descriptor (kind: workload)
  kit/kit.dockerfile # only if the stock image lacks tools
  # OpenShell
  Dockerfile         # only if the stock image lacks the agent or tools
  policy.yaml        # filesystem, landlock, process, network_policies
  boundary.yaml      # the most access you will ever accept (prover input)
  run.sh             # build, create, upload, test
```

## What to commit

| Commit | Do not commit |
|---|---|
| Everything above | Secret values, tokens, `.env` files (name them in `secrets` / providers only) |
| `.gitattributes` forcing LF on `*.sh`, Dockerfiles, kit files | `sandbox/effective.yaml` dumps (regenerate them) |
| `DECISIONS.md` | Per-machine trial records (this repo's `docs/trials/` is gitignored; keep yours local too) |

Keep the definition directory **outside** every directory the sandbox mounts or uploads, or the agent could edit what runs next. The exception is Docker's repo `sbxenv.yaml` at the root of a direct-mounted workspace: sbx mounts it read-only. A file in a subfolder of a mount could be swapped by renaming the folder. With a direct mount, the scripts in `sandbox/` are writable by the agent; review their diff before you run them again. Docker mounts the env file read-only by default; do not set `sandboxOptions.writableEnvFiles` unless you trust the agent with it. Review the diff of `sandbox/` before every rebuild.

## Docker Sandboxes

### `~/.sbxenv.yaml` and `sbxenv.yaml`

Two files, merged by `sbx env create|plan|run` when it gets **no PATH** (run it from the repo root). The repo file wins; lists such as `additionalWorkspaces` concatenate. Templates: `develop-sandbox/docker/templates/global-sbxenv.yaml` and `sbxenv.yaml`.

```yaml
# ~/.sbxenv.yaml: one per machine, shared by every repo. Cannot set `name`.
schemaVersion: "1"
agent: claude                 # or codex
additionalWorkspaces:         # ALWAYS mounted directly, even in clone mode; default to readOnly: true
  - { path: C:\Users\me\agents, readOnly: true }
env: { SBX_AGENTS_DIR: /c/Users/me/agents }
sandboxOptions: { cpus: 4, memory: 8g }
```

```yaml
# <repo>/sbxenv.yaml: at the repo root (sbx mounts it read-only there)
schemaVersion: "1"
name: myproj-sbx
workspace: .                  # direct mount; `sbx env create --clone` for a private clone
kits: [./sandbox/kit]         # optional; local paths, OCI refs, git+https allowed
env: { UV_PROJECT_ENVIRONMENT: /home/agent/.venvs/myproj }
```

Clone mode protects only `workspace`. A writable `additionalWorkspaces` entry is live host write access. `sbxenv.yaml` is edited by hand (no `sbx` command writes it) and is read from the given directory (default: the current one); `~/.sbxenv.yaml` is a per-user defaults file used only when no path is passed. Edits apply when the sandbox is created, so recreate to apply them.

Credentials use `secrets` (`ref:` or `command:`, never `value:`) with `bindings.<service>.apiKey.domains`, so a secret reaches only named hosts. Host commands in `command:` run with your permissions: use absolute paths outside writable mounts. Several files can be layered (`sbx env create base.yaml override.yaml`; later wins, lists concatenate), and `${{ env.args.NAME }}` takes values from `--env-arg`.

### `kit/kit.yaml`

```yaml
# syntax=docker/sandbox-kit:3
schemaVersion: "3"
kind: workload
capabilities:
  - type: com.docker.sandbox/sbx@1
  - type: com.docker.sandbox/network-policy@1
    config: { runtime: { allow: [registry.npmjs.org] } }
  - type: com.docker.sandbox/agent-context@2     # persona / extra instructions
    config: { content: "You are the reviewer persona. Never push to main." }
```

The `network-policy` list is the committed, reviewable home for allowed hosts. A mixin-only change (extra tools, hosts, instructions) uses `kind: mixin` with `--kit`. Built-in names such as `claude` select older v2 kits that do not take v3 mixins: use a v3 workload. Kits need `sbx` v0.45 or later.

### `kit/kit.dockerfile`

Contract for your own base image: `curl`, `git`, CA certificates, `/bin/sh` and `/bin/bash`; non-root user `agent` (UID 1000, home `/home/agent`); `USER agent`; `ENTRYPOINT`/`CMD` launches the agent; install packages as root, then switch to `agent`. To extend an official image use `FROM docker/sandbox-templates:<agent>` (confirm the tag in the Agents docs).

### Persona

Either `agent-context@2` content, or files in the project (for example `.claude/agents/`, `AGENTS.md`) that the workspace already provides. Ask the agent to state its instructions to prove it sees them.

## OpenShell

### `policy.yaml` (schema version 1; unknown fields are rejected)

```yaml
version: 1
filesystem_policy:
  include_workdir: false       # true makes the prover return "unsupported" (unresolved image workdir); list paths explicitly
  read_only: [/usr, /lib, /etc, /bin, /opt, /proc]   # /opt if a toolchain lives there
  read_write: [/tmp, /sandbox, /sandbox/src, /home/sandbox]   # /sandbox: upload extraction creates /sandbox/src inside it
landlock: { compatibility: hard_requirement }   # fail closed if Landlock cannot apply
process: { run_as_user: sandbox, run_as_group: sandbox }
network_policies:
  npm_registry:
    endpoints:
      - { host: registry.npmjs.org, port: 443, protocol: rest, enforcement: enforce, access: read-only }
    binaries: [{ path: /usr/bin/npm }]
```

- Unlisted paths are inaccessible, including for the upload. A path the upload creates or writes needs write access; a parent it only traverses needs read access.
- Filesystem, landlock and process apply at start only (recreate to change). Network policy hot-reloads.
- `enforcement` defaults to `audit` (log only). Set `enforce`.
- Start from the default policy and narrow it (Default Policy docs). Keep OpenShell's baseline paths when editing a full policy.
- The gateway adds defaults to the effective policy (`/var/log`, `/dev/urandom`, `/dev/null`) and provider rules. Inspect with `openshell policy get <name> --full`.

### `boundary.yaml`

A policy in the same format as `policy.yaml`, written by the operator: the most access you would ever accept. `openshell-prover check effective.yaml --boundary boundary.yaml` passes only when the effective policy is within it. List the gateway defaults above in it, or the prover reports `exceeds_boundary`. A pass shows containment, not minimality or enforcement: still run the negative tests.

### `Dockerfile`

`--from` does not build Dockerfiles. Build and tag with the gateway's container engine, then reference the image; a remote gateway needs a pushed image. The image must contain the agent CLI and every tool the task needs. Persona files (`.claude/agents/`, `CLAUDE.md`, `AGENTS.md`) go in the image or the upload, at a path the policy exposes.

Traps seen in practice:
- A base image may already own UID 1000 (the `node` images do). Pick another UID for the workload user.
- The build runs as root and bakes in whatever it writes under the `ENV` paths (for example a uv cache under `/tmp`). Delete those in the same `RUN`, or the sandbox user cannot write them.
- Interpreters installed at build time (for example under `/opt`) must be world-readable (`chmod -R a+rX`), and their directory must be in `read_only`.
- Build-time network is not governed by the sandbox policy; runtime network is.

### `run.sh`

Plain, reproducible commands: `docker build`, `openshell sandbox create --policy ... --upload ...`, the acceptance `exec`, `policy get`, `openshell-prover check`, `sandbox delete`. Write it for Linux or WSL2.
