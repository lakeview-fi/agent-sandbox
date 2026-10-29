# Codex Sandbox: features and controls

**Codex Sandbox is the execution boundary for commands the agent runs on your computer.** It limits what those commands can access—especially files and the network—so routine work can proceed within that boundary. Approval settings determine when Codex must stop and ask to cross it. These are separate controls: approval prompts don’t define the sandbox boundary, and the sandbox doesn’t decide whether a prompt appears. [OpenAI Docs: Sandbox](https://learn.chatgpt.com/docs/sandboxing) · [Agent approvals & security](https://learn.chatgpt.com/docs/agent-approvals-security)

## What it includes

- **Filesystem boundaries.** In `workspace-write`, Codex can read files and edit within its workspace. `read-only` permits inspection without edits; `danger-full-access` removes the sandbox’s filesystem and network boundaries. Writable roots can extend the places Codex may edit while retaining a sandbox.
- **Command execution under the same boundary.** The sandbox applies to spawned commands and their child processes, including tools such as Git, package managers, and test runners—not just Codex’s built-in file operations.
- **Protected paths inside writable roots.** In the default `workspace-write` mode, `.git` (including a resolved Git directory behind a pointer file), `.agents`, `.codex`, and `.aws` are read-only recursively.
- **Network controls.** Local commands have network access off by default in `workspace-write`. It can be enabled, and a network proxy can then constrain outbound destinations with allow/deny rules. The proxy is an enforcement option; configuring domain rules alone doesn’t turn it on or grant network access.
- **Platform-level enforcement.** macOS uses Seatbelt; Linux uses `bwrap`; native Windows uses its Windows sandbox, while WSL2 uses the Linux implementation. [OpenAI Docs: Sandbox](https://learn.chatgpt.com/docs/sandboxing) · [Agent approvals & security](https://learn.chatgpt.com/docs/agent-approvals-security)

## How you control it

| Control | What it governs | Common choices |
|---|---|---|
| **Sandbox mode** | What commands can access or change | `read-only`, `workspace-write`, `danger-full-access` |
| **Approval policy** | When Codex pauses before an action | `on-request`, `never`, or a granular policy |
| **Writable roots** | Which additional directories commands can edit | Add selected directories without granting unrestricted access |
| **Command network settings** | Whether commands can connect out, and optionally which destinations they can reach | Network off; network on; or network on with proxy rules |
| **Approval reviewer** | Who reviews eligible approval requests | `user` or `auto_review` |
| **Command rules** | Whether matching command prefixes are allowed, prompted, or denied | Narrow exceptions for particular commands |

The usual local **Auto** setup is `workspace-write` plus `on-request`: Codex can work inside the workspace without asking at every step, and asks when it needs to cross the configured boundary. You can change the active mode from the desktop app’s permissions control or the CLI’s `/permissions` picker. Defaults can be set in `~/.codex/config.toml`; CLI flags such as `--sandbox` and `--ask-for-approval` can set them for a run. [OpenAI Docs: Sandbox](https://learn.chatgpt.com/docs/sandboxing) · [Configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference)

For example:

```toml
sandbox_mode = "workspace-write"
approval_policy = "on-request"
approvals_reviewer = "user"

[sandbox_workspace_write]
network_access = false
```

`never` disables approval prompts, but **does not itself remove sandbox restrictions**. Full access is the combination of `danger-full-access` and `never`; it removes the sandbox and approval gates, so it is a substantial change in autonomy. For finer control, granular approval policies can keep selected request categories interactive while automatically rejecting others. [OpenAI Docs: Agent approvals & security](https://learn.chatgpt.com/docs/agent-approvals-security)

Network settings need particular care: enabling the `network_proxy` feature constrains command traffic only when command networking is already enabled. It does not control web search, browser or Computer Use activity, app/connector calls, MCP connections, cloud tasks, or Codex’s own model and authentication requests; those have separate controls. So **“commands have no network access” does not mean every Codex-connected tool is offline**. [OpenAI Docs: Agent approvals & security](https://learn.chatgpt.com/docs/agent-approvals-security)

## Local sandbox versus cloud

The local sandbox applies to command execution in the desktop app, CLI, and IDE extension. Codex Cloud runs in a separate managed environment with its own environment and network settings. Don’t assume a local permission setting carries over to cloud execution—or that local command-network rules govern tools with separate service connections. [OpenAI Docs: Agent approvals & security](https://learn.chatgpt.com/docs/agent-approvals-security)

**Practical takeaway:** For ordinary local coding, `workspace-write` with `on-request` is the documented bounded-work pattern. Add writable roots or narrowly scoped network access only when a task needs them; use full access only when you intend to remove those safeguards.