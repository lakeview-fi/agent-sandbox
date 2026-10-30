# Credentials for a Docker Sandbox (sbx)

Read with [../SKILL.md](../SKILL.md) and [GUIDE.md](GUIDE.md). The user creates and stores every credential. The managing agent never reads, pastes or logs a secret value, and gives the user commands to run in their own shell.

## Rules

- Do not ask the user to paste a secret into chat. Name the secret and the command that stores it.
- Give commands for PowerShell (the Windows `sbx` lives there). WSL cannot see `sbx` or its secret store.
- Verify with `sbx secret ls` (shows scope, name and `(stored)`, never the value).
- Do not put a token into the sandbox environment, the env file or a repo file as a workaround. That is a credential decision for the user.

## Scope: sandbox-scoped or global (user decides)

`sbx secret set <service>` stores a secret in one of two scopes. Present both to the user and let them choose. Do not pick one for them.

| | Sandbox-scoped (`--sandbox <name>`) | Global (no `--sandbox`) |
|---|---|---|
| Who can use it | Only the named sandbox | Every sandbox on this machine |
| Survives `sbx env rm` | No. `sbx env rm` deletes secrets scoped to that sandbox | Yes |
| Recreate needed to apply a change | Yes; secrets apply at creation | Yes |
| Blast radius if a sandbox is compromised | This sandbox only | Every sandbox that has the same service |
| Typical use | One project, reproducible rebuilds with a key the user re-enters | Testing, or a key the user wants reused across sandboxes |

Trade-off to state to the user: a sandbox-scoped secret is more isolated, but every `sbx env rm` (or recreate) deletes it, so the user must enter it again. A global secret survives recreates, but any sandbox on the machine can use it.

Check for a second copy: if a sandbox-scoped and a global secret both exist for one service, remove the one the user does not want (`sbx secret rm`) so it is clear which one applies.

## Claude Code with a Claude subscription: `/login` inside the sandbox

Tested with `sbx` v0.50.1, Claude Code 2.1.306 and a Claude subscription plan: the built-in `claude` kit supports a subscription login whose real tokens never enter the sandbox. Same property as OpenShell's placeholder model.

How it works: the user logs in inside the sandbox. The sbx proxy intercepts the token exchange at `platform.claude.com/v1/oauth/token` and keeps the real access and refresh tokens in the host secret store (global scope). The guest's `~/.claude/.credentials.json` holds only the sentinels `sk-ant-oat01-proxy-managed` and `sk-ant-ort01-proxy-managed`; the proxy swaps in the real token on egress and refreshes it.

Precondition: **no `anthropic` API-key secret may be stored.** A stored key sets `SBX_CRED_ANTHROPIC_MODE=apikey` and `apiKeyHelper: echo proxy-managed`, and the docs say the API key then wins over OAuth. Remove it first (`sbx secret rm anthropic`, a global change the user decides on).

User steps:
1. `sbx create --name <sandbox> claude [path]`
2. `sbx run --name <sandbox> -- auth login --claudeai` (needs a real terminal; in Claude Code prefix with `!`). Approve in the host browser and paste back the one-time code if asked; that code is not the token.
3. `sbx secret ls` shows `(global) service anthropic (oauth configured)`.

Verify without reading secrets, via `sbx exec <sandbox>`: `~/.claude/.credentials.json` exists and `grep -o proxy-managed ~/.claude/.credentials.json | wc -l` gives 2 (never cat it); `settings.json` has no `apiKeyHelper`; `claude auth status` reports `authMethod: claude.ai`; then `claude -p` reads a file and replies (the smoketest's 8e). Note that the sandbox env var `SBX_CRED_ANTHROPIC_MODE` reads `none` even in OAuth mode, so do not use it as the signal.

Existing sandboxes do not pick the login up (tested): credential mode is fixed when a sandbox is created. A sandbox created while an API-key secret was stored stays in `apikey` mode (`apiKeyHelper` present) and fails once that key is removed; one created with no credential reports `loggedIn: false`. Recreate such sandboxes after the login, or log in inside each one. A sandbox created after the login starts logged in with no further step (the smoketest creates a fresh sandbox each run).

Scope and risk: Anthropic OAuth is global-only locally (`sbx secret set --oauth` is "openai/global only"), so every sandbox on the machine can spend the subscription through the proxy, and a compromised guest can make API calls with it while it runs, but cannot take the token. It relies on the closed-source sbx proxy being correct. The Docker docs say an API key takes precedence over OAuth; `sbx secret import --help` says the opposite. Removing the key avoids depending on either.

Terms: running the real Claude Code CLI with its own login is within Anthropic's terms; using subscription OAuth in other tools or the Agent SDK is not (https://code.claude.com/docs/en/legal-and-compliance).

**Do not use `claude setup-token`** with a sandbox: the login above is the developer's own subscription login and keeps the token out of the guest.
- Storing a setup-token value with `sbx secret set anthropic` fails. The kit injects that secret as the `x-api-key` header, which an OAuth token cannot use, so the result is `401 invalid x-api-key` and `claude -p` hangs retrying.
- Earlier findings (a stored secret did not log in; a placeholder `CLAUDE_CODE_OAUTH_TOKEN` was ignored) were all in API-key mode and are explained by this.

**With the project kit** (`templates/kit/kit.yaml`), the kit declares a `credential@1` capability that writes Claude Code's `~/.claude/.credentials.json` with the `proxy-managed` sentinels. This is modelled on the verified pi kit. **It failed for Claude Code in testing:** after the user approved the binding, the sandbox still started with `no credential resolved for required service` and `loggedIn: false`, so the project rolled back to the built-in agent (GUIDE.md, "Image", Status). A third-party kit is not trusted with the subscription by default. The user approves the binding once by running `sbx create` with the kit in a real terminal and answering the prompt (see the `setup-smoketest-docker-sandbox` skill, "Running pi instead of claude"). Do not write the bindings file yourself: it grants a kit your subscription.

Other options if `/login` is not wanted: a proxy-held Console API key (`sbx secret set anthropic`, separate billing, no subscription), or skip the agent and defer the Claude run. Putting a token into the sandbox environment is the weakest option: the agent can read it. Do not do it without the user's explicit decision.

## Optional: WSLENV (host side only)

`WSLENV=WT_SESSION:WT_PROFILE_ID:<VAR>/u` passes a Windows environment variable into WSL. Any WSL process, including managing agents, can then read it. It does not reach the sandbox. Use it only when the user asks for it.

## Other credential types

Use the same pattern: name the service, the scope the user chose, and the command to store it. For registry pulls, see `sbx secret set --registry`; those credentials are host-only unless `--all-sandboxes` or `--sandbox` is set.
