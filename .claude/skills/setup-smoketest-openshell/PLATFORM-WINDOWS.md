# OpenShell on Windows 11

Live docs (read before acting; they override this file): https://docs.nvidia.com/openshell/latest/about/installation/ and https://docs.nvidia.com/openshell/latest/how-it-works/sandboxes/runtimes

## Support status

- Native Windows (MXC) is described as developmental and **not production-qualified**.
- WSL2 is a separate **experimental** route.
- For a supported local Windows workflow, use the `setup-smoketest-docker-sandbox` skill instead.

Tell the user which of these they are choosing, and get an explicit yes before continuing.

## Options

1. **Recommended:** switch to the Docker Sandboxes skill.
2. **WSL2 (experimental):** install and use a supported Linux distribution in WSL2, then follow [PLATFORM-MACOS-LINUX.md](PLATFORM-MACOS-LINUX.md) *inside WSL2*. Nested virtualization and KVM availability vary; if MicroVM is unavailable, the Docker or Podman driver gives a weaker (shared-kernel) boundary. Record this.
3. **Native Windows (MXC):** follow the installation page's Windows section only if the user accepts non-production status. Do not use it for sensitive work.

## Syntax notes

- When working inside WSL2, use Linux paths and shell syntax; Windows files appear under `/mnt/c/...` but keep the trial project on the WSL filesystem.
- On native Windows, use PowerShell and Windows paths (for example `.\src`) for host-side arguments; commands run in the sandbox are Linux commands.
