# agent-sandbox

Research notes on how to run AI coding agents (Claude Code, Codex, Pi-dev) without giving them unrestricted access to a developer's machine. The notes compare two layers of control and recommend local setups for Windows 11 with WSL2 and for macOS and Linux.

## What is in this repository

This repository is documentation only. It has no application code, build system, or tests.

| Path | Contents |
|---|---|
| [`docs/`](docs/index.md) | All content. Start at the index. |
| [`docs/analysis/harness/`](docs/analysis/harness/index.md) | Built-in sandboxes and approval models of the agent harnesses: Claude Code, Codex, Pi-dev. |
| [`docs/analysis/execution/`](docs/analysis/execution/index.md) | Outer execution boundaries: Docker Sandboxes, ordinary Docker, E2B, NVIDIA OpenShell, with local setup guides. |
| [`docs/analysis/synthesis/`](docs/analysis/synthesis/index.md) | Cross-cutting comparisons, risk mapping, dynamic access requests, and a design proposal for a custom chat UI. |

## The two layers

The notes separate two kinds of control, which operate at different levels and can be combined:

- **Harness layer** controls what the agent itself can invoke and approve. Claude Code and Codex include a command sandbox. Pi-dev core does not.
- **Execution layer** controls what the contained process can reach: files, network, credentials, and the Docker daemon. Docker Sandboxes (`sbx`) and NVIDIA OpenShell are the two practical local options compared here.

The effective permission is the intersection of the harness controls, the outer runtime policy, and any integrations that sit outside both.

## Recommendations

- **Local work with Claude Code or Codex:** use a Docker Sandbox for a turnkey microVM workflow, or OpenShell when you need explicit policy, credential providers, and audit. Start with the least access: clone mode or a narrow mount, network denied by default, and no host credentials or SSH forwarding unless needed.
- **Untrusted or autonomous code:** prefer a VM or microVM boundary with deliberate file transfer over a shared-kernel container.
- **Review before you run:** neither product makes permitted actions safe. Review generated scripts, hooks, and CI changes before running them on the host.

Start with [Recommended local agent sandbox options](docs/analysis/synthesis/recommended-local-agent-sandbox-options.md).

## Status and caveats

- The analyses describe vendor behavior as of late October 2026. Products change quickly; verify against the installed versions before relying on a claim.
- These notes are not a security certification. They are engineering comparisons to inform design and setup decisions.
- The E2B "local" option described in the comparison is a third-party, SDK-compatible implementation, not the hosted E2B service running locally.
- The custom chat UI document is a proposal, not an implemented system.

## Contributing

Add new notes under the matching folder in `docs/`, and add a line for each new document to that folder's `index.md` and to its parent indexes. See [docs/index.md](docs/index.md).
