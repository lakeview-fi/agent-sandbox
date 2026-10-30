# Docker Sandboxes on Windows 11

Live docs (read before acting; they override this file): https://docs.docker.com/ai/sandboxes/install/ and https://docs.docker.com/ai/sandboxes/get-started/

## Preflight

- Windows 11 x64 with Windows Hypervisor Platform. Check the live compatibility matrix for nested or other virtualization layers.
- Use PowerShell. `sbx` commands are identical to the Unix ones; only paths and shell syntax differ.
- Check for an existing install: `sbx version`.
- Querying the Windows Hypervisor Platform feature (`Get-WindowsOptionalFeature`) needs an elevated shell. Do not block on that: run `sbx diagnose` instead, and treat a successful `sbx create` as the real proof.

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
python -I .claude\skills\setup-smoketest-docker-sandbox\smoketest.py --record
```

`smoketest.py` creates the throwaway repo and runs `sbx create --clone` itself, so no manual `cd` or `sbx run` is needed (`sbx run` needs a terminal). Use Windows paths whenever you pass a host path to `sbx`. Commands run inside the sandbox through `sbx exec` are Linux commands (`curl`, `ls`), not PowerShell. The guest sees the workspace at `/c/Users/...`.

## WSL section (when the agent is running inside WSL)

Detect it: `grep -qi microsoft /proc/version` succeeds under WSL. The host is still Windows, and `sbx` is a Windows install. Do not install or run a Linux-side `sbx` from the WSL distro, and do not apply the KVM check from [PLATFORM-MACOS-LINUX.md](PLATFORM-MACOS-LINUX.md): WSL2 usually has no `/dev/kvm`, and that does not decide whether `sbx` works on Windows.

- Run `sbx` on the Windows side. From a WSL shell, call `powershell.exe -NoProfile -Command "..."` or ask the user to run the commands in PowerShell. Check the Windows side with `sbx version` from PowerShell.
- Hypervisor check: Windows Hypervisor Platform is a Windows feature. Check it from PowerShell, not from `/dev/kvm`.
- Enabling the feature and restarting need an elevated PowerShell. Ask the user first; do not run `Enable-WindowsOptionalFeature` from WSL.
- Host paths: `sbx` takes Windows paths. Converting a WSL path with `wslpath -w <dir>` is not verified against the live docs; confirm that `sbx` accepts the converted path before relying on it. Keep the throwaway repo on the Windows side or in a path the user confirms works.
- Record in the trial file that the host was WSL2 on Windows 11 and that `sbx` ran from PowerShell.

## Windows notes

- If `winget` is unavailable, use Docker's documented installer from the install page.
- A restart is required after enabling the hypervisor feature; do not continue until it is done.
