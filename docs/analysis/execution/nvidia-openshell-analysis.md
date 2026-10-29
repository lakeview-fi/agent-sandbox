# NVIDIA OpenShell: features and how they’re controlled

**OpenShell is a runtime and control plane for running AI agents in isolated sandboxes.** Its main security idea is to enforce permissions outside the agent process: the gateway manages configuration and access, while a supervisor and sandbox runtime apply controls to each workload.

This summary follows NVIDIA’s current documentation as of **October 29, 2026**. The docs are actively changing, and some pages describe older behavior; I call out a notable example below.

## Components and responsibilities

| Component | What it does | How it is controlled |
|---|---|---|
| **CLI, SDK, and TUI** | Create and manage sandboxes, policies, providers, and logs. | User authentication and gateway authorization determine which operations are available. |
| **Gateway** | Control plane for sandbox lifecycle, policy and settings delivery, providers, credentials, identity, and relays. | Configured authentication, roles, workspace membership, and gateway settings. |
| **Supervisor** | Enforces controls for each sandbox, launches the agent, handles policy-controlled network traffic, credentials, logging, and gateway communication. | Receives desired configuration from the gateway and applies it locally. |
| **Sandbox runtime** | Runs the agent under process and filesystem restrictions, with outbound traffic routed through the supervisor’s network proxy. | Runtime-specific compute driver and the sandbox’s effective policy. |

