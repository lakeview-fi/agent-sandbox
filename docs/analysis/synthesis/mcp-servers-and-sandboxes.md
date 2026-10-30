# MCP servers and sandboxes

Where an MCP server runs decides which control applies to it. This note covers three placements for an agent that runs inside a Docker Sandbox (`sbx` v0.50) or an OpenShell sandbox (0.1.5): (a) the server inside the sandbox, (b) outside the sandbox on the same host, (c) on another instance or a web URL.

Status: current-state analysis (October 30, 2026), compiled from the repo docs and the official Docker, OpenShell and Codex pages. **Nothing here was run on a sandbox.** Claims marked *(unverified)* were not confirmed by the repo or an official page; test them before relying on them. Harness differences (Claude Code, Codex, Pi) are in [harness/](../harness/index.md).

## Summary

| | (a) Inside the sandbox | (b) Outside, same host | (c) Remote or web URL |
|---|---|---|---|
| Contained by the sandbox | Yes, like any guest code | No. Runs with the host user's authority | The server is not; its traffic from the guest is |
| Control point | Image contents; shared egress policy | Network rule to the host, or Docker's MCP gateway | Egress rule per host; gateway or provider for credentials |
| Tool-level filtering | None (stdio is invisible to Cedar and APF) | Docker: gateway plus paid AI Governance. OpenShell: `protocol: mcp` rules | Same two mechanisms |
| Credential exposure | Guest holds it unless proxy-injected | Route A: guest holds it. Docker gateway: host holds it | Docker gateway: host holds it. OpenShell provider: placeholder (static token) |
| Main risk | Shared allowlist; tampered MCP config | Confused deputy: a host shell or file tool is a sandbox escape | Exfiltration through tool arguments; third-party trust |
| Recommended | Default choice for untrusted servers | Only with a narrow, authenticated API; avoid on OpenShell | Docker gateway with `--static-mcp`; OpenShell exact-host `protocol: mcp` endpoint |

Two facts hold in every scenario:

- **The harness sandboxes do not cover MCP.** Claude Code's and Codex's own sandboxes exclude MCP servers ([claude-code-analysis.md](../harness/claude-code-analysis.md), [codex-analysis.md](../harness/codex-analysis.md)). The outer sandbox is what bounds an agent that runs wholly inside it.
- **Inside sbx the agent runs with permission prompts bypassed** ([GUIDE.md](../../../.claude/skills/develop-sandbox/docker/GUIDE.md)), so MCP tool-approval prompts do not protect you. Prompt injection can drive any reachable tool without a human.

## Docker's MCP gateway in one paragraph

The repo's other docs describe MCP only as host-run servers and MCP Cedar policy ([docker-agent-sandbox.md](../execution/docker-agent-sandbox.md)). Docker also ships an experimental per-sandbox gateway: servers are registered on the host with `sbx mcp add <name> --url <url>` or `--command <cmd>`, and attached with `sbx run ... --static-mcp a,b` or `sbx mcp load <name> --sandbox <sb>`. The agent sees one gateway endpoint. Header secrets use a placeholder (`--header 'Authorization: Bearer ${key}'` plus `sbx secret set mcp:<server>:key`), and OAuth runs on the host, so the token stays in the host credential store. Without `--static-mcp` the gateway exposes `mcp-find`, `mcp-add` and `mcp-config-set`, which let the agent attach servers itself. Always use `--static-mcp` or explicit `load`. Cedar tool-level policy needs the paid AI Governance tier. Sources: [MCP gateway](https://docs.docker.com/ai/sandboxes/mcp-gateway/), [MCP policies](https://docs.docker.com/ai/sandboxes/governance/access-controls/mcp/).

## (a) Server inside the sandbox

A stdio server started from the agent's own MCP config (`.mcp.json`, Codex `config.toml`, Pi `.pi/mcp.json`) runs in the guest. Neither the repo nor the official pages describe this case; the analysis follows from how image, network policy and credentials work.

