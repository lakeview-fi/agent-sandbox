# Choosing an outer execution boundary for local coding agents

This guide compares **outer execution environments** for local use. Claude Code, Codex and pi are agent harnesses that can run inside these environments; their native command approvals and sandboxes are a separate, optional inner layer. This guide’s Docker Sandboxes and OpenShell recommendations concern the outer boundary, not a choice between agent harnesses.

## Outer execution options

For local development with Claude Code or Codex, two practical outer boundaries stand out:

1. **Docker Sandboxes (`sbx`)** runs a supported agent in a per-agent microVM with its own Linux kernel, filesystem, network, and private Docker Engine. It is the more turnkey local option. You can give it a live workspace, a read-only source plus private clone, or no host workspace. The live workspace is convenient; clone mode gives a clearer review and handoff point.
2. **NVIDIA OpenShell** runs an agent under a centrally managed policy. It supports Docker, Podman, Kubernetes, and MicroVM drivers, and can restrict filesystem paths, process identity, network destinations/requests, and credentials. Its strongest distinction is policy and provider management, including operator-reviewed network policy proposals (Policy Advisor, off by default). Local setup and workspace wiring require more choices.

Both are **outer sandboxes**. Claude Code’s or Codex’s built-in sandbox can optionally add a second, narrower boundary around commands it runs inside the outer environment. The inner sandbox can restrict only what the outer environment already exposes: it cannot grant access to a host path or network destination denied by Docker Sandboxes or OpenShell. If all files exposed to the agent are intended to be available, the inner filesystem sandbox may be unnecessary. Keeping network restrictions in the outer layer is still useful.

Neither product makes permitted actions harmless. An agent with write access can damage those files; one with a database credential can issue destructive SQL if it can reach the database. Use least-privilege credentials and review changes before running or merging generated scripts.

## Which should I choose?

| Choose | When |
|---|---|
| **Docker Sandboxes** | You want a ready local microVM workflow, private Docker Engine, and simple workspace modes for one developer or a small number of agents. Prefer `--clone` when you want to review and fetch changes rather than share a live working tree. |
| **NVIDIA OpenShell** | You want explicit policy administration, credential providers, detailed network rules, logs, or a runtime that can be managed across a team. Choose a local driver that is supported by your OS and configure the gateway and workspace deliberately. |

For Windows 11, Docker Sandboxes currently has a documented local installation route with Windows Hypervisor Platform. NVIDIA OpenShell’s current installation documentation describes native Windows MXC as developmental and not production-qualified; WSL2 use is described as experimental. Check the current support matrix before choosing OpenShell on Windows. Claude Code’s built-in sandbox does not run on native Windows (WSL2 only), so it cannot serve as the optional inner layer there. ([Docker installation](https://docs.docker.com/ai/sandboxes/install/), [OpenShell installation](https://docs.nvidia.com/openshell/latest/about/installation/))

## Setup and local-development workflow

1. Pick one outer sandbox and install its CLI/runtime using the linked guide below.
2. Start with least access: clone mode or mount/upload only the project you need; deny network by default or use a narrow policy; avoid host credentials and SSH forwarding unless needed.
3. Authenticate Claude Code or Codex using the supported host-side credential/provider mechanism where possible.
4. Develop inside the sandbox. Use Git branches/commits or explicit file transfer as the handoff to the host.
5. Review diffs before running generated scripts, hooks, CI, or deployment commands on the host.

## Modifying permissions during a task

Think of access as two gates:

- **Outer sandbox gate:** Docker Sandboxes or OpenShell determines which host files, guest paths, networks, and credentials are exposed.
- **Agent gate:** Claude Code or Codex controls whether the agent’s own command/tool operation is approved and can apply a narrower inner command sandbox.

An inner approval cannot override the outer gate. To make a new host file available, update the outer workspace/share or upload/clone it into the sandbox. For OpenShell, filesystem/process policy is fixed at startup, so filesystem policy changes require recreating the sandbox. For Docker Sandboxes, select the workspace mode/path at creation; changing network policy is available live through `sbx policy`.

For network access, Docker Sandboxes lets the operator add/remove policy rules during a run. OpenShell can optionally let the agent submit a narrow network rule proposal; the operator reviews it, and an approved rule hot-reloads into the running sandbox. Claude Code/Codex approval prompts may authorize a particular action, but do not assume they persistently alter the outer network policy.

When using Claude Code’s built-in sandbox inside either outer environment, `/sandbox` and permission rules can narrow shell access to already-visible paths and proxy-reachable destinations. If a needed file is visible to the guest but denied by Claude’s inner sandbox, use Claude’s approval/configuration flow if allowed by its mode and administrator policy. When using Codex, its local command sandbox and approvals are also separate: use the permission controls for the inner command boundary. Verify nested sandboxing works on the chosen image/runtime; if it conflicts with container/VM restrictions, use the outer sandbox as the enforcement layer rather than weakening it blindly.

## Detailed guides

- [Docker Sandboxes: setup and local development](../execution/docker-sandbox-local-agent-guide.md)
- [NVIDIA OpenShell: setup and local development](../execution/nvidia-openshell-local-agent-guide.md)

## Reproducible trial skills

Runnable checklists (preflight, least-access setup, smoke test, teardown) for trying each option:

- [`docker-sandbox-local-agent`](../../../.claude/skills/docker-sandbox-local-agent/SKILL.md)
- [`openshell-local-agent`](../../../.claude/skills/openshell-local-agent/SKILL.md)

## Source and version notes

These recommendations are based on the workspace comparison plus the current product setup documentation linked in the detailed guides. Installation prerequisites, agent authentication, and runtime support change; verify them for the installed versions. The E2B local-compatible project is not covered here because it is a separate third-party implementation, not one of these two primary local workflows.
