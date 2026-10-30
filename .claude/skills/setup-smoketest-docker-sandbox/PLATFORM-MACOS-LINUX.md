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
python3 -I .claude/skills/setup-smoketest-docker-sandbox/smoketest.py --record
```

`smoketest.py` creates the throwaway repo and runs `sbx create --clone` itself; `sbx run` needs a terminal, so do not use it for the smoke test. The script's host-path to guest-path mapping is verified only on Windows; on macOS and Linux it assumes the guest sees the same path, and the "guest workdir mirrors host path" line reports what it actually found.

## macOS and Linux notes

- Linux: if `/dev/kvm` is missing or not writable, stop and fix virtualization/group membership first; do not work around it.
- WSL: if `uname -r` contains `microsoft`, this is WSL2 on a Windows host. Do not use this file; read the "WSL section" of [PLATFORM-WINDOWS.md](PLATFORM-WINDOWS.md) instead, where `sbx` runs on Windows.
- Commands the agent runs inside the sandbox are the same on both OSes (Linux guest).
