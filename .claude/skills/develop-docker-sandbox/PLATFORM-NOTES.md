# Docker Sandboxes: host-specific notes for sandbox development

Read with the shared "Host differences" section of [developing-an-app-sandbox.md](../../../docs/guides/developing-an-app-sandbox.md). Install and preflight are in the `setup-smoketest-docker-sandbox` platform files. Live docs win: https://docs.docker.com/ai/sandboxes/

## All hosts

- Host-side steps in `sbxenv.yaml` (`secrets.command`, `lifecycle.initialize/postCreate/preRemove`, `mcp.servers.command`) run in the user's host shell. Write commands that exist there, for example `gh auth token`; avoid shell-specific syntax unless you note the shell.
- Relative paths in `sbxenv.yaml` resolve from the file's directory, not the current directory. Re-check them after moving the file.
- Direct mounts use a virtiofs cache by default. If the sandboxed agent sees stale files, try `DOCKER_SANDBOXES_ENABLE_VIRTIOFS_CACHE=0` (documented by Docker; per-OS effect untested) and record that you did.

## Windows 11

- Prefer Windows paths in `sbxenv.yaml` only if tested; otherwise use relative paths. Avoid spaces in paths.
- Host scripts called from lifecycle commands need a PowerShell form (`.ps1`) or an explicit shell invocation.
- Set LF line endings for Dockerfiles, kit files and any script copied into the image (`.gitattributes`).
- Windows Hypervisor Platform must be enabled (see the setup skill's Windows file).

## macOS (Apple silicon and Intel)

- Apple silicon: build and test images for arm64; do not hard-code x86-64 binaries in the Dockerfile. If an x86-64-only tool is required, say so in `DECISIONS.md`.
- The host file system is usually case-insensitive; prefer clone mode so the agent works on a case-sensitive in-VM copy.

## Linux

- Direct mounts can show ownership or permission errors if the host user's UID is not 1000 (the sandbox `agent` user). Prefer clone mode, or diagnose with `ls -ln` inside the sandbox before widening any policy.
- Docker documents specific distributions (reportedly Ubuntu 24.04 and later); record the distribution and version in `DECISIONS.md`.
