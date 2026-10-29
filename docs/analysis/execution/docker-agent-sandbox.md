# Using Docker to sandbox a coding agent

**Docker can sandbox a coding agent at two different strengths.** A hand-built `docker run` container is useful for reproducible dependencies and basic process/filesystem/resource isolation, but it shares the host kernel and can be weakened by mounts or daemon access. Docker Sandboxes (`sbx`) are Docker's agent-specific workflow: each local agent runs inside a microVM with its own Linux kernel and private Docker Engine, and the CLI controls what crosses that VM boundary. These are distinct products and security models.

## 1. Three ways to use Docker

| Approach | Isolation boundary | Best fit | Main caveat |
|---|---|---|---|
| Ordinary container (`docker run`) | Namespaces, cgroups and kernel security controls; host kernel is shared | Reproducible dev/test environment; trusted code; resource limits | Not a VM boundary. Host mounts and Docker socket access can expose the host |
| Docker Sandboxes (`sbx`) | Local lightweight microVM per sandbox, with a private Docker Engine | Running autonomous coding agents locally with a practical host boundary | A directly mounted workspace is deliberately read/write; review outputs and injected tools |
| Docker Agent `--sandbox` | Sandbox execution for Docker Agent configurations | Sandboxing Docker Agent teams and their declared tools | Tool/MCP capabilities and staged inputs still matter; don't confuse agent orchestration with isolation |

Docker's current `sbx` product supports agents including Codex, Claude Code, Copilot, Cursor, Gemini, OpenCode and others. It launches supported agents in full-autonomy modes; the sandbox is intended to contain that autonomy. [Docker Sandboxes](https://docs.docker.com/ai/sandboxes/), [supported agents](https://docs.docker.com/ai/sandboxes/agents/), [Docker Agent sandbox](https://docs.docker.com/ai/docker-agent/configuration/sandbox/)

## 2. Practical quick start with Docker Sandboxes

Install the `sbx` CLI for a supported platform, sign in, choose a network preset, then run an agent from the repository:

```sh
cd /path/to/repository
sbx run --name my-project codex
```

By default, the current directory is mounted read-write. Changes appear in the host working tree immediately. Reconnect with `sbx run --name my-project`; remove the environment and its installed tools with `sbx rm my-project`. For an isolated Git working copy, use:

```sh
sbx run --clone --name my-project codex .
```

