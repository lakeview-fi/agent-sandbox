# OpenShell: host-specific notes for sandbox development

Read with the shared "Host differences" section of [developing-an-app-sandbox.md](../../../../docs/guides/developing-an-app-sandbox.md). Install, driver choice and preflight are in the `setup-smoketest-openshell` platform files. Live docs win: https://docs.nvidia.com/openshell/latest/

## All hosts

- Record the compute driver (MicroVM, Docker, Podman, Kubernetes) and host OS in `DECISIONS.md`. A Docker or Podman driver is a container on the gateway host with a shared kernel; MicroVM is a different boundary. State which one the safety review covered.
- `--from` does not build Dockerfiles. Build with the engine the gateway uses (`docker build` for a Docker gateway, `podman build` for Podman) and push the image for a remote gateway.
- Sandbox files are Linux paths (`/sandbox/...`). Policy paths must be absolute, with no `..`.

## macOS and Linux

- Write `run.sh` as a POSIX shell script that exits on error and prints each command.
- macOS: MicroVM uses Hypervisor.framework. On Apple silicon build arm64 images, and avoid x86-64-only binaries in the Dockerfile.
- Linux: MicroVM needs KVM. If it is unavailable and you fall back to the Docker or Podman driver, record the weaker boundary and tell the user.

## Windows 11

- OpenShell is experimental on Windows (native MXC is not production-qualified; WSL2 is experimental). Tell the user, and offer the Docker skill as the supported route.
- If proceeding, work inside WSL2 and keep the project on the WSL file system (not `/mnt/c`). Run `run.sh` there; there is no native PowerShell version.
- Upload syntax uses a colon (`--upload ./src:/sandbox/src`), which may clash with a Windows drive letter (`C:\...`). Not verified: how the CLI parses that; use relative WSL paths, and test with `openshell sandbox upload --help` first.
- Set LF line endings for Dockerfiles and scripts (`.gitattributes`); CRLF shell scripts fail in the Linux image.
