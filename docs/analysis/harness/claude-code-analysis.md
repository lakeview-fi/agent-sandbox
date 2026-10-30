# Claude Code Sandbox: features and controls

**Claude Code Sandbox** is the operating-system-enforced boundary around shell commands Claude runs locally. It can restrict which files those commands read or write and which network hosts they reach. It applies to Bash, PowerShell, Monitor commands, and the processes they launch.

It is **off by default**. The sandbox runs on macOS, Linux, and WSL2; it does not run on native Windows, where commands run unsandboxed, and WSL1 is unsupported. macOS enforcement uses Seatbelt, while Linux and WSL2 use bubblewrap. On Linux and WSL2, `socat` relays network traffic through the sandbox proxy; an optional seccomp filter adds Unix-socket blocking. [Anthropic’s sandboxing guide](https://code.claude.com/docs/en/sandboxing)

## What it includes

### Filesystem boundaries

The default policy gives sandboxed commands read and write access to the working directory, added directories, and a per-user temporary directory. They can generally **read other parts of the machine** unless a further restriction blocks those paths. That means the default sandbox does not automatically hide credentials such as SSH keys or AWS credentials.

You can tune access with:

- `sandbox.filesystem.allowWrite`, `denyWrite`, `allowRead`, and `denyRead`
- `permissions.additionalDirectories` or `--add-dir` to add working locations
- `permissions.blockReadsOutsideWorkingDirectories` to restrict reads outside working directories
- `sandbox.filesystem.disabled` to turn off filesystem isolation while keeping network isolation

The sandbox also protects important Claude Code configuration paths from writes, including project `.claude` settings, hooks, skills and agents, `.mcp.json`, and most of `~/.claude`. These protections help stop a shell command from changing configuration that Claude Code may load later. [Filesystem isolation and protected paths](https://code.claude.com/docs/en/sandboxing#filesystem-isolation)

### Network boundaries

Sandboxed commands have no direct network route. Their connections go through a local proxy that checks destination hosts against the configured allowlist and denylist. The allowlist starts empty. When a command tries an unapproved host, the result depends on the permission mode and network settings: Claude may prompt, a classifier may review the requested hosts, or the connection may be denied.

Key controls include:

- `sandbox.network.allowedDomains` and `deniedDomains`
- `sandbox.network.strictAllowlist`, which denies unlisted hosts rather than prompting (requires Claude Code v2.1.219 or later)
- `sandbox.allowManagedDomainsOnly`, which limits the effective allowlist to managed settings
- `sandbox.network.allowLocalBinding` and Unix-socket settings for special local access
- `sandbox.network.httpProxyPort` and `socksProxyPort` to use a custom proxy

The proxy filters by destination host, but by default it does **not** inspect encrypted TLS request contents. Broadly allowing a domain can therefore create an exfiltration route, and Anthropic's docs warn about domain fronting through broad allowlists such as `github.com`. Setting `httpProxyPort` or `socksProxyPort` stops Claude Code's own network controls applying to that traffic. Some tools also cannot use the proxy: plain SSH, many database clients, UDP, HTTP/3 over QUIC, and ICMP traffic do not get the same connectivity as proxy-aware tools. [Network isolation and limitations](https://code.claude.com/docs/en/sandboxing#network-isolation)

### Credential protection

You can declare credential files and environment variables in `sandbox.credentials`:

- `mode: "deny"` blocks file reads or removes the named variable from sandboxed commands.
- `mode: "mask"` gives the command a placeholder and lets the proxy substitute the real value on permitted outbound requests.

Masking needs TLS termination and an allowed destination. On macOS, masked credential files are blocked rather than made available through a sentinel copy. These settings affect sandboxed shell commands; they do not automatically protect credentials from Claude’s other tools or processes outside the sandbox. [Credential controls](https://code.claude.com/docs/en/sandboxing#protect-credentials)

### Sandbox modes and prompts

`/sandbox` provides a panel to enable the sandbox, choose how sandboxed commands are approved, configure overrides, and inspect the resolved settings.

There are two approval modes:

- **Auto-allow:** sandboxed commands generally run without a prompt because the OS boundary limits them.
- **Regular permissions:** sandboxed commands still go through the normal permission flow.

Auto-allow does not eliminate every prompt. Deny rules and content-specific ask rules still apply, among other exceptions. This approval setting is separate from **Auto mode**, which uses a classifier to review actions. The sandbox controls what a shell command can access after it runs; permission modes control whether Claude may run an action and whether it needs approval. [Sandbox modes and permission boundaries](https://code.claude.com/docs/en/sandboxing#sandbox-modes)

## How it is controlled

### Turning it on and configuring it

You can enable the sandbox in `/sandbox`, in a settings file, or for one session with `--settings`. The main settings scopes are user (`~/.claude/settings.json`), shared project (`.claude/settings.json`), project-local (`.claude/settings.local.json`), managed organization policy, and session-specific CLI settings.

The `/sandbox` panel saves its choices to project-local settings. Settings precedence and security locks affect which value actually applies; use `/status` to see loaded setting sources and `/sandbox`’s Config tab to review the resolved sandbox policy. [Settings scopes and precedence](https://code.claude.com/docs/en/settings)

### Fallbacks and exceptions

Two controls matter when a command cannot run inside the boundary:

- `sandbox.allowUnsandboxedCommands: false` disables Claude’s unsandboxed retry escape hatch.
- `sandbox.failIfUnavailable: true` makes Claude Code exit if the sandbox cannot start, instead of falling back to unsandboxed commands.

There is also `sandbox.excludedCommands`, which deliberately runs matching commands **outside** the sandbox with full user access. It should be treated as a security exception: broad patterns can let many commands run without filesystem or network restrictions.

These controls do not, by themselves, sandbox everything a person can start from the Claude Code session. A command typed directly at the `!` shell prompt usually runs outside the sandbox. [Retry behavior and strict sandbox mode](https://code.claude.com/docs/en/sandboxing#the-unsandboxed-retry-escape-hatch)

### Enforcing organization policy

Administrators can use managed settings to require sandboxing, fail closed when the sandbox is unavailable, and prevent unsandboxed retries. Additional locks can restrict domains or read paths to managed values. With an **admin-required** sandbox, repository settings cannot make certain widening changes, such as adding excluded commands or write paths; administrators must supply approved exceptions through managed settings.

The settings system’s precedence is not the only issue: some list-valued settings merge across scopes, so a local value can add entries unless a corresponding policy lock prevents it. [Enforcing and locking sandbox settings](https://code.claude.com/docs/en/sandboxing#configure-the-sandbox-for-your-organization)

## What it does not cover

The sandbox is a boundary for shell commands, **not for the whole Claude Code process**. Claude’s file and web tools, MCP servers, hooks, plugins, LSP servers, helper commands, and computer use can run outside it and follow their own permission or isolation rules. Subagents share the parent session’s sandbox configuration, but that does not bring those other tools inside the shell boundary. This describes Claude Code's own sandbox on the host; when the whole Claude Code process runs inside a Docker or OpenShell guest, its stdio MCP servers run in the guest too (see [MCP servers and sandboxes](../synthesis/mcp-servers-and-sandboxes.md)). [What runs outside the sandbox](https://code.claude.com/docs/en/sandboxing#what-runs-outside-the-sandbox)

So, the practical model is: **the sandbox constrains local shell processes; permissions and other controls govern the rest of the agent.** For a whole-process boundary, Anthropic recommends running Claude Code inside a container, virtual machine, or sandbox runtime. The sandbox reduces risk, but broad write permissions, broad network allowlists, excluded commands, and weakened-isolation options (`enableWeakerNestedSandbox`, `allowNestedUserNamespaces`, `allowAppleEvents`, `allowUnixSockets`) can materially reduce its protection. [Security limitations and scope](https://code.claude.com/docs/en/sandboxing#limitations)