In clone mode, the repository is mounted read-only and the agent edits a private clone in the VM. Fetch the sandbox branch or commits into the host repo when ready to review or integrate them. For a scratch environment with no host project mount, create a mountless sandbox. [Docker tutorial](https://docs.docker.com/get-started/tutorials/run-an-agent/), [workspace modes](https://docs.docker.com/ai/sandboxes/security/isolation/)

The sandbox persists between stops and starts, including packages and containers installed inside its private VM. Removing it discards that VM state. This lets an agent install compilers, package managers, databases, run tests, build images and use Compose without those packages, images, or containers appearing in the host Docker daemon. [Develop and test locally](https://docs.docker.com/ai/sandboxes/workflows/development/)

## 3. What the isolation enables

### Let an agent operate with fewer interruptions

An agent can have `sudo` inside its VM, install dependencies, run shell commands, start services, and use a private Docker daemon. This makes full-autonomy modes practical: the agent can prepare its environment and run a test loop without receiving host administrator access. The trust boundary is the microVM, rather than in-VM user permissions. [Isolation layers](https://docs.docker.com/ai/sandboxes/security/isolation/)

### Keep system changes disposable

Tools and operating-system changes live in the VM and can be removed with the sandbox. Persistent named sandboxes preserve useful setup across sessions; removing and recreating one gives a clean environment. Templates/kits can standardize toolchains for repeated work. [Docker tutorial](https://docs.docker.com/get-started/tutorials/run-an-agent/), [customize sandboxes](https://docs.docker.com/ai/sandboxes/configuration/customize/)

### Run multiple agents and build/test infrastructure

Each sandbox has its own kernel, filesystem, network, and Docker Engine. Agents can build images and run databases or service dependencies without sharing the host daemon or directly communicating with sibling sandboxes. A Git clone per sandbox also avoids agents racing over shared Git indexes and refs. [Isolation layers](https://docs.docker.com/ai/sandboxes/security/isolation/), [Git workflows](https://docs.docker.com/ai/sandboxes/workflows/git/)

### Select how work crosses back to the host

- **Mountless:** no host workspace; work remains in the sandbox.
- **Direct mount:** live read/write access to the selected host directory.
- **Clone mode:** host repository read-only, with a private in-VM clone; fetch/push is the deliberate handoff.

This choice is central. Direct mount gives convenience but lets the agent alter any workspace file, including scripts, CI, hooks, editor tasks, project agent settings, hidden files, and untracked or ignored files. Clone mode prevents writes through the host repository mount, but does not hide its contents: `.env`, ignored files, and other secrets under the Git root remain readable. Store secrets outside the workspace. [Workspace isolation](https://docs.docker.com/ai/sandboxes/security/isolation/)

## 4. How the controls work

### Filesystem and host access

The microVM cannot browse the host filesystem except through explicit shares. A direct workspace mount is read-write; clone mode mounts the source read-only and puts the working copy inside the VM. A shared skills store may also be mounted for supported agents, so treat it as another explicit cross-boundary resource. Sandboxes can also use filesystem policies and organization policies to restrict selected paths. Inspect the active policy with `sbx policy ls`. [Default security posture](https://docs.docker.com/ai/sandboxes/security/defaults/), [filesystem policies](https://docs.docker.com/ai/sandboxes/governance/access-controls/filesystem/)

The direct mount has important edge cases: hard links in the workspace can refer to the same underlying host file through a path outside the workspace, and files written by the agent can execute later when a developer builds, commits, pushes, or opens the project. Docker recommends reviewing workspace changes as if they came from an untrusted contributor. Clone mode blocks host writes through the repo mount, but still exposes repository contents for reading. [Isolation layers](https://docs.docker.com/ai/sandboxes/security/isolation/)

### Network access

Outbound TCP is routed through a host-side proxy that checks policy. Local presets are **Open**, **Balanced** (default deny with common development services allowed), and **Locked Down** (deny all unless allowed). Under both Balanced and Locked Down, a request that matches no rule is held for developer approval rather than hard-denied; only explicit deny rules deny outright (see Network approval below). Add or deny destinations globally or per sandbox, for example:

```sh
sbx policy init balanced
sbx policy allow network api.example.com
sbx policy deny network ads.example.com
sbx policy ls
```

UDP and ICMP are blocked by default; UDP egress is experimental. Balanced contains broad wildcard domains, so inspect its effective allowlist and remove destinations the task does not need. Organization policy can further constrain local policy: local rules cannot broaden an organization allowlist, while local denies can narrow it. [Local policy](https://docs.docker.com/ai/sandboxes/security/policy/), [default security posture](https://docs.docker.com/ai/sandboxes/security/defaults/)

### Credentials and SSH

For supported AI providers, keep API credentials in the host-side `sbx secret` store. The proxy adds authentication headers to matching outbound requests, so raw keys need not be written into the VM or exported into the agent process. Third-party kits can declare credential requirements and domains; users approve credential bindings. Registry credentials can be host-only or scoped to one or all sandboxes. [Credential management](https://docs.docker.com/ai/sandboxes/configuration/credentials/)

SSH agent forwarding is enabled by default in the documented local setup. The private key stays on the host, but a process in the sandbox can ask the forwarded agent to authenticate or sign. Disable forwarding if the agent does not need host SSH identity. Don't treat a forwarded signing or SSH agent as harmless just because the private key is not readable. [Isolation layers](https://docs.docker.com/ai/sandboxes/security/isolation/), [credentials](https://docs.docker.com/ai/sandboxes/configuration/credentials/)

### Docker daemon separation

Do not mount `/var/run/docker.sock` or the Windows equivalent into an agent container when the goal is host isolation. Control of the Docker daemon can provide host-level control. Docker Sandboxes instead provide a per-VM daemon, so agent-created containers stay within that sandbox. This also avoids polluting host images, containers, and volumes. [Docker Engine security](https://docs.docker.com/engine/security/), [Isolation layers](https://docs.docker.com/ai/sandboxes/security/isolation/)

### Lifecycle and administrative controls

Use named sandboxes to resume work, `sbx exec` for commands, `sbx cp` for deliberate file transfer, and `sbx rm` to discard an environment. Organization administrators can centrally manage network, filesystem, and MCP policies for local sandboxes. Policy inspection and logs help check which rule allowed or blocked traffic. [sbx CLI](https://docs.docker.com/reference/cli/sbx/), [policy monitoring](https://docs.docker.com/ai/sandboxes/governance/monitor-and-enforce/monitoring/)

## 5. If using ordinary Docker containers instead

A custom container is still useful where Docker Sandboxes is unavailable or a fixed build/test image is enough. A conservative Linux starting point might look like this:

```sh
docker run --rm -it \
  --user 1000:1000 \
  --cap-drop=ALL \
  --security-opt=no-new-privileges \
  --read-only \
  --tmpfs /tmp:rw,nosuid,nodev,noexec,size=1g \
  --memory=8g --cpus=4 --pids-limit=512 \
  --network=bridge \
  --mount type=bind,src="$PWD",dst=/workspace \
  --workdir=/workspace \
  my-agent-image:version
```

Treat this as a starting point, not a ready-made security recipe: the image/user, writable build directories, shell, and package manager need adapting. A read-write project mount lets the agent change the host project. `--network=bridge` still normally permits outbound connectivity; use no network or a separately enforced egress proxy/firewall if network access must be restricted. `--memory`, `--cpus`, and `--pids-limit` control resource consumption, not access to data. Never add `--privileged`, host PID/network namespaces, broad host mounts, or the host Docker socket casually. Docker documents default capability reduction and seccomp, while also warning that containers share the kernel and configuration choices matter. [Docker Engine security](https://docs.docker.com/engine/security/), [resource constraints](https://docs.docker.com/engine/containers/resource_constraints), [run reference](https://docs.docker.com/reference/cli/docker/container/run/)

An ordinary container is not automatically a security sandbox just because it is called a container. Run it as an unprivileged user, minimize mounts and capabilities, keep the default seccomp/AppArmor/SELinux confinement, add resource limits, control egress outside the container, and ensure the daemon is not exposed. Rootless Docker reduces the consequences of daemon/runtime compromise but is a separate daemon configuration, not a substitute for careful container settings. [Rootless mode](https://docs.docker.com/engine/security/rootless/), [protect daemon access](https://docs.docker.com/engine/security/protect-access/)

## 6. Limits and residual risks

1. **The shared workspace is the most direct path back to the host.** In direct mode, the agent can rewrite project files and delete data there. Clone mode is the safer choice for unfamiliar agents, parallel runs, or preserving the host working tree, but it exposes source files and secrets under the repository.
2. **Allowed network is still a data path.** An agent can send workspace contents to any permitted service. Deny-all or a short task-specific allowlist gives tighter control; credential proxying protects raw key values but does not prevent an agent from using authorized APIs.
3. **Host integrations can cross the boundary.** Local MCP servers/gateways, shared skills, clipboard writes, port forwarding, and forwarded SSH agents have their own host-side effects and controls. A sandbox does not automatically sandbox those host processes.
4. **MicroVMs reduce shared-kernel exposure; they are not a proof of invulnerability.** Keep the runtime updated and avoid weakening its boundary. For ordinary containers, the host kernel is shared by design.
5. **Development outputs can be executable inputs later.** Review scripts, hooks, CI, IDE tasks, agent settings, and generated code before triggering them on the host.

## 7. Centralized organization governance

Docker has an official centralized option: **Docker AI Governance** (called organization governance in the Docker Sandboxes docs). It is designed to govern local `sbx` sandboxes across developer machines. Admins define policy in Docker Home, scope policies to the whole organization or selected teams, and can manage network and filesystem policies through a Governance API. This is a separately paid subscription; local `sbx policy` remains available without organization governance. [Governance overview](https://docs.docker.com/ai/sandboxes/governance/), [organization policies](https://docs.docker.com/ai/sandboxes/governance/access-controls/organization/), [Docker AI Governance](https://www.docker.com/products/ai-governance/)

### Cost and approval flows

- The **`sbx` CLI and local sandbox compute are free**, including commercial use. Model-provider charges are separate.
- **Docker AI Governance is paid per license** (assignable to a team or an individual) and is sold through Docker sales. It includes centrally managed network, filesystem, and MCP governance, sign-in enforcement, and governance audit logs. The Docker subscription docs say unlicensed members can still use Docker AI products; don't assume organization policy covers those users unless they are licensed and sign-in enforcement is deployed as required. [Docker Sandboxes FAQ](https://docs.docker.com/ai/sandboxes/faq/), [AI Governance plan](https://docs.docker.com/subscription-billing/plans/ai-governance/)
- **Network approval without AI Governance:** on a local machine, a request with no matching network allow/deny rule can be held for developer approval (under the Balanced and Locked Down profiles). `sbx policy approval ls` and `sbx policy approval respond <id> --option allow` manage it. Approval adds a local grant for later requests from that sandbox to the exact destination; under an HTTP rule it is limited to the requested method/path. The denied attempt itself is not replayed, so the agent must retry. When org governance is active, a developer approval can satisfy an org policy's approval requirement only for something the org policy allows; it cannot override an explicit deny or expand the org's allowlist. [Network approvals](https://docs.docker.com/ai/sandboxes/governance/access-controls/network/)
- **MCP approval:** with AI Governance, an MCP policy can use `@requireApproval` to ask the connected MCP client for in-session confirmation. If supported and approved, that single tool/resource/prompt request is reevaluated and may proceed; it does not create a lasting grant or an administrator approval ticket. Unsupported elicitation contexts fail closed. [MCP access policies](https://docs.docker.com/ai/sandboxes/governance/access-controls/mcp/)
- **Web UI:** admins use Docker Home to author network, filesystem, and MCP policies and inspect audit events. Network pending approvals are documented as a developer-side `sbx` CLI flow; MCP confirmations are presented by the connected client. I found no documented central web approval inbox where an admin reviews and approves individual agent requests. [Organization policies](https://docs.docker.com/ai/sandboxes/governance/access-controls/organization/)
- **Cloud sandboxes cost separately:** Docker-managed cloud compute is pay-as-you-go, and model-provider usage is separate. Local organization governance does not automatically carry over to cloud sandboxes. [Docker Sandboxes FAQ](https://docs.docker.com/ai/sandboxes/faq/), [Docker Agentic Platform plans](https://docs.docker.com/subscription-billing/plans/docker-agentic-platform/)

### Could a custom UI replace paid centralized governance?

A custom UI can front the **free, per-machine local controls**: show `sbx policy ls` and pending approvals, then invoke documented `sbx policy approval`, `allow`, `deny`, and `rm` commands. That is a convenience layer for local decisions, not an organization policy plane. The reviewed docs expose a Governance API for organization policies, but it is part of the paid AI Governance service; they do not document a free API or hook that lets a local UI change centrally enforced rules.

When Docker organization governance is active, local and kit-defined allows cannot expand the organization allowlist, and explicit organization denies cannot be approved around. So a local UI cannot legitimately bypass that enforcement. To offer an equivalent centrally managed system without Docker AI Governance, an organization would need to build and operate its own trusted control plane: identity and team mapping, signed/versioned policy distribution, device/daemon enforcement that users cannot simply override, network and filesystem policy evaluation, approval workflow, audit retention, and update/failure handling. A UI or config-push script alone would not provide those guarantees. If the goal is only usability for unmanaged personal machines, wrapping `sbx` CLI commands is plausible; if the goal is enforceable fleet governance, it is a substantial security product and should be reviewed as such. [Local policy](https://docs.docker.com/ai/sandboxes/governance/access-controls/local/), [organization policy precedence](https://docs.docker.com/ai/sandboxes/governance/access-controls/organization/), [Governance API](https://docs.docker.com/reference/api/ai-governance/)

The centrally governed surfaces are:

- **Network:** allow or deny domains, IP/CIDR ranges, and ports; rules can also limit HTTP methods, paths, and query parameters. Policies may be org-wide or team-scoped. Admins can require a developer to approve destinations allowed by a policy. Organization allows are authoritative: local and kit allows cannot expand them; local and kit denies can narrow access further.
- **Filesystem mounts:** centrally allow read and/or write access to host path patterns. A writable workspace needs both read and write permission; a read-only workspace needs read permission. This is checked when a sandbox mounts its workspace, so changing the policy does not revoke access from already-running sandboxes; recreate them to apply a changed filesystem policy.
- **MCP through Docker's gateway:** Cedar policies can govern server registration, tool calls, resource reads, prompts, and built-in gateway operations, with default-deny behavior when MCP governance is active. This applies to MCP requests through the Docker gateway; an agent's direct MCP connection bypasses those MCP rules, so network policy must also govern remote destinations. Host-run stdio servers remain host processes and deserve separate scrutiny.

Docker also documents sign-in enforcement through endpoint management, intended to require organization membership and prevent developers from avoiding governance by signing in with a personal account. Monitoring includes `sbx policy ls` and `sbx policy log`; governance audit records can be viewed/exported and streamed to SIEM systems. Policy changes can take up to five minutes to propagate. Network decisions apply on subsequent requests after sync; filesystem policy applies on sandbox creation; MCP registration and use-time policies have different enforcement points. [Network policies](https://docs.docker.com/ai/sandboxes/governance/access-controls/network/), [filesystem policies](https://docs.docker.com/ai/sandboxes/governance/access-controls/filesystem/), [MCP policies](https://docs.docker.com/ai/sandboxes/governance/access-controls/mcp/), [policy monitoring](https://docs.docker.com/ai/sandboxes/governance/monitor-and-enforce/monitoring/)

### How it compares with NVIDIA Agent Policy Fabric

The two are similar in purpose at the fleet-governance level, but **not feature-for-feature equivalents**. Docker AI Governance is the direct, supported way to centrally govern Docker Sandboxes. It has an admin console, org/team scoping, machine policy synchronization, network/filesystem enforcement, MCP gateway governance, sign-in enforcement, and audit/monitoring.

NVIDIA APF, as described in the OpenShell analysis, emphasizes a signed policy-bundle supply chain and policy projection into the OpenShell admission flow, Cedar evaluation/effects through middleware, capability grants, provider governance, and policy revision/digest provenance. Docker documents central organization policies and a Governance API for network/filesystem, plus Cedar MCP policies, but the reviewed Docker docs do not describe APF-style signed bundles with admission-time projection, provider-profile governance, or the same bundle-level provenance model. Treat Docker AI Governance as a **product-level analogue for centralized access governance**, not as a claim that it implements APF's architecture.

The organization governance described here applies to **local** Docker Sandboxes. Cloud sandboxes use a separate account/sandbox network-policy store; local organization policies, credentials, workspace mounts, and local MCP registrations do not transfer. Current cloud docs describe destination-based network rules but no HTTP method/path filtering or local governance profiles; cloud MCP servers are configured through Docker Agentic Platform. Cloud execution is pay-as-you-go, has no host workspace mount/clone mode, and uses an expiry timer (one hour by default). Confirm which cloud MCP governance and audit controls apply before comparing it with local AI Governance. [Governance overview](https://docs.docker.com/ai/sandboxes/governance/), [local/cloud comparison](https://docs.docker.com/ai/sandboxes/cloud/local-vs-cloud/), [cloud usage](https://docs.docker.com/ai/sandboxes/cloud/usage/), [cloud network policy](https://docs.docker.com/ai/sandboxes/cloud/network-policy/)

I did not find a community project that integrates with `sbx` and provides an equivalent centralized enforcement plane. Community scripts or shared configuration can distribute local `sbx policy` settings, but they should be treated as configuration management, not tamper-resistant governance: Docker's own organization policy is the documented mechanism that prevents a developer's local allow rules from expanding centrally allowed access.

## Suggested configurations

| Need | Recommended starting point |
|---|---|
| Familiar agent, ordinary local development | `sbx run` with a named sandbox and Balanced network; inspect the workspace diff after each task |
| Unfamiliar agent or simultaneous agents | `sbx run --clone`; use a private working copy and fetch changes for review |
| No host source visibility needed | Mountless sandbox; copy in only necessary inputs |
| Sensitive source or network exfiltration concern | Clone or mountless mode, Locked Down networking, minimal credentials, no SSH forwarding/shared tools unless needed |
| Reproducible CI/build job | Pinned image plus non-root container, minimal mounts/capabilities, explicit CPU/memory/PID limits, controlled egress; use a VM boundary for untrusted code |

**Rule of thumb:** Use Docker Sandboxes when the goal is safe agent autonomy with a practical host workflow. Use a normal container primarily for environment packaging and resource control. In either case, choose the workspace, network, credentials, Docker daemon access, and external tools as explicit security boundaries.
