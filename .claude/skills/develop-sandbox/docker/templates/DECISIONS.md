# Decisions: <project> Docker Sandbox

Each access grant and each deviation from the method, with its reason. Unrecorded access does not ship.

## Environment

- Host: <OS and version>. `sbx` <version>. Network default: <balanced / deny-all> (`sbx policy init`).

## Scope

- Project: <repo>, <language and toolchain>.
- Purpose: <coding, unless stated otherwise, and why>.
- Sandboxed agent: Claude Code, built-in `claude` agent <or the project kit, and why>.
- Workspace: <direct mount, read-write (default: the agent's edits and commits land in the host repo) / clone mode with `start.ps1 -Clone` (adds a `sandbox-<name>` remote to the host repo; commits come back with `pull.ps1`)>, chosen by the user.
- Location of `sbxenv.yaml`: <repo root, which sbx mounts read-only in direct mode>.
- Acceptance task (confirmed by the user): see `TASK.md`.

## Mounts

| Path | Mode | Reason |
|---|---|---|
| `..` | read-only | the project |

## Credential (agent)

- Claude subscription login held by the sbx proxy (`auth login --claudeai`, global scope). The guest sees only `proxy-managed` sentinels. Any sandbox on this machine can use the subscription through the proxy while it runs.
- Not used: `claude setup-token`, an `anthropic` API-key secret, or any token in the sandbox environment.

## Network

| Host | Where granted | Reason |
|---|---|---|
| `api.anthropic.com`, `platform.claude.com` | <balanced default / kit> | Claude Code and its OAuth token endpoint |
| <host> | <kit / `sbx policy allow --sandbox`> | <reason> |

## Deviations from the method

- <one bullet per deviation, with the reason>

## Pending (user decisions)

- <open decisions, including any `ADAPT:` marker still in the files>

## Safety checks

- Effective policy (`sbx policy ls <name>`): <result>.
- Negative tests: <results>.
- Acceptance task by the agent: <result, quoted from the agent's reply>.
