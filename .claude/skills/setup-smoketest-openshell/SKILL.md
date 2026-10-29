---
name: setup-smoketest-openshell
description: Set up and run Claude Code or Codex inside a local NVIDIA OpenShell sandbox on macOS, Linux or Windows (experimental) in a reproducible way, with deny-by-default egress, a chosen compute driver, and a smoke test. Use when the user wants to try, set up, reproduce, or tear down NVIDIA OpenShell, openshell gateway or sandbox commands, or policy-governed agent sandboxes.
---

# NVIDIA OpenShell: reproducible local trial

Background: [nvidia-openshell-local-agent-guide.md](../../../docs/analysis/execution/nvidia-openshell-local-agent-guide.md). Why OpenShell: [executive-summary.md](../../../docs/analysis/executive-summary.md). This skill is the runnable checklist; some CLI details are unverified. If anything disagrees with OpenShell's live docs (https://docs.nvidia.com/openshell/latest/), say so and follow the docs.

## Ground rules

- Ask the user before installing anything; show the installer URL and get a yes first.
- Never type or paste credentials. Providers hold credentials in the gateway; the user supplies them when the CLI prompts.
- Filesystem and process policy is fixed at sandbox creation; only network policy hot-reloads.

## Pick your platform first

Detect the host OS, then read the matching file **before step 1** and the live docs it links:

- macOS or Linux → [PLATFORM-MACOS-LINUX.md](PLATFORM-MACOS-LINUX.md)
- Windows 11 → [PLATFORM-WINDOWS.md](PLATFORM-WINDOWS.md) (not production-qualified; Docker Sandboxes is the supported alternative)

Those files own preflight, driver choice, install, and host syntax. Everything below is the same on every OS.

## Workflow

```
- [ ] 1. Preflight and driver (platform file)
- [ ] 2. Install CLI and local gateway (platform file)
- [ ] 3. Create a sandbox from an image that contains the agent CLI
- [ ] 4. Transfer a throwaway project in
- [ ] 5. Smoke test
- [ ] 6. Record versions and results
- [ ] 7. Teardown
```

### 2b. Gateway

If no gateway is selected after install, register the one the installer printed (its own gateway is `https://127.0.0.1:17670` on Linux/macOS):

```sh
openshell gateway add <printed-url> --local --name local
openshell gateway select local
```

### 3. Create the sandbox

The default Ubuntu workload does not bundle agent CLIs, so pass an image that has one:

```sh
openshell sandbox create --name trial --from <image-with-agent-cli> -- claude   # or: codex
```

This exact form is not shown in the docs for Claude/Codex; if it fails, follow the quickstart pattern. Decline or narrow any offered provider.

### 4. Transfer a throwaway project

Use `openshell sandbox upload trial <host-src> /sandbox/src` (path syntax in the platform file). The basename is preserved. Skip host bind mounts for the first trial.

### 5. Smoke test

1. Ask the agent to fetch an external URL: must be denied. Check `openshell logs trial --tail --source sandbox`.
2. Add one destination as operator via `openshell policy update` (see `--help`), retry: must succeed; another host must still be denied.
3. Inspect effective policy: `openshell policy get trial --base` and `--full`; note provider-added rules.
4. Confirm host files outside the uploaded project are not visible.
5. Optional: enable Policy Advisor (off by default), trigger a denial, confirm an operator must approve and the agent cannot approve its own proposal.

Unexpected results are findings; record them.

### 6. Record

Write to `docs/trials/openshell-<os>.md`: OpenShell/CLI version, driver, host OS and version, date, effective policy output, each smoke-test result. If you create `docs/trials/`, add it to `docs/index.md`.

### 7. Teardown

OpenShell keeps state until removed. Copy out needed files (`openshell sandbox download ...`), then delete the sandbox (see `openshell sandbox --help`).

## Gotchas

- Docker/Podman driver is not the MicroVM boundary; record which one you tested.
- `hard_requirement` Landlock fails closed; `best_effort` may start without filesystem rules.
- Effective policy includes provider-contributed rules; inspect it, not just your file.
- A credential placeholder hides the raw secret, but the agent can still use it at permitted endpoints.
