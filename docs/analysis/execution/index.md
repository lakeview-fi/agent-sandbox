# Execution analyses index

Execution environments and policy runtimes contain an agent process or its code. These notes cover isolation boundaries, workspace handoff, and network and credential policy.

## Feature analyses

- [Docker containers and Docker Sandboxes](docker-agent-sandbox.md) — why an ordinary container shares the host kernel, and what a microVM-based Docker Sandbox adds.
- [E2B Sandbox](e2b-analysis.md) — hosted (and self-hostable) microVM sandboxes driven through an SDK, API, or CLI.
- [NVIDIA OpenShell](nvidia-openshell-analysis.md) — policy-driven runtime with path, process, network, and credential controls, plus fleet and audit features.

## Local setup guides

- [Docker Sandboxes: setup and local development](docker-sandbox-local-agent-guide.md) — install, authenticate, choose a workspace mode, and modify permissions.
- [NVIDIA OpenShell: setup and local development](nvidia-openshell-local-agent-guide.md) — choose a driver, start the gateway, create a sandbox, and modify policy.

## Reproducible trial skills

Agent skills that turn the guides into a runnable checklist with a smoke test:

- [`setup-smoketest-docker-sandbox`](../../../.claude/skills/setup-smoketest-docker-sandbox/SKILL.md) — Docker Sandboxes (`sbx`) trial.
- [`setup-smoketest-openshell`](../../../.claude/skills/setup-smoketest-openshell/SKILL.md) — NVIDIA OpenShell trial.
- [`develop-docker-sandbox`](../../../.claude/skills/develop-docker-sandbox/SKILL.md) and [`develop-openshell-sandbox`](../../../.claude/skills/develop-openshell-sandbox/SKILL.md) — develop and test a project-specific sandbox ([method](../../guides/developing-an-app-sandbox.md)).
