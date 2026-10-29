# NVIDIA OpenShell as an outer execution boundary: setup and local development

This guide covers the **execution layer**, using NVIDIA OpenShell as the outer policy and execution boundary for the **agent harness** Claude Code or Codex. The harness controls its own tool workflow and may apply an inner command sandbox; OpenShell controls what the outer workload can access. OpenShell launches the agent in a sandbox, applies filesystem/process rules, routes network traffic through its policy layer, and can broker supported credentials. The sandbox compute driver determines the isolation implementation: Docker, Podman, Kubernetes, or MicroVM. An inner harness control cannot grant access denied by OpenShell.

To reproduce this setup as a checklist with a smoke test, use the [`openshell-local-agent`](../../../.claude/skills/openshell-local-agent/SKILL.md) skill.

## 1. Check host support and choose a driver

OpenShell requires a reachable gateway, the CLI, and a configured compute driver.

- **macOS:** the current docs support a local gateway and MicroVM using Hypervisor.framework. The installer uses Homebrew.
- **Linux:** Debian/Ubuntu or Fedora/RHEL installation is documented. MicroVM requires KVM; Docker and Podman are also available.
- **Windows:** current native Windows MXC support is described as developmental and not production-qualified. WSL2 is a separate experimental route. For a supported local workflow on Windows, consider the Docker Sandboxes guide instead.

