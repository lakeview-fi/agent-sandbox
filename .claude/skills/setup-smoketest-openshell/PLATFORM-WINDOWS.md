# OpenShell on Windows 11

Live docs (they override this file): https://docs.nvidia.com/openshell/latest/about/installation/ and https://docs.nvidia.com/openshell/latest/how-it-works/sandboxes/runtimes

## Support status

- Native Windows (MXC) is described as developmental and **not production-qualified**.
- WSL2 is a separate **experimental** route.
- For a supported local Windows workflow, use the `setup-smoketest-docker-sandbox` skill instead.

Tell the user which route you are choosing and get an explicit yes before continuing.

## Options

1. **Recommended:** switch to the Docker Sandboxes skill.
2. **WSL2 (experimental):** install a supported Linux distribution in WSL2, then follow [PLATFORM-MACOS-LINUX.md](PLATFORM-MACOS-LINUX.md) inside WSL2. Without `/dev/kvm`, the Docker driver is the only option, and its boundary is weaker (shared kernel). Record that.
3. **Native Windows (MXC):** follow the installation page's Windows section only if the user accepts non-production status. Do not use it for sensitive work.

## WSL2 route

Detect it with `grep -qi microsoft /proc/version`. The host is still Windows, so the support status above applies.

Read-only preflight:

- `ls -l /dev/kvm`. On WSL2 it is often missing. Nested virtualization needs `nestedVirtualization=true` in `.wslconfig` and host support. If it is missing, MicroVM is unavailable.
- `docker info`. If it reports `permission denied` on `/var/run/docker.sock`, see [WSL-DOCKER-DESKTOP.md](WSL-DOCKER-DESKTOP.md). Do not chmod or chown the socket, and do not run `sudo` without consent.
- `openshell status`. `Connection refused` on `127.0.0.1:17670` means the gateway is not running. Do not rely on `openshell doctor check`; the live docs do not list it.
- Docker and gateway commands may be blocked by the agent's bash sandbox. See "Running Docker and gateway commands" in SKILL.md.

Running from a `/mnt/c` path works (verified with openshell 0.1.5), so the project need not be moved onto the WSL filesystem. From Windows, call the script as `wsl -d <distro> -e bash -lc "cd /mnt/c/<path to the agent-sandbox repo> && python3 -I .claude/skills/setup-smoketest-openshell/smoketest.py --name <name>"`; the working directory must be the repo holding the skill, not the target project. `/dev/kvm` may be present, but that does not show which gateway driver is in use (check `openshell status`); the MicroVM driver is not verified. Record in the trial file: WSL2 on Windows 11, the driver, and the KVM result.

## Syntax

- Inside WSL2, use Linux paths and shell syntax. Windows files are under `/mnt/c/...`.
- On native Windows, use PowerShell and Windows paths for host-side arguments. Commands run in the sandbox are Linux commands.
