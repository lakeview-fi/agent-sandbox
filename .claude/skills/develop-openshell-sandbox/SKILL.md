---
name: develop-openshell-sandbox
description: Develop, test and harden an application-specific NVIDIA OpenShell sandbox for a project: build the sandbox image, write the policy.yaml (filesystem, process, network), set up providers and uploads, run the user's agent on a representative task, verify the policy with openshell-prover, and iterate until the sandbox is safe and capable. Use when the user wants a project sandbox built or tuned for OpenShell, an OpenShell policy written or debugged, or an agent's sandbox permissions tightened.
---

# Develop an OpenShell sandbox for a project

Method (inputs, loop, safety and capability review, deliverables): [developing-an-app-sandbox.md](../../../docs/guides/developing-an-app-sandbox.md). **Read it first**; this file only adds OpenShell specifics. Prerequisite: `setup-smoketest-openshell` passed on this machine. Docs index: https://docs.nvidia.com/openshell/latest/llms.txt . Verify flags with `openshell <cmd> --help`; trust live docs over this file.

## Ground rules

- Ask before installing, creating providers, or any step that widens access to credentials, host-write paths or broad egress.
- Default definition directory is `sandbox/`. Create files there unless the user names another path.
- Copy the project in with `--upload`; do not host-bind-mount (disabled by default on the Docker driver, and it bypasses isolation). Uploaded copies keep the host `sandbox/` files out of the agent's reach.
- The user creates provider credentials (`openshell provider create ... --from-existing` reads an env var); never read or print them.

Host-specific traps (Windows via WSL2, macOS, Linux): read [PLATFORM-NOTES.md](PLATFORM-NOTES.md) before drafting files.

## Artifacts

```
sandbox/
  Dockerfile          # only if the stock image lacks the agent or tools
  policy.yaml         # filesystem, landlock, process, network_policies
  boundary.yaml       # the most access you are willing to allow
  run.sh              # build, create, upload, test: exact reproducible commands
  DECISIONS.md  README.md
```

### Image

`--from` does not build Dockerfiles. Build first, then reference the image; a remote gateway needs a pushed image:

```sh
docker build -t myproj-sbx:dev sandbox/        # or: podman build -t localhost/myproj-sbx:dev
```

The image must contain the agent CLI and every tool the task needs. Persona or custom-agent files (for example `.claude/agents/`, `CLAUDE.md`, `AGENTS.md`) go in the image or the upload, at a path the policy exposes.

### `policy.yaml` (schema version 1; unknown fields are rejected)

```yaml
version: 1
filesystem_policy:
  include_workdir: true
  read_only: [/usr, /lib, /etc, /sandbox/reference]
  read_write: [/tmp, /sandbox/src]
landlock: { compatibility: hard_requirement }   # fail closed if Landlock cannot apply
process: { run_as_user: sandbox, run_as_group: sandbox }
network_policies:
  npm_registry:
    endpoints:
      - { host: registry.npmjs.org, port: 443, protocol: rest, enforcement: enforce, access: read-only }
    binaries: [{ path: /usr/bin/npm }]
```

Unlisted paths are inaccessible. Filesystem, landlock and process settings apply at startup only (recreate to change); network policy hot-reloads. Start from the default policy and narrow it (see Default Policy docs). `enforcement` defaults to `audit`: set `enforce`.

## Workflow

Follow the method's loop. OpenShell commands:

```sh
openshell sandbox create --name myproj-test --from myproj-sbx:dev \
  --policy sandbox/policy.yaml --provider <name> --upload ./:/sandbox/src   # no trailing command with --upload
openshell sandbox exec -n myproj-test -- <agent non-interactive command> "<acceptance task>"
openshell logs myproj-test --since 10m --source sandbox       # denials
openshell policy get myproj-test --full                       # effective policy incl. provider rules
openshell sandbox delete myproj-test                          # recreate from files to prove reproducibility
```

Check the agent's non-interactive flag with `<agent> --help` (for example `claude -p`, `codex exec`).

## Triage notes

- Network denied: either `openshell policy update myproj-test --rule-name X --binary P --add-endpoint host:443:read-only:rest:enforce --wait` to try it live, or review a Policy Advisor proposal (`openshell rule get myproj-test --status pending`, then approve or reject). Then **copy the rule into `policy.yaml`**: live edits are lost on recreate.
- Filesystem denial: edit `policy.yaml` and recreate the sandbox.
- Safety gate (required): save the effective policy and compare it with the boundary:

```sh
openshell sandbox get myproj-test --policy-only > sandbox/effective.yaml
openshell-prover check sandbox/effective.yaml --boundary sandbox/boundary.yaml   # only within_boundary passes
```

A pass does not prove the policy is minimal or enforced; still run the negative tests: unlisted host blocked, host paths not visible, write to a read-only path fails.

Finish with the deliverables listed in the method doc.