Review [OpenShell installation](https://docs.nvidia.com/openshell/latest/about/installation/) and [compute drivers](https://docs.nvidia.com/openshell/latest/how-it-works/sandboxes/runtimes) for current requirements. The local gateway auto-detects an available runtime; operators can pin a driver in the gateway configuration. If choosing Docker, Docker Desktop/Engine is required and specific Docker Desktop settings may apply. For the strongest local host boundary in a supported configuration, choose the MicroVM driver where available.

## 2. Install the CLI and start the local gateway

On macOS/Linux, OpenShell documents:

```sh
curl -LsSf https://raw.githubusercontent.com/NVIDIA/OpenShell/main/install.sh | sh
```

The installer uses the platform package manager and starts a local gateway. Confirm the CLI is available:

```sh
openshell --help
```

If the gateway is not selected automatically, register/select the local gateway using the address printed by installation. The documented example (a trusted local port-forward; the installer's own gateway listens on https://127.0.0.1:17670 on Linux/macOS) is:

```sh
openshell gateway add http://127.0.0.1:8080 --local --name local
openshell gateway select local
```

Use the actual local gateway URL for your installation. Check status and available drivers with the current CLI help/installation docs before launching workloads.

## 3. Create an agent sandbox

OpenShell can create Claude Code or Codex sandboxes. The quickstart form is:

```sh
openshell sandbox create --name my-project -- claude
```

For Codex, replace `claude` with `codex`:

```sh
openshell sandbox create --name my-project -- codex
```

The default Ubuntu workload does not bundle agent CLIs, and the quickstart passes `--from <image containing the agent>`. These two examples are not shown for Claude Code or Codex in the docs; add `--from` with an image that contains the CLI.

The CLI may offer to create a model provider from local credentials. OpenShell provider credentials are held by the gateway and represented inside the sandbox by placeholders; network policy and provider endpoint bindings both determine where they can be used. Use a dedicated least-privilege GitHub provider only if the agent needs to push or open pull requests. ([Quickstart](https://docs.nvidia.com/openshell/latest/get-started/quickstart), [Providers](https://docs.nvidia.com/openshell/latest/how-it-works/providers/overview))

To create with explicit CPU/memory or a policy file, see [Manage Sandboxes](https://docs.nvidia.com/openshell/latest/how-it-works/sandboxes/overview) and [Manage Sandbox Policies](https://docs.nvidia.com/openshell/latest/how-it-works/policies/manage-policies). Filesystem/process rules are fixed at startup, so decide on those before creation.

## 4. Bring in a local project and work on it

### Safer default: transfer or clone project files into the sandbox

Keep the host project outside the sandbox boundary and transfer only the files needed. OpenShell documents `sandbox upload` and `sandbox download`; upload a project directory to the sandbox workspace, then point Claude Code/Codex at that guest path. For repeated work, use Git branches in the sandbox and push/fetch changes through a scoped Git provider.

Example upload form from the OpenShell CLI documentation:

```sh
openshell sandbox upload my-project ./src /sandbox/src
```

The CLI preserves a named directory’s basename at the destination (the example results in `/sandbox/src/src`). Downloads are constrained to the writable sandbox workspace. Check the [sandbox file transfer guide](https://docs.nvidia.com/openshell/latest/how-it-works/sandboxes/overview) for exact current syntax and path behavior.

### Direct host bind mount: only when live editing is needed

OpenShell can configure host bind mounts for some drivers, but they expose gateway-host files and can bypass workspace isolation and filesystem policy. Bind mounts are disabled by default in the documented Docker driver and require operator configuration. Use a narrow path, prefer read-only unless live writes are essential, and understand that an outer filesystem policy is not a substitute for protecting the shared host path. See [Sandbox Runtimes](https://docs.nvidia.com/openshell/latest/how-it-works/sandboxes/runtimes).

## 5. Local development loop

1. Create a named sandbox with the intended policy and workspace data.
2. Work inside the sandbox. Run builds and tests there; keep production credentials out of the guest.
3. Inspect current policy and denied requests:

   ```sh
   openshell policy get my-project --base
   openshell policy get my-project --full
   openshell logs my-project --tail --source sandbox
   ```

   The effective policy includes provider-contributed rules; inspect it when assessing actual reach.
4. Transfer or push reviewed changes back to the host. Inspect the diff before executing generated scripts or merging.
5. Stop or delete the sandbox when done. OpenShell retains sandbox state until it is removed; copy out needed files first.

## 6. Modify permissions

OpenShell splits permissions into **static startup controls** and **dynamic network controls**.

### Filesystem and process permissions

`filesystem_policy`, Landlock behavior, and process identity are established when the sandbox starts. To grant the agent another filesystem path, revise the policy and recreate the sandbox. The `hard_requirement` setting fails closed if filesystem enforcement cannot be established; best-effort behavior may allow startup without the requested filesystem rules, so choose deliberately for your threat model. Follow the current schema and preserve OpenShell’s required baseline paths when editing a full policy.

The agent’s built-in Claude Code `/sandbox` or Codex `/permissions` is an optional inner layer. It can narrow access to files already visible inside the OpenShell guest. It cannot override Landlock or expose a host file not transferred/mounted into the guest. If Claude/Codex inner restrictions conflict with the runtime, keep OpenShell’s outer policy authoritative and investigate the inner configuration rather than weakening the outer policy reflexively.

### Network permissions

OpenShell denies outbound access unless policy permits it. An operator can add a rule to a running sandbox using `openshell policy update`; network changes hot-reload. For inspected HTTP endpoints, policy can restrict methods and paths and bind access to binaries.

If you want the agent to request access after a denial, enable **Policy Advisor**. The agent can propose a narrow network rule; by default an operator reviews and approves/rejects it. The agent does not approve its own proposal. The approved rule applies to the running sandbox. Policy Advisor is a network mechanism only; it does not add filesystem paths. ([Policy Advisor](https://docs.nvidia.com/openshell/latest/how-it-works/policies/advisor), [Policy updates](https://docs.nvidia.com/openshell/latest/how-it-works/policies/manage-policies))

### Credentials

Use OpenShell providers for supported model/Git credentials. Keep credential scope narrow and inspect both the provider binding and the sandbox’s effective network policy. A credential placeholder protects the raw secret value from guest processes, but the agent can still use the permitted identity at its allowed endpoints.

### Licensing and operating costs

OpenShell is published under Apache-2.0, and no per-sandbox or per-run license fee is documented. Self-hosting still uses your own compute, storage, and operations, while model-provider usage is billed separately. NVIDIA AI Enterprise/support are separate commercial offerings; the OpenShell documentation does not make them prerequisites. APF, if added, is also Apache-2.0 in its current Dev documentation, but check its compatibility and production support status before adopting it. ([OpenShell repository](https://github.com/NVIDIA/OpenShell), [APF license](https://docs.nvidia.com/agent-policy-fabric/resources/license), [NVIDIA software licensing FAQ](https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-software-licensing-overview-and-faq/))

## 7. Important limitations

- OpenShell’s protection depends on the selected driver and host configuration. A Docker driver is not automatically the same isolation boundary as a MicroVM driver.
- A host bind mount deliberately shares files and can weaken the filesystem boundary.
- Network allow rules permit activity at the destination; use request-level policy where supported and least-privilege credentials.
- Filesystem/process changes require sandbox recreation; only network policy is generally hot-reloadable.
- OpenShell native Windows MXC is not production-qualified in the current docs; verify support before relying on it for sensitive work.

## Sources

- [OpenShell Quickstart](https://docs.nvidia.com/openshell/latest/get-started/quickstart)
- [Installation](https://docs.nvidia.com/openshell/latest/about/installation/)
- [Sandbox Compute Drivers](https://docs.nvidia.com/openshell/latest/how-it-works/sandboxes/runtimes)
- [Manage Sandboxes](https://docs.nvidia.com/openshell/latest/how-it-works/sandboxes/overview)
- [Sandbox Runtimes and mounts](https://docs.nvidia.com/openshell/latest/how-it-works/sandboxes/runtimes)
- [Sandbox Policies](https://docs.nvidia.com/openshell/latest/how-it-works/policies/overview)
- [Policy Advisor](https://docs.nvidia.com/openshell/latest/how-it-works/policies/advisor)
- [Manage Sandbox Policies](https://docs.nvidia.com/openshell/latest/how-it-works/policies/manage-policies)
