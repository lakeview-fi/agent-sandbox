# E2B Sandbox: features and how they’re controlled

**As of October 28, 2026**, E2B Sandbox is best understood as an isolated Linux machine that an application or agent can create and operate through an SDK, CLI, or API. The sandbox provides the execution environment; the developer chooses its template, lifecycle, network policy, and how it connects to data and credentials. E2B’s documentation describes the runtime as a Firecracker-based microVM with a dedicated kernel per session. [E2B overview](https://e2b.dev/), [E2B documentation](https://docs.e2b.dev/)

## What the sandbox includes

| Capability | What it provides | How it is controlled |
|---|---|---|
| **Linux execution** | A full Linux environment for running commands, arbitrary code, and long-running processes. | Create a sandbox with the JavaScript/TypeScript or Python SDK, then use its command API or CLI. |
| **Filesystem** | Read, write, list, upload, download, and watch files. Files live in the sandbox’s filesystem and can be captured in snapshots. | Use the SDK filesystem methods or interact with files from commands running in the sandbox. |
| **Interactive terminal** | A PTY for interactive shell workflows, plus command streaming and background execution. | Use the SDK’s PTY and command interfaces. |
| **Custom environments** | Templates can include a base image, packages, files, a working directory, a user, and commands to run at startup. | Define and build a template, then select it when creating sandboxes. |
| **Network access** | Outbound internet access and inbound access to services exposed on sandbox ports. | Set egress rules at sandbox creation; use `getHost(port)` for an inbound URL; optionally require a token for that URL. |
| **Persistence** | Pause and resume the same sandbox with its memory and filesystem, or make snapshots that can seed multiple new sandboxes. | Call pause/resume or snapshot/fork operations through the SDK or API. |
| **Resource monitoring** | CPU, memory, and disk metrics; E2B also supports exporting telemetry to an OTLP endpoint. | Read metrics through the SDK/API or configure telemetry export. |
| **Agent integrations** | E2B documents integrations for coding agents, computer-use agents, MCP tools, data analysis, CI, and other workflows. | Integrate through E2B’s SDK and the relevant agent or product integration. |

The core SDK is distinct from E2B’s **Code Interpreter** and **Desktop** products. Code Interpreter adds a higher-level `runCode()` interface and returns results such as charts and images; Desktop adds a virtual graphical desktop with screen streaming and mouse/keyboard interaction. [Code Interpreter overview](https://docs.e2b.dev/code-interpreting/analyze-data-with-ai), [Computer use](https://docs.e2b.dev/use-cases/computer-use)

## Main control surfaces

### 1. Creation and configuration

The application creating a sandbox selects a template and can supply runtime options such as timeout, environment variables, network policy, and volume mounts. Templates define the machine’s prepared environment: base image, installed packages, copied files, work directory, user, and startup commands. [Template definition](https://docs.e2b.dev/template/defining-template)

This divides configuration into two stages:

- **Template-time:** what software and files the environment starts with.
- **Sandbox-time:** how a particular instance runs—for example, its timeout, network rules, and mounted data.

API keys authenticate the developer’s SDK or CLI calls. Separately, direct calls to the sandbox controller use a sandbox access token; current SDKs enable secured access by default (default from SDK v2.0.0, not disableable from v2.51.0; custom templates built before envd v0.2.0 need a rebuild). [API key](https://docs.e2b.dev/api-key), [Secured access](https://docs.e2b.dev/sandbox/secured-access)

### 2. Execution

A sandbox can run commands, code, and interactive or background processes. The application decides what to execute and what results to return to its user. E2B provides the execution environment and interfaces; it does not supply the model or agent logic itself. [E2B documentation](https://docs.e2b.dev/), [Commands](https://docs.e2b.dev/commands)

Templates can also start services automatically. Their configured start and readiness commands let the sandbox launch a process and indicate when it is ready. [Template start and ready commands](https://docs.e2b.dev/template/start-ready-command)

### 3. Network policy

**Outbound access is enabled by default.** The creator can disable it entirely or provide fine-grained allow/deny rules. Rules can use IP addresses and CIDR blocks; domain allowlists are supported for HTTP on port 80 and TLS on port 443. Domain rules have limits: they rely on HTTP Host or TLS SNI inspection and do not cover UDP-based QUIC/HTTP/3 or arbitrary ports in the same way. Domains are allowed only in `allowOut`, not in deny lists, so using a domain also requires denying other traffic in `denyOut` (for example `0.0.0.0/0`); allow rules take precedence over deny rules. Allowing a domain also auto-allows 8.8.8.8 for DNS, which opens all traffic to that IP, and a denied TCP connection can appear open from inside the sandbox. [Internet access and network rules](https://docs.e2b.dev/network/internet-access)

Outbound filtering and inbound service exposure are separate controls:

- **Egress:** whether code inside the sandbox can reach external destinations.
- **Ingress:** whether external callers can reach services listening inside it.

A sandbox port can be exposed through a public URL. **By default, anyone who knows that URL can reach the service.** Set `allowPublicTraffic: false` to require the per-sandbox traffic token. Treat an unrestricted URL as sensitive, especially if the service can execute code. [Public URLs](https://docs.e2b.dev/network/public-url), [Restricting public access](https://docs.e2b.dev/network/restrict-public-access)

For organizations that need their own egress path, E2B documents routing TCP traffic through a customer-operated SOCKS5 proxy. Its documentation says the configured filtering runs first and proxy failure is closed rather than falling back to direct egress; UDP traffic is not tunneled. [Bring your own proxy](https://docs.e2b.dev/network/byop)

### 4. Credentials and identity

There are two documented approaches:

- **Environment variables:** convenient, but readable by code running in the sandbox if injected there.
- **E2B Secrets:** store a credential with E2B and reference it in an outbound network rule. The egress proxy inserts the value into matching HTTPS requests, so the secret value is not placed in the sandbox or returned by secret reads and lists.

Secrets can be rotated or deleted. E2B cautions that the destination receiving an injected credential is trusted with it; the destination could expose it in a response. For short-lived, per-sandbox credentials, E2B also documents workload identity (private beta; access must be requested from E2B support; up to 5 tokens per sandbox). [Secrets overview](https://docs.e2b.dev/secrets), [Workload identity](https://docs.e2b.dev/iam/workload-identity)

### 5. Storage and data

The sandbox’s own filesystem persists when the sandbox is paused and is included in full snapshots. E2B also documents **Volumes**, which are storage independent of a sandbox and can be mounted across sandboxes. The documentation currently marks volumes as **private beta** and notes limitations including file locking, many-small-file performance, and ownership behavior. [Sandbox persistence](https://docs.e2b.dev/sandbox/persistence), [Volumes](https://docs.e2b.dev/volumes)

Cloud-bucket integrations are also listed in the docs. These let workloads access external object storage; they are an integration path, not the same thing as the sandbox’s local filesystem. [Cloud buckets](https://docs.e2b.dev/storage/cloud-buckets)

### 6. Lifecycle and persistence controls

A sandbox can be created, connected to, paused, resumed, snapshotted, forked, or killed. Its timeout can be set at creation and changed while it is running. Depending on lifecycle settings, timeout expiry can kill or pause the sandbox. [Sandbox lifecycle](https://docs.e2b.dev/sandbox)

The distinction between persistence options matters:

- **Pause/resume** suspends a sandbox and later restores that same sandbox, including its filesystem and memory. The docs say paused sandboxes are retained indefinitely until explicitly killed.
- **Snapshot/fork** captures a point in time and can create multiple new sandboxes from that state. Snapshotting briefly pauses the original and drops active connections such as WebSockets, PTYs, and command streams. [Persistence](https://docs.e2b.dev/sandbox/persistence), [Snapshots](https://docs.e2b.dev/sandbox/snapshots)

### 7. Monitoring and event reporting

E2B exposes timestamped CPU, memory, and disk metrics, documented as collected every five seconds. It can also export metrics and logs over OTLP, and lifecycle webhooks can notify an external endpoint about sandbox events. [Metrics](https://docs.e2b.dev/sandbox/metrics), [OTel export](https://docs.e2b.dev/sandbox/otel-telemetry-export), [Lifecycle webhooks](https://docs.e2b.dev/sandbox/lifecycle-events-webhooks)

## Limits and deployment choices

Published limits depend on plan. The current docs list Hobby sandboxes at up to **1 hour continuous runtime**, **20 concurrent sandboxes**, and up to **8 vCPUs / 8 GiB memory**; Pro lists up to **24 hours**, **100–1,100 concurrent sandboxes**, and higher resource ceilings. Pausing and resuming resets the continuous-runtime window. Enterprise limits are custom. [Billing and limits](https://docs.e2b.dev/billing)

E2B offers its managed cloud and BYOC deployments, and its site also lists E2B Embed. E2B Cloud runs on Google Cloud in US, EU and APAC regions. BYOC runs on AWS, GCP and Azure: E2B operates the control plane, the data plane runs in your VPC, and it requires the Enterprise plan. E2B Embed is the self-hosted option: open source (Apache-2.0), the full stack on one Firecracker node (Linux x86-64 with KVM), installed via Docker Compose, Terraform (AWS/GCP) or Kubernetes. A “Private cloud” option is listed as in development. The managed service documentation and deployment claims should be checked against the specific plan and contract, particularly where region, compliance, or data-residency requirements matter. [E2B deployment overview](https://e2b.dev/), [Enterprise](https://e2b.dev/enterprise)

## Practical security reading

The microVM is an isolation boundary, but the sandbox is still designed to run code with broad capabilities **inside its own guest**. The security posture therefore depends heavily on configuration and application design:

1. **Restrict egress** for untrusted workloads; default internet access is on.
2. **Restrict public ingress** when exposing a service; the URL is public by default.
3. **Avoid putting high-value credentials in guest environment variables** when proxy-injected secrets or workload identity fit the use case.
4. **Keep the E2B API key in trusted application infrastructure**, not in code the sandbox executes.
5. **Set a timeout and explicitly kill sandboxes** when finished; paused sandboxes persist until killed.
6. **Treat snapshots and mounted storage as data-bearing artifacts** because they preserve or share workload state.

Those recommendations follow from E2B’s documented defaults and controls; they are an operational interpretation, not a claim that every deployment has identical security settings.