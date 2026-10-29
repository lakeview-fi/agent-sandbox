---
name: develop-docker-sandbox
description: Develop, test and harden an application-specific Docker Sandbox (sbx) for a project: write the kit Dockerfile and sbxenv.yaml, set mounts, network policy and persona, run the user's agent on a representative task, and iterate until the sandbox is safe and capable. Use when the user wants a project sandbox built or tuned for Docker Sandboxes, sbx, sbxenv.yaml or an sbx kit, or wants an agent's sandbox permissions debugged.
---

# Develop a Docker Sandbox for a project

Method (inputs, loop, safety and capability review, deliverables): [developing-an-app-sandbox.md](../../../docs/guides/developing-an-app-sandbox.md). **Read it first**; this file only adds Docker specifics. Prerequisite: `setup-smoketest-docker-sandbox` passed on this machine. Docs: https://docs.docker.com/ai/sandboxes/ . Kits need `sbx` v0.45 or later; verify flags with `sbx <cmd> --help` and trust live docs over this file.

## Ground rules

- Ask before installing, logging in, or any step that widens access to credentials, host-write paths or broad egress.
- Default definition directory is `sandbox/`. Create files there unless the user names another path.
- `sbxenv.yaml` must live **outside** every directory it mounts (including `additionalWorkspaces`). If `sandbox/` sits inside the project being mounted, mount a subdirectory or keep the env file one level up, and tell the user why.

Host-specific traps (Windows, macOS, Linux): read [PLATFORM-NOTES.md](PLATFORM-NOTES.md) before drafting files.

## Artifacts

```
sandbox/
  sbxenv.yaml          # agent, kits, workspaces, env, bindings, sandboxOptions
  kit/
    kit.yaml           # descriptor (kind: workload)
    kit.dockerfile     # only if the stock image lacks tools
  DECISIONS.md  README.md
```

### `sbxenv.yaml` (fields from the environment-file reference)

```yaml
schemaVersion: "1"
name: myproj-sbx
agent: claude                 # or codex, or a kit reference
workspace: { path: .., clone: true }   # clone = host repo read-only, agent edits a private copy
additionalWorkspaces:
  - { path: ../reference-docs, readOnly: true }
kits: [./kit]                 # local paths, OCI refs, git+https allowed
env: { NODE_ENV: test }
sandboxOptions: { cpus: 4, memory: 8g }
```

Credentials: use `secrets` (`ref:` or `command:`, never `value:`) with `bindings.<service>.apiKey.domains` so the secret reaches only named hosts. The user supplies them.

### Kit descriptor (`kit/kit.yaml`)

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

Dockerfile contract for your own base image: `curl`, `git`, CA certificates, `/bin/sh` and `/bin/bash`; non-root user `agent` (UID 1000, home `/home/agent`); `USER agent`; `ENTRYPOINT`/`CMD` launches the agent; install packages as root, then switch to `agent`. To extend an official agent image use `FROM docker/sandbox-templates:<agent>` (confirm the tag in the Agents docs) with `USER agent` and the launch command. A mixin-only change (extra tools, hosts, instructions) uses `kind: mixin` with `--kit`. Built-in names such as `claude` select older v2 kits, which do not take v3 mixins: use a v3 workload.

Persona alternatives: `agent-context@2` content, or files in the project (for example `.claude/agents/` or `AGENTS.md`) that the workspace mount already provides. Prove the agent sees it.

## Workflow

Follow the method's loop. Docker commands:

```sh
sbx env plan  sandbox/            # dry run: shows what would be created
sbx env create sandbox/ --name myproj-test
sbx env exec  --name myproj-test -- <agent non-interactive command> "<acceptance task>"
sbx policy ls ; sbx policy log    # network decisions (network only)
sbx env rm    --name myproj-test  # recreate from files to prove reproducibility
```

If `sbx env` does not accept the directory form, check `sbx env --help`. Check the non-interactive flag of the user's agent with `<agent> --help` (for example `claude -p`, `codex exec`). Docker launches agents with their own permission prompts bypassed, so the microVM, mounts and network policy are the safety boundary: the safety review is mandatory.

## Triage notes

- Network denied: add the host to the kit's `network-policy` allow list (persistent, reviewable) rather than ad hoc `sbx policy allow`; an org policy may still deny it.
- Balanced and Locked Down profiles hold unmatched requests for developer approval; the user approves with `sbx policy approval`, the agent retries. Record approved hosts in `DECISIONS.md`.
- Path not visible: add an `additionalWorkspaces` entry, read-only first. Mount changes need a recreated sandbox.
- Negative tests (required): unlisted host blocked; `~` and other host paths not visible; write to a read-only workspace fails.

Finish with the deliverables listed in the method doc.