- **Install:** bake a pinned server into the kit image (sbx) or the sandbox image (OpenShell). Avoid `npx`/`uvx` at runtime: it pulls unpinned code and needs registry egress.
- **Egress:** sbx policy is per sandbox, so **the agent and the server share one allowlist**. OpenShell scopes rules per binary, but a Node server runs as `/usr/local/bin/node`, the same binary as an npm-installed Claude Code or Pi ([policy.yaml](../../../.claude/skills/develop-sandbox/openshell/templates/policy.yaml)). To separate them, run the server under a different binary (a Python server, or a native `claude`). Glob matching of binaries is *(unverified)*.
- **Governance gap:** stdio `tools/call` traffic never reaches Docker's Cedar policy or OpenShell's `protocol: mcp` rules and APF ([nvidia-openshell-analysis.md](../execution/nvidia-openshell-analysis.md)). Do not claim they cover an in-guest server.
- **Credentials:** best is a host-held secret injected on egress (sbx) or an OpenShell provider placeholder. Whether either binds to an arbitrary non-LLM host is *(unverified)*. An env var in the guest is the weakest option. A proxy hides the value, not the authority: any guest process can still use it toward the allowed host.
- **Reach:** agent and server share files, env and workspace with no boundary between them. In return, a malicious server cannot reach host files, host network or the host credential store.
- **Risks:** prompt injection and tool poisoning pass straight through; every allowed host is an exfiltration channel, write-capable SaaS APIs most of all; in direct-mount mode the agent can edit `.mcp.json`, `config.toml`, `.pi/mcp.json` or the kit definition and change what later sessions run.
- **Do:** prefer clone mode (sbx); give the server's upstream a narrow rule (method/path on sbx, `read-only` on OpenShell); review MCP-config diffs before merging; add a smoketest step for the server's egress, allowed and denied.

## (b) Server outside the sandbox, same host

| | Docker route A: direct HTTP | Docker route B: MCP gateway | OpenShell |
|---|---|---|---|
| Reach | `http://host.docker.internal:<port>`; the proxy maps it to host `localhost`, so a loopback-only server works | Guest talks only to the gateway. Whether the gateway reaches host-localhost URLs is *(unverified)* | Loopback is never allowed. Workaround: bind non-loopback, reach `host.openshell.internal`, list in `allowed_ips`. That exposes the server to the LAN |
| Rule | Name `localhost:<port>` (a `host.docker.internal` rule does not match); method and path limits; unlisted routes get 403 ([GUIDE.md](../../../.claude/skills/develop-sandbox/docker/GUIDE.md)) | Cedar via AI Governance. A direct guest connection bypasses it | `protocol: mcp` filters by method and tool name per binary; no argument matching, no stdio, no response parsing |
| Granularity | MCP streamable HTTP is `POST /mcp` for every call, so path rules cannot tell tools apart: all or nothing | Tool level, with Governance | Tool name only; APF adds argument checks |
| Token | Sits in the guest | Stays on the host | Provider injection for a host-alias endpoint is *(unverified)* |
| stdio | n/a | Runs on the host with full host filesystem and network reach, by design | No bridge. Run it in the sandbox (a), or wrap it in a stdio-to-HTTP bridge (unverified) |

NVIDIA's NemoClaw, a separate product built on OpenShell, rejects host aliases and plain `http` for authenticated MCP ([docs](https://docs.nvidia.com/nemoclaw/user-guide/openclaw/manage-sandboxes/set-up-mcp-servers)). That suggests NVIDIA treats host-alias MCP as unsafe.

**Main risk: confused deputy.** The server acts with the host user's files, tokens and network. A `run_command`, `read_file` or `write_file` tool on it is a sandbox escape, drivable by prompt injection with no approval. A tool that writes `~/.bashrc`, git hooks, CI files or `.mcp.json` gives later persistence on the host. One server shared by several sandboxes links them unless it scopes data per caller. In direct-mount mode the agent can edit the host repo's `.mcp.json`, and the host then runs it.

**Do:**
1. Prefer (a) or (c) unless the server needs host state. Then give it a narrow API with no shell, file or path tools, the same rule as [host-guest-file-sharing](host-guest-file-sharing-and-version-control.md).
2. Docker: use route B with `--static-mcp` and header secrets in `sbx secret`. Use route A only for non-MCP REST, where path rules work.
3. Require authentication on the server, bind to loopback, run it as a low-privilege user or in its own container.
4. OpenShell: avoid host MCP for now.

## (c) Server on another instance or a web URL

With the whole agent in the sandbox, remote MCP traffic is ordinary egress, so the sbx proxy or the OpenShell supervisor sees it. This is unlike the harness-native sandboxes, which exclude MCP.