OpenShell documents compute drivers for **Docker, Podman, Kubernetes, and MicroVM**, with driver-specific options for resources such as CPU, memory, and GPU. Driver choice and configuration are gateway-level settings. [How OpenShell Works](https://docs.nvidia.com/openshell/latest/about/how-it-works) · [Sandbox Compute Drivers](https://docs.nvidia.com/openshell/latest/how-it-works/sandboxes/runtimes)

### Compute driver changes the isolation and operating-cost comparison

Do not treat every OpenShell driver as the same isolation boundary. The **Docker driver creates containers on the gateway host and uses its Docker daemon**, so it shares the host kernel; enabling bind mounts can also expose host paths and weaken filesystem isolation. The **Podman driver is intended for rootless local/workstation use**. The **MicroVM driver creates one lightweight VM per sandbox**, using Hypervisor.framework on macOS or KVM on Linux, and is opt-in. Kubernetes runs workloads in an operator-provided cluster. Current OpenShell releases configure one compute driver per gateway, so compare separate gateway deployments when comparing Docker, MicroVM, or Kubernetes. Docker Sandboxes `sbx`, by contrast, gives each local agent a microVM and a private Docker Engine. A like-for-like local VM comparison is therefore `sbx` versus OpenShell MicroVM; OpenShell Docker is a separate, shared-kernel option. Compute, virtualization, cluster, storage, gateway operations, and model use remain deployment costs even where the OpenShell software is Apache-2.0. [OpenShell compute drivers](https://docs.nvidia.com/openshell/latest/how-it-works/sandboxes/runtimes) · [Docker Sandboxes isolation](https://docs.docker.com/ai/sandboxes/security/isolation/)

## The main policy controls

A sandbox policy is YAML with up to five substantive sections. OpenShell denies outbound network access unless policy allows it. [Sandbox Policies](https://docs.nvidia.com/openshell/dev/how-it-works/policies/overview) · [Policy Schema](https://docs.nvidia.com/openshell/latest/how-it-works/policies/schema)

| Policy section | Controls | Where it takes effect |
|---|---|---|
| `filesystem_policy` | Which paths are readable or writable; optionally adds the work directory as read-write. Unlisted paths are inaccessible. | At sandbox startup, enforced using the kernel’s Landlock LSM. |
| `landlock` | Whether startup fails if filesystem enforcement cannot be applied, or proceeds without those rules. | At sandbox startup. |
| `process` | The user and group the agent runs as. | When the sandbox is created. |
| `network_policies` | Which binaries can reach which destinations, and—in supported protocols—which requests they can make. | Dynamically; rules can be updated while the sandbox runs. |
| `network_middlewares` | Extra inspection, blocking, or transformations for selected traffic destinations. | Dynamically, for middleware registered with the gateway. |

**Filesystem and process controls are static:** changing them requires recreating the sandbox. Network policies and middleware are dynamic and can be updated in a running sandbox. Landlock’s `hard_requirement` makes startup fail if enforcement cannot be established; `best_effort` allows startup without the filesystem rules in that failure case. Both modes require Landlock ABI v3 or later. [Policy Schema](https://docs.nvidia.com/openshell/dev/how-it-works/policies/schema)

## Network controls: destination, binary, and request

Each network rule combines a list of **destinations** with a list of **binaries**. Within one rule, each listed binary can reach each listed endpoint, so separate rules are needed when tools should have different reach. OpenShell identifies the executable that actually opens the connection; that may be an interpreter rather than the command name—for example, Python may make a request initiated by `pip`. [Network Rules](https://docs.nvidia.com/openshell/dev/how-it-works/policies/network-rules)

For endpoints using a supported inspection protocol, policy can go beyond host and port:

- **REST:** HTTP methods, paths, and query parameters.
- **WebSocket:** upgrade requests and client text messages.
- **GraphQL:** operation type, name, and top-level fields.
- **MCP:** method and tool name.
- **JSON-RPC:** method name.
- **TCP:** destination access, without request-level inspection.

An endpoint can use `enforcement: audit` to log rule violations while allowing them, or `enforce` to block them. **Audit mode applies to network and request rules; it does not bypass middleware denials.** Matching rules are cumulative rather than an ordered firewall list, and a matching deny takes precedence over an allow. Private-address restrictions and `allowed_ips` provide additional destination controls. [Network Rules](https://docs.nvidia.com/openshell/dev/how-it-works/policies/network-rules)

### MCP-specific controls

OpenShell has MCP-aware rules within `network_policies`: set an endpoint to `protocol: mcp`, then allow or deny MCP methods and tool names for the listed binary and server endpoint. This is an egress/network policy feature, not a separate MCP server registry or policy plane. Current rules inspect sandbox-to-server MCP Streamable HTTP requests; tool arguments cannot yet be matched, and server responses/SSE messages are not parsed for MCP policy. Local stdio MCP servers do not traverse this network enforcement path. [OpenShell MCP policy reference](https://docs.nvidia.com/openshell/latest/how-it-works/policies/schema) · [MCP network-rule examples](https://docs.nvidia.com/openshell/dev/how-it-works/policies/network-rules)

APF adds a distinct authorization check for MCP `tools/call` requests that OpenShell routes through APF middleware. Its Cedar capability grants authorize named tools, can constrain arguments, and are required for every MCP tool call APF evaluates. APF currently evaluates `tools/call` in HTTP request bodies; it does not govern the full MCP protocol surface or local tool execution. In an APF deployment, these capability grants are part of the signed bundle, while OpenShell’s MCP endpoint policy remains the Layer 1 network perimeter. [APF capability grants](https://docs.nvidia.com/agent-policy-fabric/author-policies/capability-grants) · [APF support and compatibility](https://docs.nvidia.com/agent-policy-fabric/about/support-and-compatibility)

## Credentials and inference

**Providers** hold credentials as gateway-managed entities. Provider profiles declare credentials and the endpoints and binaries associated with them; a provider can be attached to or detached from a sandbox. The workload receives an opaque placeholder rather than the underlying secret, and OpenShell only supplies a provider credential at destinations permitted by that provider’s profile or an explicit binding. [Providers](https://docs.nvidia.com/openshell/dev/how-it-works/providers/overview) · [Manage Providers](https://docs.nvidia.com/openshell/latest/how-it-works/providers/overview)

**Inference behavior depends on the OpenShell version and configuration.** An older, still-indexed guide describes a gateway-managed `https://inference.local` route that strips caller credentials and injects configured upstream credentials. However, the current inference guide says OpenShell removed the workspace-global managed route and `openshell inference` commands; under the documented current path, inference uses an attached provider and the native provider endpoint, with policy controlling access. Don’t assume `inference.local` applies to your installation without checking its version’s docs. [Current Inference Guide](https://docs.nvidia.com/openshell/latest/how-it-works/inference) · [Older Inference Routing Guide](https://docs.nvidia.com/openshell/v0.0.116/sandboxes/inference-routing)

## Middleware, policy review, and live changes

**Supervisor middleware** can inspect, deny, or transform admitted traffic before OpenShell injects provider credentials. A policy selects middleware by destination host and order, and sets failure behavior: `fail_closed` blocks affected traffic on middleware failure; `fail_open` skips a failed stage. Current documentation describes HTTP request and client WebSocket text-message support, with some traffic—such as WebSocket binary messages—not inspected. [Supervisor Middleware](https://docs.nvidia.com/openshell/latest/extensibility/supervisor-middleware)

**Policy Advisor** lets an agent submit a narrow proposed rule after a denial. The proposal remains subject to operator review by default; the agent cannot approve its own proposal. The advisor runs a risk check, including checks for credential reach expansion and link-local or metadata access. Its enablement and approval behavior are settings, while approvals and rejections are operator decisions. [Policy Advisor](https://docs.nvidia.com/openshell/latest/how-it-works/policies/advisor)

**Policy Prover** checks whether a candidate policy exceeds a boundary supplied for comparison. It is a verification aid, not proof that a policy is safe for a task or that a running sandbox enforces it. [Policy Prover](https://docs.nvidia.com/openshell/latest/how-it-works/policies/prover)

For live network changes, the supervisor reloads the policy and closes connections opened under the old rules so clients reconnect and are checked against the new policy. If a policy reload fails, the gateway’s `policy_validation_failure_mode` controls whether traffic is blocked (`fail_closed`, the default) or the last valid policy stays active (`retain_last_valid`). [Manage Sandbox Policies](https://docs.nvidia.com/openshell/dev/how-it-works/policies/manage-policies)

## Fleet and administrator controls

A **global policy** lets an administrator apply one complete policy to every sandbox on a gateway. It replaces sandbox-level policy, suppresses provider-contributed network rules, and blocks sandbox policy changes until removed. This is a broad override, not an additional per-sandbox restriction. [Sandbox Policies](https://docs.nvidia.com/openshell/dev/how-it-works/policies/overview)

For gateway access, the documented OIDC setup validates token signature, issuer, audience, expiry, roles, and optionally scopes. Authorization also considers workspace membership; platform-scoped operations require the admin role, while workspace-scoped operations require an appropriate user role and membership. Supervisors authenticate separately with gateway-issued tokens scoped to their sandbox. [Gateway Authentication](https://docs.nvidia.com/openshell/latest/how-it-works/gateways/authentication)

## Audit and operational visibility

OpenShell records network allows and denials, policy changes, and lifecycle events in sandbox logs. Operators can stream recent logs through the CLI or TUI; the gateway’s pushed log buffer is bounded and not persisted across gateway restarts, so durable retention requires collecting the sandbox log files or exporting structured OCSF JSON to an external system. [Accessing Logs](https://docs.nvidia.com/openshell/latest/observability/accessing-logs)

## Practical reading of the feature set

The controls are split across several places:

1. **Gateway settings and identity** control who can administer sandboxes and which platform integrations are available.
2. **Per-sandbox policy** controls filesystem, process identity, network access, and middleware.
3. **Provider profiles and attachments** control where credentials can be used.
4. **Runtime drivers** control how and where the workload is provisioned, including supported resource and GPU options.
5. **Logs, advisor, and prover** support review and oversight; they do not replace policy enforcement.

The key operational distinction is that filesystem and process restrictions are established at startup, while network policy and middleware can change live. Provider rules can add network access to a sandbox’s effective policy, so inspect the **effective** policy—not only the user-authored base policy—when assessing what a sandbox can reach. [Sandbox Policies](https://docs.nvidia.com/openshell/dev/how-it-works/policies/overview)

## NVIDIA Agent Policy Fabric (APF)

**NVIDIA Agent Policy Fabric is a governance layer that integrates with OpenShell.** OpenShell remains the runtime and enforcement boundary; APF supplies a signed, centrally managed policy and evaluates selected requests that OpenShell routes to it. The agent does not call APF directly, and APF does not reach into the sandbox. The current APF documentation describes OpenShell as its integrated enforcement point; additional enforcement points are an extension direction, not a shipped integration today. [APF Overview](https://docs.nvidia.com/agent-policy-fabric) · [Architecture](https://docs.nvidia.com/agent-policy-fabric/about/architecture)

### What APF adds

- **Signed policy bundles.** Enterprise policy is authored, reviewed, compiled, and signed outside the APF services. A bundle can include the OpenShell sandbox perimeter, approved provider profiles, Cedar policy rules, capability grants, annotators, effects, and findings. The policy service verifies the signature, member digests, validity window, and monotonically increasing revision before serving projections. It rejects tampering and rollback.
- **Policy projection at admission.** APF’s OpenShell gateway interceptor replaces a caller-supplied sandbox policy with the signed projection, attaches bundle and document provenance, then verifies that provenance and policy contents again before OpenShell commits the sandbox. A missing or invalid projection fails admission.
- **Per-request decisions and transformations.** For requests routed through APF middleware, the policy gateway enriches request data, evaluates Cedar rules, and returns allow or deny plus permitted effects such as body or header changes and findings. Evaluation errors fail closed on the OpenShell path. APF runs before provider credentials are injected, so its middleware does not see the injected secrets.
- **Capability grants for MCP calls.** An MCP `tools/call` request reaching APF is denied unless a matching capability grant permits the named tool; grants can constrain arguments. This adds an application-level tool permission check on top of OpenShell’s filesystem and network perimeter.
- **Provider governance and audit provenance.** APF can project approved provider profiles and refuse unmanaged profile or policy changes. Admission annotations and decision logs identify the bundle revision and digest; component audit records use correlation IDs to connect events across policy verification, admission, and request evaluation. [Policy Model](https://docs.nvidia.com/agent-policy-fabric/author-policies/policy-model) · [Capability Grants](https://docs.nvidia.com/agent-policy-fabric/author-policies/capability-grants) · [Enforcement Coverage](https://docs.nvidia.com/agent-policy-fabric/security/enforcement-coverage-and-limitations)

### How it is attached to OpenShell

APF registers two OpenShell extension points, both served by `apf-policy-gateway`:

| OpenShell hook | APF adapter | Role |
|---|---|---|
| Gateway interceptor | `apf-openshell-interceptor` | Governs sandbox admission and selected control-plane changes; injects and validates the signed sandbox policy. |
| Supervisor middleware | `apf-openshell-middleware` | Evaluates each HTTP request to hosts selected by the sandbox’s `network_middlewares` policy, before credential injection. |

Both extension registrations must be configured in the OpenShell gateway and the gateway restarted. The signed sandbox policy must select the APF middleware for each destination that needs request-level review. APF’s interceptor registration is configured to fail closed. Agent-authored policy proposals and direct policy changes are disabled or refused so they cannot create a path around the signed bundle. APF docs describe protocol negotiation as a startup check; incompatible or unavailable required adapters prevent the OpenShell gateway from starting. [OpenShell Integration](https://docs.nvidia.com/agent-policy-fabric/integrations/openshell) · [Add APF to OpenShell](https://docs.nvidia.com/agent-policy-fabric/get-started/add-apf-to-openshell)

Policy updates follow an offline publish flow: edit the documents, increment `policy_revision`, sign and verify the bundle, then publish it to the policy service. The service verifies the new bundle and the gateway rebuilds its evaluator. This can update request decisions for running sandboxes without recreating them. Updating the sandbox’s projected perimeter is a separate refresh step and is documented as opt-in; it requires the APF-to-OpenShell gateway connection. [Update Policies](https://docs.nvidia.com/agent-policy-fabric/manage-policy-bundles/update-policies)

### Important limits and deployment considerations

- **APF governs only traffic OpenShell sends through its hooks.** The middleware is selected by host in the sandbox policy; traffic not routed to that middleware does not get APF’s per-request Cedar decision. Keep OpenShell’s network perimeter narrow and explicit.
- **Not every action is evaluated.** Current documentation centers on HTTP request evaluation at `PRE_CREDENTIALS`; the OpenShell middleware path can evaluate MCP tool calls carried in HTTP request bodies. APF does not generally govern local tool execution or all agent actions. Tool invocation and credential handling remain outside APF’s own policy layer.
- **Fail-closed depends on the configured hook and service.** Admission is documented as fail-closed, and request evaluation errors deny. The deployment must register APF with the intended failure policy and ensure required listeners are reachable from the gateway and sandbox supervisors.
- **Some integrations are explicitly limited.** Provider-profile reconciliation and automatic refresh of already-running sandboxes are documented as limited/opt-in. The APF-to-OpenShell gateway connection currently has no client TLS configuration or client credentials; APF documentation advises using it only where the OpenShell gateway accepts such calls, such as a loopback development setup. This is a material production deployment constraint to verify against the exact release.
- **Policy semantics need careful authoring.** APF’s policy model says ordinary HTTP requests reaching APF are allowed unless a `forbid` rule fires; default deny specifically applies to MCP tool calls without a capability grant. Therefore retain a restrictive OpenShell perimeter and write explicit Cedar forbids where APF should deny ordinary requests. An `escalate` verdict is recorded as advisory and does not currently trigger a human review workflow.
- **Version status is important.** APF’s Dev documentation says its `main` branch is built against OpenShell `v0.1.3`; check the published compatibility matrix and release notes before treating these capabilities as stable or assuming compatibility with another OpenShell release. [Support and Compatibility](https://docs.nvidia.com/agent-policy-fabric/about/support-and-compatibility) · [Policy Model](https://docs.nvidia.com/agent-policy-fabric/author-policies/policy-model)

In short, APF changes OpenShell’s policy operating model from runtime-local policy management to **signed, centrally distributed policy plus request-time decisions**. OpenShell still supplies isolation and executes enforcement; APF supplies policy provenance, governance over selected control-plane operations, and content/context decisions on traffic explicitly routed through its middleware.

## Licensing and costs

As of **October 29, 2026**, the core OpenShell and APF software can be self-hosted without a per-sandbox or per-request product fee identified in their published license terms. OpenShell is Apache-2.0, and NVIDIA identifies it as open-source software; APF’s current Dev documentation also specifies Apache-2.0. This supports use and modification subject to each license’s terms, but it does not mean deployment has zero operating cost. Compute, storage, networking, support, model inference, and engineering/operations remain separate costs. [OpenShell repository](https://github.com/NVIDIA/OpenShell) · [NVIDIA software licensing FAQ](https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-software-licensing-overview-and-faq/) · [APF License](https://docs.nvidia.com/agent-policy-fabric/resources/license)

| Component | Software/license status | Costs to account for |
|---|---|---|
| **OpenShell** | Open source, Apache-2.0; no published per-sandbox charge found. | Host or cloud compute, GPU hardware if used, operations, and model/provider usage. NVIDIA AI Enterprise or paid support should be treated as separate offerings; the current OpenShell license does not require them. |
| **Agent Policy Fabric** | APF Dev documentation says Apache-2.0. No separate APF product price or hosted service fee is documented in the material reviewed. | Self-host the policy service and gateway, manage signing keys and bundles, and operate integrations/providers. Dev documentation and compatibility status mean production readiness/support costs should be assessed separately. |
| **OpenShell Slack Admin Bridge** | Slack’s sample repository publishes the bridge under MIT; its bundled OpenShell protobuf definitions remain Apache-2.0. | The bridge itself has no stated license fee. Slack offers a Free plan at $0 with up to 10 apps, which can be enough for a small deployment; paid Slack plans may be needed for retention, administration, or organization requirements. Hosting the bridge also has an operational cost. It uses OpenShell draft approvals and is not compatible as-is with APF, which refuses those approvals. [Repository license](https://github.com/slack-samples/openshell-slack-admin-bridge) · [Slack pricing](https://slack.com/pricing) |
| **ServiceNow AI Control Tower / AI Passport** | Commercial ServiceNow offerings, not part of the free OpenShell/APF code. The announced AI Passport enforcement with NVIDIA OpenShell is described as a future release, so it is not currently a turnkey APF integration. | AI Control Tower pricing is quote-based (“Contact Us for Pricing”); confirm required ServiceNow products, entitlements, and the availability/pricing of AI Passport enforcement with ServiceNow. [AI Control Tower](https://www.servicenow.com/uk/products/ai-control-tower.html) · [ServiceNow/NVIDIA announcement](https://newsroom.servicenow.com/press-releases/details/2026/ServiceNow-delivers-industry-first-personal-enterprise-agent-and-policy-enforcement-with-NVIDIA-extending-AI-governance-across-software-and-silicon/default.aspx) |

Thus the **software stack can be assembled from open-source components**, and the Slack bridge can run against Slack Free within its limits. The paid parts are optional commercial services and infrastructure rather than a documented mandatory OpenShell/APF license fee. ServiceNow is a commercial alternative with no public price in the reviewed listing. NVIDIA’s separate enterprise licensing/support may be relevant to organizations buying an enterprise AI stack, but the reviewed sources do not establish it as a prerequisite for OpenShell or APF.

## Requirements for a custom permissions Web UI

A web UI is feasible, but OpenShell-only and APF-governed deployments need different write paths. OpenShell exposes SDKs and gateway operations for sandbox, policy, workspace, and provider management. A UI could show sandbox state, base and effective policy, denials, audit events, and pending network proposals; reviewers could approve or reject proposals, or edit dynamic network policy and wait for the sandbox to load the revision. Filesystem and process changes are static and require sandbox recreation. [OpenShell SDK](https://docs.nvidia.com/openshell/latest/sdk/python) · [Policy management](https://docs.nvidia.com/openshell/latest/how-it-works/policies/manage-policies)

With APF, the UI must not approve OpenShell draft proposals or directly mutate sandbox policy: APF rejects those paths. Its policy service exposes document read/refresh operations, not a policy CRUD editor. A governed UI would author and validate policy documents, prepare a higher-revision bundle, route it for review, have a protected signing service or CI pipeline sign it, publish the immutable artifact, request/observe refresh, and report activation and propagation status. The signing key should remain outside the browser and ordinary UI backend. [APF enforcement coverage](https://docs.nvidia.com/agent-policy-fabric/security/enforcement-coverage-and-limitations) · [APF service APIs](https://docs.nvidia.com/agent-policy-fabric/reference/service-apis) · [Compile and sign](https://docs.nvidia.com/agent-policy-fabric/manage-policy-bundles/compile-and-sign)

For per-action human approval under APF, add an external approval service and expose its decision as a Policy Information Provider fact for Cedar rules. APF’s provider interface supplies facts; it does not create a request queue or approval UI. Network requests blocked by OpenShell’s perimeter also need an OpenShell policy path: APF cannot decide a request it never receives through its middleware. [Policy Information Providers](https://docs.nvidia.com/agent-policy-fabric/integrations/policy-information-providers) · [APF/OpenShell integration](https://docs.nvidia.com/agent-policy-fabric/integrations/openshell)

In either mode, use a backend-for-frontend with SSO, reviewer/admin roles, workspace scoping, concurrency-safe revisions, policy validation, clear diffs and impact warnings, and an audit trail tying each change to the actor, rationale, target sandbox or fleet, and resulting revision. Do not give browser code a broad gateway token or APF signing key. A sensible first release is read-only inventory and audit; then add OpenShell approvals for OpenShell-only deployments or signed-bundle authoring/release for APF deployments. OpenShell’s gateway already supports OIDC roles and workspace memberships, but the UI should still enforce its own user experience and authorization checks. [Gateway authentication](https://docs.nvidia.com/openshell/latest/how-it-works/gateways/authentication)
