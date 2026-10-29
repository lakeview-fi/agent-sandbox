# agent-sandbox

Research notes on how to run AI coding agents (Claude Code, Codex, Pi-dev) without giving them unrestricted access to a developer's machine. The notes compare two layers of control and recommend local setups for Windows 11 with WSL2 and for macOS and Linux.

## What is in this repository

This repository is documentation plus Claude Code skills. It has no application code, build system, or tests.

| Path | Contents |
|---|---|
| [`docs/`](docs/index.md) | All documentation. Start at the index. |
| [`.claude/skills/`](.claude/skills) | Skills that set up and smoke-test a sandbox, and that develop a sandbox for your project. See [How to use this](#how-to-use-this). |
| [`docs/analysis/harness/`](docs/analysis/harness/index.md) | Built-in sandboxes and approval models of the agent harnesses: Claude Code, Codex, Pi-dev. |
| [`docs/analysis/execution/`](docs/analysis/execution/index.md) | Outer execution boundaries: Docker Sandboxes, ordinary Docker, E2B, NVIDIA OpenShell, with local setup guides. |
| [`docs/analysis/synthesis/`](docs/analysis/synthesis/index.md) | Cross-cutting comparisons, risk mapping, dynamic access requests, and a design proposal for a custom chat UI. |

## How to use this

The skills are for [Claude Code](https://code.claude.com/docs/en/skills). Pick **Docker Sandboxes** (supported on Windows 11, macOS and Linux) or **NVIDIA OpenShell** (macOS and Linux; experimental on Windows). Not sure? Read the [executive summary](docs/analysis/executive-summary.md) first.

### 1. Set up and smoke-test the tool (once per machine)

Open Claude Code **in this repository**. The skills in `.claude/skills/` load automatically as project skills, so nothing is installed globally.

```sh
cd /path/to/agent-sandbox
claude
```

Then run one of:

- `/setup-smoketest-docker-sandbox`
- `/setup-smoketest-openshell`

Claude asks before installing anything and before any login. You run the sign-in and secret commands yourself. The skill proves the sandbox starts, blocks unlisted network hosts, and keeps host files out of reach, and it records the results in `docs/trials/` (gitignored, so your machine's records are not committed).

### 2. Develop a sandbox for your project

Start Claude Code **in your project** and add this repository for that session only. The `develop-...` skills load from this repository's `.claude/skills/` and nothing is copied or installed globally.

```sh
cd /path/to/your-project
claude --add-dir /path/to/agent-sandbox
```

On Windows PowerShell use a Windows path, for example `claude --add-dir C:\src\agent-sandbox`. The `--add-dir` flag also gives the session file access to this repository.

Then run `/develop-docker-sandbox` or `/develop-openshell-sandbox` and describe what you want, for example:

> Build a sandbox for this project for Claude Code. Put it in `sandbox/`. Mount `../reference-docs` read-only. Use the reviewer persona in `.claude/agents/reviewer.md`. The acceptance task is: run the test suite and fix any failing test.

The managing session writes the Dockerfile (if needed) and the policy or environment file, runs your agent in the sandbox on the acceptance task, and tightens or widens access one step at a time. Each widening is logged in `sandbox/DECISIONS.md`, and anything touching credentials or host-write paths comes back to you. The method is in [developing an application-specific sandbox](docs/guides/developing-an-app-sandbox.md).

### Alternative: symlink instead of `--add-dir`

To have the skills in one project without passing a flag each time, symlink them into that project:

```sh
mkdir -p .claude/skills
ln -s /path/to/agent-sandbox/.claude/skills/develop-docker-sandbox .claude/skills/develop-docker-sandbox
ln -s /path/to/agent-sandbox/.claude/skills/develop-openshell-sandbox .claude/skills/develop-openshell-sandbox
```

Claude Code documents symlinked skill folders. On Windows, creating symlinks needs Developer Mode or an elevated shell, and `--add-dir` is simpler. A symlinked skill links to this repository's guides by relative path, which may not resolve from the project; `--add-dir` does not have that problem.

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