| | Docker Sandboxes | OpenShell |
|---|---|---|
| Direct | Host, port, method and path rules (`allowed-hosts.txt`). No MCP semantics. | Endpoint with `protocol: mcp`, `path: /mcp`, `rules.allow` and `deny_rules` by method and tool, bound to one binary. `mcp.versions` defaults to `2025-11-25` only. |
| Brokered | Gateway: `sbx mcp add <name> --url`, `--static-mcp`; Cedar applies | No gateway. Supervisor proxy, provider credentials, optional APF |
| Credential | Gateway OAuth or header placeholder: the guest holds nothing. `sbx secret set <service>` covers a fixed service list only | Provider bound to the MCP host: placeholder for a static bearer. OAuth refresh in a provider is *(unverified)* |
| Logs | `sbx policy log`; no tool arguments | `openshell logs <sb> --source sandbox` (not `--level warn`); no tool arguments |

- **Do not allow the MCP host directly as well as through the gateway:** the agent could bypass the gateway.
- **Wildcards:** pin exact hosts. OpenShell wildcards open a DNS-label exfiltration channel. Under sbx Balanced or Locked Down, an unmatched host is held for approval, so approval fatigue can open an MCP host. Redirect handling is undocumented for both *(unverified)*.
- **LAN servers:** sbx needs `--skip-ssrf-check` (pin the host); OpenShell needs `allowed_ips` with a narrow CIDR, and every resolved address must be inside it.
- **OAuth login from the guest:** the callback listens on localhost inside the guest, so the host browser cannot reach it without port forwarding, and `claude -p` cannot finish the flow. Codex has `mcp_oauth_callback_port` and `mcp_oauth_callback_url`. Claude Code and Pi options are *(unverified)*. On sbx, do OAuth on the host through `sbx mcp add`. On OpenShell there is no equivalent: either accept a guest-held token and record it in `DECISIONS.md`, or use a static-token provider.
- **Risks:** tool arguments (`create_issue`, `write_file`, search queries) are an outbound data channel, and OpenShell cannot match them; a proxied credential hides the token but not the authority, so scope the token at the service; a server can change its tools after approval (rug pull) and the responses pass unparsed; workspace content goes to a third party under its terms.
- **Do:** least-privilege, short-lived, per-project tokens; deny write tools by name; review the tool list each session; record every server, tool set and credential in `DECISIONS.md`.

## Recommendations across the three

1. **Untrusted server or untrusted data:** run it in the sandbox (a), pinned in the image.
2. **Server that needs host state:** (b) with a narrow authenticated API, on Docker only, via the gateway.
3. **SaaS or shared server:** (c) through the Docker gateway with `--static-mcp`; on OpenShell an exact-host `protocol: mcp` endpoint with `enforcement: enforce`.
4. Treat every MCP response as untrusted input. Record each server in `DECISIONS.md` and add negative smoketests: a denied tool or route, no guest reach without the rule, another sandbox blocked.

## Inconsistencies in the existing docs

Found while compiling this note. Wordings corrected in the source files:

- GUIDE.md said sbx cannot inject a custom header for a host. Now scoped to network rules; gateway servers can.
- PLATFORM-NOTES.md cited an `mcp.servers.command` key in `sbxenv.yaml` that neither the [config reference](../../guides/how-to/config-file-reference.md) nor the Docker pages confirm. Now flagged *(verify)*.
- The host-guest note said behavior for unlisted methods is "not spelled out". Now cites the 403 seen in the GUIDE.md trial.
- "Local stdio MCP servers run on the host" ([risk scenarios](coding-agent-risk-scenarios-and-sandbox-mitigations.md), [docker-agent-sandbox.md](../execution/docker-agent-sandbox.md)) is now scoped to gateway-registered servers.
- [claude-code-analysis.md](../harness/claude-code-analysis.md) "MCP servers ... run outside it" describes Claude Code's own host sandbox. A clarification now says it does not apply inside a guest.

Still open:

- No repo doc covers `--skip-ssrf-check`, and the skills and templates do not yet use `sbx mcp add/load` or `--static-mcp`.
- OpenShell "deny-by-default" is correct for unlisted hosts, but a listed endpoint's `enforcement` defaults to `audit` (allow and log). The templates set `enforce`; custom policies must too.
- The Claude kit allowlist already contains `mcp-proxy.anthropic.com:443` (the claude.ai connector path). Whether it lets connectors reach SaaS data without a per-server rule is *(unverified)* and needs a decision.

## Open questions

- Does the sbx gateway's upstream traffic pass the sandbox network policy, or leave from the host? Is gateway mode on by default (some sources mention `SBX_MCP_ENABLE`)?
- Can `sbx secret` or a kit credential bind a secret to an arbitrary non-LLM host? Can an OpenShell provider hold MCP OAuth with refresh?
- Does OpenShell binary matching accept globs?
- Does Pi support MCP natively, or only through an extension?
- Which MCP protocol revision does each client negotiate against OpenShell's `mcp.versions`?
