# Docker Sandboxes: setup and local development

This guide runs Claude Code or Codex inside a **local Docker Sandbox** (`sbx`). Each sandbox is a microVM with its own Linux kernel, network, filesystem, and Docker Engine. The agent has broad control inside that VM, but host resources are available only through configured shares and network rules.

To reproduce this setup as a checklist with a smoke test, use the [`setup-smoketest-docker-sandbox`](../../../.claude/skills/setup-smoketest-docker-sandbox/SKILL.md) skill.

## 1. Install and sign in

### Windows 11

Docker documents local `sbx` support on Windows 11 x64 with Windows Hypervisor Platform.

1. In an elevated PowerShell window, enable the hypervisor feature:

   ```powershell
   Enable-WindowsOptionalFeature -Online -FeatureName HypervisorPlatform -All
   ```

2. Restart Windows if prompted.
3. Install the per-user CLI:

   ```powershell
   winget install -h Docker.sbx
   ```

### macOS or Linux

Use the platform-specific instructions in [Docker’s installation guide](https://docs.docker.com/ai/sandboxes/install/). Local sandboxes require Apple Silicon/macOS 14+ or Linux with KVM enabled and supported by Docker’s documented distribution requirements.

Sign in and initialize a restrictive network preset:

```sh
sbx login
sbx policy init deny-all
```

You can use `balanced` instead for common development domains, but inspect the resulting allowlist. On Windows, use PowerShell command syntax where needed; `sbx` commands are the same.

## 2. Authenticate the agent

For Claude Code, run `claude` inside the sandbox and use `/login` for subscription OAuth, or store a supported API credential on the host using `sbx secret`. For Codex, authenticate on the host through the prompted OAuth flow, or store an OpenAI credential:

```sh
sbx secret set openai --oauth
```

Docker documents these host-side flows so the raw provider credential does not need to be placed in a project file or guest environment. Don’t mount general credential folders into the sandbox. To use GitHub operations, configure a narrowly scoped GitHub secret only if required. ([Claude Code](https://docs.docker.com/ai/sandboxes/agents/claude-code/), [Codex](https://docs.docker.com/ai/sandboxes/agents/codex/), [Credentials](https://docs.docker.com/ai/sandboxes/configuration/credentials/))

## 3. Choose how the project enters the sandbox

### Recommended for unfamiliar agents: private clone

The host repository is exposed read-only and the agent edits a private in-VM clone. Changes are not written into the host working tree until you fetch them back.

```sh
cd /path/to/project
sbx run --clone --name project-work codex .
```

Replace `codex` with `claude` to run Claude Code. The same named sandbox can be resumed with `sbx run --name project-work`. Review fetched commits/branches like any other incoming code.

### Convenient: direct workspace mount

```sh
cd /path/to/project
sbx run --name project-live claude .
```

The agent sees and can change the host working tree immediately. Use ordinary Git diffs and commits to review its work. Treat all files under the mounted workspace—including ignored files—as readable by the agent. Keep secrets outside that directory.

### Isolated scratch work: mountless

Create the sandbox without a project path, then attach and clone the repository inside it:

```sh
sbx create --name scratch codex
sbx run --name scratch
```

This avoids a host workspace share. You can clone from a remote or deliberately copy files in and out. A remote clone needs the appropriate network rule and authentication.

## 4. Local development loop

1. Start the sandbox in clone or direct-mount mode.
2. Let the agent install packages and run services inside the sandbox’s private Docker Engine.
3. If a download is blocked, inspect current policy:

   ```sh
   sbx policy ls
   ```

4. Add only the required host, preferably scoped to the sandbox:

   ```sh
   sbx policy allow network --sandbox project-work registry.npmjs.org
   ```

   Network policy updates take effect immediately. Avoid broad wildcard allowances when a specific host will work.
5. Review changes. In clone mode, fetch the sandbox branch/commits and inspect before merging. In direct mode, inspect `git diff` before committing.
6. Stop to preserve the VM for later, or remove it when finished:

   ```sh
   sbx stop project-work
   sbx rm project-work
   ```

## 5. Modify permissions

There are two permission layers.

### Outer Docker Sandbox permissions

- **Workspace:** choose direct mount, clone, or mountless at sandbox creation. A sandbox cannot access an arbitrary host path simply because Claude or Codex asks for it. Recreate/configure the sandbox with the intended workspace or deliberately transfer files.
- **Network:** operator-managed `sbx policy allow/deny` rules can be changed during a run and apply immediately. The agent does not grant itself access; a user or administrator changes the rule.
- **Credentials:** use the `sbx secret` store and narrow credential bindings. Disable SSH agent forwarding if the agent does not need host signing/authentication.
- **Agent authentication:** provider OAuth/API authorization is separate from file and network isolation.

### Optional inner Claude Code or Codex sandbox

Docker’s default launch commands bypass this inner layer: its Claude Code and Codex agent pages use `claude --dangerously-skip-permissions` and `codex --dangerously-bypass-approvals-and-sandbox`. Enabling an inner sandbox is therefore your own override, which Docker does not document, so treat the following as unverified. If the guest image/runtime supports it, Claude Code’s `/sandbox` or Codex’s `/permissions` can impose a narrower boundary on that agent’s shell commands. An on-request approval may let the agent use an already-visible guest file or a permitted command action. It cannot expose a host file that `sbx` did not mount, nor override Docker network policy. If all project files exposed to the guest should be available, you may choose not to enable the inner filesystem restriction; keep the Docker microVM boundary and network policy intact.

Nested sandbox implementations can have platform/runtime prerequisites. If Claude Code or Codex reports that its inner sandbox cannot initialize, do not blindly switch to unrestricted execution. Use the Docker Sandbox as the enforced outer boundary, inspect the inner sandbox configuration, and only relax the inner layer when you understand the impact.

## 6. Useful commands

```sh
sbx ls
sbx policy ls
sbx policy allow network --sandbox project-work api.example.com
sbx policy deny network --sandbox project-work ads.example.com
sbx stop project-work
sbx rm project-work
```

## Sources and platform notes

- [Install Docker Sandboxes](https://docs.docker.com/ai/sandboxes/install/)
- [Get started with local sandboxes](https://docs.docker.com/ai/sandboxes/get-started/)
- [Isolation layers and workspace modes](https://docs.docker.com/ai/sandboxes/security/isolation/)
- [Local network policy](https://docs.docker.com/ai/sandboxes/security/policy/)
- [Claude Code in Docker Sandboxes](https://docs.docker.com/ai/sandboxes/agents/claude-code/)
- [Codex in Docker Sandboxes](https://docs.docker.com/ai/sandboxes/agents/codex/)

Check Docker’s live compatibility matrix before installing. Docker documents Windows 11 support with Windows Hypervisor Platform, but other virtualization layers and nested environments can have additional requirements.
