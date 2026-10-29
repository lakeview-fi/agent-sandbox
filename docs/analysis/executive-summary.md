# Executive summary: sandboxing coding agents

As of October 29, 2026. This summarizes the other analyses in `docs/analysis/` and inherits their limits: it is based on vendor documentation, not hands-on testing, and defaults change between versions. Pin versions and test before relying on any claim.

## The core idea

Two layers, chosen independently and combined:

- **Harness layer** — the agent that runs the model and its tools. Controls what the agent may invoke and approve, and may sandbox the commands it launches.
- **Execution layer** — the environment around the agent process or its code. Controls what files, networks and credentials are reachable at all.

The effective control is the intersection of both, plus anything that runs outside them (MCP servers, plugins, connectors). The key question is not "which sandbox is strongest?" but: *what is inside the boundary, what can it read, where can it send data, which identities can it use, and how do results come back?*

## What was analyzed

| Tool | Layer | What it is for |
|---|---|---|
| **Claude Code** | Harness | Local coding agent. Optional OS shell sandbox (Seatbelt, bubblewrap; WSL2 on Windows), off by default; covers shell commands, not every tool. |
| **Codex** | Harness | Local coding agent. Command sandbox (read-only, workspace-write, full access) with approval policies; command network off by default in workspace-write. |
| **Pi-dev** | Harness | Extensible, composable agent core. No built-in sandbox or per-tool approvals; isolation comes from an external runtime or an extension. |
| **Ordinary Docker** | Execution | Reproducible builds, CI, resource limits. Shares the host kernel, so a weak choice for hostile code. |
| **Docker Sandboxes (`sbx`)** | Execution | Local autonomous-agent isolation: one microVM per agent with its own kernel and private Docker Engine; mountless, direct, or clone workspace modes. |
| **E2B** | Execution | Managed (or self-hosted) microVM sandboxes via SDK/API for products that run user code remotely. Outbound access is on by default. |
| **NVIDIA OpenShell** | Execution | Policy runtime for centrally governed agents: Landlock filesystem, deny-by-default egress, credential brokering, audit. Boundary depends on the compute driver. |

## What is recommended

| Situation | Recommendation | Reasoning |
|---|---|---|
| Routine local work on a trusted repo | Use the harness's own sandbox (Claude Code or Codex) with a narrow filesystem boundary and command network limited to what is needed. | The inputs are trusted, so the lightest control that fits the normal workflow is enough. The native sandboxes are integrated and fast, and limit shell commands, but they cover only commands, not connectors or other tools. |
| Untrusted or autonomous agents, including Pi on an untrusted repo | Run the **whole agent process** in a microVM boundary. For one developer or a small team, start with **Docker Sandboxes**, preferring clone or mountless mode and a narrow egress policy. | A microVM has its own kernel, unlike a container or a command sandbox. Whole-process isolation also covers extensions and tools that command-only sandboxes miss; Pi has no sandbox of its own. Docker Sandboxes is the more turnkey local option, with a private Docker Engine and workspace modes that give a review and handoff point. |
| Team or fleet needing central policy, credential providers and audit | **NVIDIA OpenShell**; accept more setup and verify the effective policy, including provider-added rules. | It has the most detailed policy surface in the notes: deny-by-default egress, request-aware rules, gateway-held credentials and audit. The price is more moving parts, and its boundary depends on the compute driver you pick. |
| Product feature that runs user code remotely | **E2B**; narrow egress, token-gate ingress, set timeouts, clean up persisted sandboxes. | It is built for application-managed remote execution through an SDK or API, with microVM isolation and parallel jobs. Defaults need tightening: outbound access is on and public URLs are open unless token-gated. |
| Trusted build/test jobs | Ordinary Docker with non-root, minimal mounts and no host Docker socket. | It packages environments and sets resource limits at low cost. The shared host kernel is acceptable only when the code is trusted; if it is not, move up to a microVM. |

Do this regardless of the tool:

1. Start from least access; avoid SSH agent forwarding and broad host credentials.
2. Treat network egress as the main exfiltration path and inspect the *effective* policy.
3. Review returned artifacts (scripts, hooks, CI files) before running them on the host.
4. Remember that approvals limit unauthorized actions and sandboxes limit impact; neither replaces the other.

## What no sandbox fixes

A permitted action can still do damage: an agent with write access can alter those files, and one holding a database credential can use it. A microVM with a read-write mount, broad egress or forwarded identity can be less safe than a tightly configured weaker boundary.

## Try it

Reproducible trial checklists (preflight, least-access setup, smoke test, teardown) are available as skills in this repo:

- **Docker Sandboxes:** [`setup-smoketest-docker-sandbox`](../../.claude/skills/setup-smoketest-docker-sandbox/SKILL.md)
- **NVIDIA OpenShell:** [`setup-smoketest-openshell`](../../.claude/skills/setup-smoketest-openshell/SKILL.md)

OpenShell is not production-qualified on native Windows; on a Windows 11 host, Docker Sandboxes is the supported local route.

## Build a sandbox for your project

Once a trial passes, a managing agent can develop a project-specific sandbox (Dockerfile, mounts, network policy, agent persona) and prove it with a representative task, following [the method](../guides/developing-an-app-sandbox.md):

- **Docker Sandboxes:** [`develop-docker-sandbox`](../../.claude/skills/develop-docker-sandbox/SKILL.md)
- **NVIDIA OpenShell:** [`develop-openshell-sandbox`](../../.claude/skills/develop-openshell-sandbox/SKILL.md)

## Where to read more

- Choosing a local outer boundary and setup: [recommended-local-agent-sandbox-options.md](synthesis/recommended-local-agent-sandbox-options.md)
- Full layered matrix and cost comparison: [comparative-sandboxing-analysis.md](synthesis/comparative-sandboxing-analysis.md)
- Risks mapped to mitigations: [coding-agent-risk-scenarios-and-sandbox-mitigations.md](synthesis/coding-agent-risk-scenarios-and-sandbox-mitigations.md)
- Per-product detail: [harness](harness/index.md) and [execution](execution/index.md)
