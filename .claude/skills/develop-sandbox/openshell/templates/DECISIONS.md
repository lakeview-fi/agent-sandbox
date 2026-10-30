# Decisions: <project> OpenShell sandbox

Each access grant and each deviation from the method, with its reason. Unrecorded access does not ship.

## Environment

- Host: <OS and version; WSL2 kernel on Windows>.
- Container runtime: <Docker Desktop / Docker Engine / Podman, version>.
- OpenShell CLI <version>; gateway <name> at <endpoint>. Compute driver: <MicroVM / Docker / Podman>. A Docker or Podman driver is a container with a shared kernel, not a VM.

## Scope

- Project: <repo>, <language and toolchain>. Git HEAD <sha>; the upload is the working tree as it stands, including uncommitted changes.
- Purpose: <coding, unless stated otherwise, and why>.
- Sandboxed agent: Claude Code <version> (installed in the image).
- Git remote: none. The sandbox works on an uploaded copy; `run.sh baseline` commits it inside the sandbox. Results come back with `openshell sandbox download`.
- Acceptance task (confirmed by the user): see `TASK.md`.

## Uploaded and writable paths

- Upload: staged copy of the tracked and untracked, not git-ignored, regular files at `/sandbox/src` (<n> files, <size>). A copy, not a mount: the host repo is not reachable.
- Excluded: `sandbox/` (the definition stays on the host), `.claude/` (host agent config), `.git`, git-ignored files, and `<STAGE_EXCLUDE paths, with reasons>`.
- Writable: `/sandbox/src`, `/tmp`, and two widenings:
  - `/sandbox`: the upload extraction creates `/sandbox/src` inside it. The agent can add entries next to `src`.
  - `/home/sandbox`: Claude Code writes its config, state and subscription login under `$HOME`.
- Read-only: `/usr`, `/lib`, `/etc`, `/bin`, `/opt`, `/proc`. The gateway adds `/var/log`, `/dev/urandom` and `/dev/null`; `boundary.yaml` lists them.

## Credential (agent)

- Claude subscription login inside the sandbox (`run.sh login`, run by the user in their own terminal). The OAuth tokens live in `/home/sandbox/.claude/.credentials.json` inside the sandbox. The agent can read them; deleting the sandbox discards them. They are a separate login from the host's.
- Not used: `claude setup-token` or any token in the sandbox environment.

## Network

Deny by default. Each rule is scoped to one binary.

| Rule | Endpoint | Access | Binary | Reason |
|---|---|---|---|---|
| `anthropic_api` | `api.anthropic.com:443` | read-write | `/usr/local/bin/node` | Claude Code model API (POST) |
| `anthropic_api` | `platform.claude.com:443` | read-write | `/usr/local/bin/node` | OAuth token exchange and refresh for the subscription login |
| `pypi` | `pypi.org:443`, `files.pythonhosted.org:443` | read-only | `/usr/local/bin/uv` | `uv sync --frozen` |

- Not granted: any Git host, any OS package mirror, any other host.
- Unverified: that `read-only` blocks writes on allowed hosts. GET query strings to allowed hosts could still carry data out.

## Deviations from the method

- <one bullet per deviation, with the reason>

## Pending (user decisions)

- <open decisions, including any `ADAPT:` marker still in the files>

## Safety checks

- `openshell-prover check sandbox/policy.yaml --boundary sandbox/boundary.yaml`: <result>. Discrimination check with an out-of-boundary candidate: <result>.
- Effective policy (`run.sh safety`): <result>.
- Negative tests (`run.sh negative`): <results>.
- Acceptance task by the agent (`run.sh agent`): <result, quoted from the agent's reply>.

## Records

- Sandbox name: <name>. Other sandboxes on this gateway were not touched.
