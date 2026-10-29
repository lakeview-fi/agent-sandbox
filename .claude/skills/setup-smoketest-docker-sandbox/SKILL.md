---
name: setup-smoketest-docker-sandbox
description: Set up and run Claude Code or Codex inside a local Docker Sandbox (sbx microVM) on Windows, macOS or Linux in a reproducible way, with a least-access network and workspace policy and a smoke test. Use when the user wants to try, set up, reproduce, or tear down Docker Sandboxes (sbx), or run a coding agent in a Docker microVM.
---

# Docker Sandboxes: reproducible local trial

Background: [docker-sandbox-local-agent-guide.md](../../../docs/analysis/execution/docker-sandbox-local-agent-guide.md). Why Docker Sandboxes: [executive-summary.md](../../../docs/analysis/executive-summary.md). This skill is the runnable checklist; if it disagrees with Docker's live docs (https://docs.docker.com/ai/sandboxes/), say so and follow the live docs.

## Ground rules

- Ask the user before installing software, enabling OS features, or running `sbx login`.
- Never type or paste credentials. The user runs `sbx login` and `sbx secret set ...`; tell them the command.
- Start with least access: `deny-all` network, clone mode, no SSH agent forwarding unless needed.

## Pick your platform first

Detect the host OS, then read the matching file **before step 1** and the live docs it links:

- Windows 11 → [PLATFORM-WINDOWS.md](PLATFORM-WINDOWS.md)
- macOS or Linux → [PLATFORM-MACOS-LINUX.md](PLATFORM-MACOS-LINUX.md)

Those files own preflight, install, and host shell/path syntax. Everything below is the same on every OS.

## Workflow

```
- [ ] 1. Preflight (platform file)
- [ ] 2. Install sbx (platform file)
- [ ] 3. Sign in and init policy (user runs)
- [ ] 4. Authenticate the agent (user runs)
- [ ] 5. Create a sandbox in clone mode
- [ ] 6. Smoke test
- [ ] 7. Record versions and results
- [ ] 8. Teardown
```

### 3-4. Sign in, policy, agent auth (user runs)

```sh
sbx login
sbx policy init deny-all
```

Claude Code: run `claude` in the sandbox and use `/login`, or `sbx secret set` for a supported API credential. Codex: `sbx secret set openai --oauth`.

### 5. Create the sandbox

Use a disposable repo first, not a real project. Run `sbx run --clone --name trial claude .` (or `codex`) from the repo, using the path syntax in your platform file. Clone mode exposes the host repo read-only; the agent edits an in-VM clone.

### 6. Smoke test

Ask the agent inside the sandbox to do each and confirm the outcome (guest commands are Linux on every OS):

1. Fetch an external URL (e.g. `curl -sI https://example.com`): must be blocked under `deny-all`.
2. Allow one host from the host shell: `sbx policy allow network --sandbox trial example.com`, retry: must succeed; a different host must still be blocked.
3. Create a file in the clone: confirm it is NOT in the host working tree until fetched.
4. Read a file outside the project on the host (e.g. under the home directory): must not be visible.

Any unexpected result is a finding; record it.

### 7. Record

Write to `docs/trials/docker-sandboxes-<os>.md`: `sbx version`, `sbx policy ls`, host OS and version, date, each smoke-test result. If you create `docs/trials/`, add it to `docs/index.md`.

### 8. Teardown

```sh
sbx stop trial
sbx rm trial
```

## Gotchas

- Docker's default agent launch bypasses the agent's own inner sandbox (`--dangerously-skip-permissions` / `--dangerously-bypass-approvals-and-sandbox`); the microVM and network policy are the boundary.
- Direct mount (`sbx run --name x claude .`) lets the agent change the host tree immediately and read ignored files; use only after the clone trial.
- Network policy changes apply immediately; workspace choices are fixed at creation.
- Balanced and Locked Down hold unmatched requests for developer approval (`sbx policy approval ...`); the agent must retry.
