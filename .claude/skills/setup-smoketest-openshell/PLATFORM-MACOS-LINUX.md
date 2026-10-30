# OpenShell on macOS and Linux

Live docs (read before acting; they override this file): https://docs.nvidia.com/openshell/latest/about/installation/ and https://docs.nvidia.com/openshell/latest/how-it-works/sandboxes/runtimes

## Preflight and driver

- **macOS:** local gateway + MicroVM driver via Hypervisor.framework; the installer uses Homebrew.
- **Linux:** Debian/Ubuntu or Fedora/RHEL installation is documented. MicroVM needs KVM (`ls -l /dev/kvm`); Docker and Podman drivers are also available. If Docker is the driver, Docker Desktop/Engine must be installed and its settings may apply.
- Prefer MicroVM for the strongest local boundary. Docker/Podman drivers are containers on the gateway host (shared kernel). Record which driver was used.
- The local gateway auto-detects a runtime; operators can pin a driver in the gateway configuration.

## Install (ask the user first)

```sh
curl -LsSf https://raw.githubusercontent.com/NVIDIA/OpenShell/main/install.sh | sh
openshell --help
```

Show the user the script URL and get a yes before running it. The installer uses the platform package manager and starts a local gateway.

## Host-side syntax for the shared workflow

```sh
openshell sandbox upload trial ./src /sandbox/src
```

Same on macOS and Linux. Linux note: if `/dev/kvm` is missing or not accessible, stop and fix it, or choose the Docker/Podman driver knowingly and record the weaker boundary.

WSL note: if `uname -r` contains `microsoft`, this is WSL2 on a Windows host. Read the "WSL2 section" of [PLATFORM-WINDOWS.md](PLATFORM-WINDOWS.md) before running any preflight step; the Windows support status applies, and a missing `/dev/kvm` is common there.
