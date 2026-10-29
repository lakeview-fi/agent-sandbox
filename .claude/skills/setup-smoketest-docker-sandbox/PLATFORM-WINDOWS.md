# Docker Sandboxes on Windows 11

Live docs (read before acting; they override this file): https://docs.docker.com/ai/sandboxes/install/ and https://docs.docker.com/ai/sandboxes/get-started/

## Preflight

- Windows 11 x64 with Windows Hypervisor Platform. Check the live compatibility matrix for nested or other virtualization layers.
- Use PowerShell. `sbx` commands are identical to the Unix ones; only paths and shell syntax differ.
- Check for an existing install: `sbx version`.

## Install (ask the user first; step 1 needs an elevated PowerShell)

```powershell
Enable-WindowsOptionalFeature -Online -FeatureName HypervisorPlatform -All
```

Restart Windows if prompted, then in a normal PowerShell:

```powershell
winget install -h Docker.sbx
```

## Host-side syntax for the shared workflow

```powershell
cd C:\path\to\throwaway-repo
sbx run --clone --name trial claude .   # or: codex
```

Use Windows paths for the host working directory. Commands the agent runs inside the sandbox are Linux commands (`curl`, `ls`), not PowerShell.

## Windows notes

- If `winget` is unavailable, use Docker's documented installer from the install page.
- A restart is required after enabling the hypervisor feature; do not continue until it is done.
