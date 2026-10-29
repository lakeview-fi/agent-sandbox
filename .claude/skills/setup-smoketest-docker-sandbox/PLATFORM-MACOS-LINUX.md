# Docker Sandboxes on macOS and Linux

Live docs (read before acting; they override this file): https://docs.docker.com/ai/sandboxes/install/ and https://docs.docker.com/ai/sandboxes/get-started/

## Preflight

- **macOS:** Apple silicon and macOS 14 or later.
- **Linux:** KVM enabled and accessible to your user (`ls -l /dev/kvm`), on a distribution Docker documents. Docker's docs reportedly support only Ubuntu 24.04+ and not its derivatives; verify against the install page.
- Check for an existing install: `sbx version`.

## Install (ask the user first)

Follow the macOS or Linux section of the install page above; the install command differs per OS and changes between releases, so take it from the live page rather than from memory.

## Host-side syntax for the shared workflow

```sh
cd /path/to/throwaway-repo
sbx run --clone --name trial claude .   # or: codex
```

## macOS and Linux notes

- Linux: if `/dev/kvm` is missing or not writable, stop and fix virtualization/group membership first; do not work around it.
- Commands the agent runs inside the sandbox are the same on both OSes (Linux guest).
