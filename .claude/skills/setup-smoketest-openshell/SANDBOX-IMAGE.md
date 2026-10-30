# Sandbox image with Claude Code

Used by step 3 of SKILL.md. The OpenShell docs do not show a Claude or Codex image, so this skill ships its own: [Dockerfile](Dockerfile) in this folder.

## pi image

[Dockerfile.pi](Dockerfile.pi) is the same image with `@mariozechner/pi-coding-agent@0.73.1` instead of Claude Code (pinned; Node 22 base).

```sh
docker build -t trial-pi:local -f Dockerfile.pi .
docker run --rm --entrypoint pi trial-pi:local --version   # expect 0.73.1
```

Verified 2026-10-29 (WSL2, openshell 0.1.5): `pi -p` completes a file-reading task through the `openrouter` provider; see "Running pi through openrouter" in SMOKETEST.md. After a CLI upgrade change the supervisor tag in both Dockerfiles. Do not reuse a pre-existing image that this skill did not build.

## What the Dockerfile does

- Base: `node:22-bookworm-slim`. Claude Code 2.1.312 declares `node >=22`. On Ubuntu's packaged Node 18, the install still succeeds but prints an `EBADENGINE` warning, which is easy to miss.
- Copies `/openshell-sandbox` from `ghcr.io/nvidia/openshell/sandbox:0.1.5`. That is the OpenShell supervisor, and its tag must match the installed CLI.
- Installs `git`, `ca-certificates` and `curl` (curl gives the smoke test a second HTTP client, needed to show a network rule is scoped to one binary), then `@anthropic-ai/claude-code@2.1.312`, pinned.
- Sets `ENTRYPOINT ["/openshell-sandbox"]` and `WORKDIR /sandbox`.

The build pulls `node:22-bookworm-slim` and the OpenShell sandbox image, so it needs network access.

## Why not build on the OpenShell base image

`ghcr.io/nvidia/openshell/sandbox:0.1.5` has no shell, so `docker run ... sh` fails with `executable file not found`. It is used only as a source for the supervisor binary.

## Build and verify

Run from the skill folder. In WSL with the agent's bash sandbox, Docker commands need the bypass (see SKILL.md):

```sh
docker build -t trial-claude:local -f Dockerfile .
docker run --rm --entrypoint node trial-claude:local --version    # expect v22.x
docker run --rm --entrypoint claude trial-claude:local --version  # expect 2.1.312 (Claude Code)
```

Check that the build output has no `EBADENGINE` warning.

## Keeping it current

- Match the supervisor tag to `openshell --version`. After a CLI upgrade, change the `COPY --from=` tag.
- To change Claude Code, change the pinned version in the Dockerfile. Check its Node requirement with `npm view @anthropic-ai/claude-code@<version> engines`.
- Record the image tag and the Claude Code version in the trial file.

## Open items

- Verified: the image is found locally by the sandbox create command with the Docker driver, and the sandbox reaches `Ready` with `sleep infinity`.
- Verified (2026-10-29): `openshell sandbox exec <name> -- claude --version` prints `2.1.312 (Claude Code)` in a sandbox created this way, and the image rebuilds from cache after adding `curl`.
- Verified (2026-10-29): `claude -p` completes a file-reading task in the sandbox through the `openrouter` provider. It needs an L7 policy rule for the native `claude.exe`, the `ANTHROPIC_*` mapping and `CLAUDE_CODE_MAX_OUTPUT_TOKENS=4000`; see "Running claude through openrouter" in SMOKETEST.md.
- Not verified: an interactive `claude` session.
