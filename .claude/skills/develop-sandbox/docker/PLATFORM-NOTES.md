# Docker Sandboxes: host-specific notes for sandbox development

Read with the shared "Host differences" section of [developing-an-app-sandbox.md](../../../../docs/guides/developing-an-app-sandbox.md). Install and preflight are in the `setup-smoketest-docker-sandbox` platform files. Live docs win: https://docs.docker.com/ai/sandboxes/

## Support status: Windows and PowerShell only (other OSs not yet supported)

The templates were tested only on Windows 11 with PowerShell (pwsh 7) and `sbx` v0.50.1. The host-side scripts are PowerShell: `start.ps1`, `stop.ps1`, `pull.ps1` and `watch-policy.ps1`. Nothing has been tested on macOS or Linux. Tell the user this before building there. Open work for macOS and Linux:
- Run the `.ps1` scripts with `pwsh`, or port them to `sh`. Windows-specific parts:
  - `ConvertTo-SandboxPath` in `start.ps1` assumes a drive-letter path (`C:\x` becomes `/c/x`); on macOS and Linux the host path is used as is.
  - `Start-Process -WindowStyle Hidden` starts the watcher, so `start.ps1` skips it elsewhere and tells the user to run it by hand.
  - `watch-policy.ps1` uses `%LOCALAPPDATA%` (with an untested `~/.local/state` fallback) and a named mutex.
- Verify the trap list in GUIDE.md on those hosts: mount paths, line endings, ownership and case sensitivity.
- Run the `setup-smoketest-docker-sandbox` skill on each OS first.

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
- The host file system is usually case-insensitive, and a direct mount (the default) keeps that. If the project has case-only file name differences, or its tests depend on case sensitivity, offer clone mode, which works on a case-sensitive in-VM copy.

## Linux

- Direct mounts (the default) can show ownership or permission errors if the host user's UID is not 1000 (the sandbox `agent` user). Diagnose with `ls -ln` inside the sandbox before widening any policy. If ownership cannot be fixed, offer clone mode.
- Docker documents specific distributions (reportedly Ubuntu 24.04 and later); record the distribution and version in `DECISIONS.md`.
