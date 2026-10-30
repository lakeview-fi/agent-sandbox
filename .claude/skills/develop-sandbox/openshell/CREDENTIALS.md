# Credentials for an OpenShell sandbox

Read with [../SKILL.md](../SKILL.md) and [GUIDE.md](GUIDE.md). The user creates and stores every credential. The managing agent never reads, pastes or logs a secret value, and gives the user commands to run in their own shell. Details below are from the OpenShell provider docs (https://docs.nvidia.com/openshell/latest/how-it-works/providers/overview); anything marked unverified needs `openshell provider --help` or a test.

## Rules

- Do not ask the user to paste a secret into chat. Name the provider and the command that creates it.
- `openshell provider create ... --from-existing` reads the credential from an environment variable in the shell that runs the CLI. The user exports it in their own terminal (for example `export OPENROUTER_API_KEY=...`), not in a shell the managing agent can read. On Windows, that shell is WSL2.
- Credentials stay in the gateway. The sandbox sees placeholders; the proxy substitutes the real value only toward the endpoints bound to the provider.
- Do not put a token into the image, the policy, `run.sh` or a repo file as a workaround. That is a credential decision for the user.

## Provider attachment (user decides)

A provider is created once on the gateway and attached to a sandbox with `--provider <name>` at creation. Present these choices to the user; do not pick for them:

| | Attach to this sandbox only | Reuse across sandboxes |
|---|---|---|
| How | `--provider <name>` on this sandbox's `create` only | the same provider attached to several sandboxes |
| Blast radius if a sandbox is compromised | This sandbox's access to the provider's endpoints | Every sandbox with that attachment |
| After `openshell sandbox delete` | The docs say delete purges injected credentials; whether the provider object remains on the gateway is unverified, so check `openshell provider --help` and list providers | Provider remains for other sandboxes |

Prefer a dedicated, least-privilege provider per project (for example a GitHub token limited to one repository) over a broad one. After a recreate, re-attach with `--provider`.

## Claude Code with a Claude subscription: `claude auth login` inside the sandbox (default)

This is the default for Claude Code. It is the same subscription login the developer uses on the host (`claude auth login`), done once per sandbox:

1. `sh sandbox/run.sh create`. No credential is passed at creation.
2. The user runs `sh sandbox/run.sh login` in their own terminal (WSL2 on Windows). In a Claude Code session, prefix it with `!` so it gets a real terminal. It runs `openshell sandbox exec -n <name> --tty -- claude auth login --claudeai`. Claude Code prints a URL. The user opens it in the host browser, approves, and pastes the one-time code back if asked. That code is not the token.
3. `run.sh login` then runs `claude auth status`, which must report `authMethod: claude.ai`. Never print `~/.claude/.credentials.json`.

The policy template allows `api.anthropic.com` and `platform.claude.com` (the OAuth token endpoint) for the `node` binary that runs Claude Code in the template image (an npm install). If your image installs the native `claude` binary instead, list that binary's path in the rule; the rule matches the calling binary. Both hosts are read-write, because the agent and the token exchange POST.

What is verified and what is not:
- **Verified:** `claude auth login --claudeai` exists (Claude Code 2.1.x), and `openshell sandbox exec --tty` exists (openshell 0.1.5).
- **Not covered by testing yet:** the full login inside an OpenShell sandbox. The first run on your host must confirm two things. First, that the policy needs no further host; if it does, add it from the denial log and record it. Second, that `exec` sees `HOME=/home/sandbox`, so the login and later runs share one credentials file.

Exposure:
- The OAuth access and refresh tokens are stored in `/home/sandbox/.claude/.credentials.json` inside the sandbox. The sandboxed agent can read them, and anything in the sandbox could send them to an allowed host.
- They are a separate login from the host's. Revoking them, or deleting the sandbox, does not log the host out.
- Deleting the sandbox discards the file. A recreate needs a new `login`.
- State this in the exposure-risk summary. OpenShell's placeholder model would keep the token out of the guest, but it has no subscription provider today (see below).

**Do not use `claude setup-token`.** Do not export `CLAUDE_CODE_OAUTH_TOKEN`, and do not pass it with `--env` or `--env-from`.
- It mints a long-lived token that is not the developer's normal login.
- It sits in an environment variable visible to the agent and to every process.
- The interactive login above gives the same access without a second long-lived credential on the host.

Do not copy the host's `~/.claude/.credentials.json` into the sandbox either. A refresh inside the sandbox can rotate the refresh token and log the host out (unverified, and not worth the risk). On macOS the host login is in the Keychain, not in that file.

## Other routes for Claude Code (user decides)

OpenShell's gateway holds a provider credential and the guest gets an opaque placeholder env var; the proxy swaps it for the real value on egress, only to the endpoints the provider profile binds. **Tested with openshell 0.1.5:** `claude -p` completes a real tool-using task in a sandbox through an `openrouter` provider, with the env mapping `ANTHROPIC_BASE_URL=https://openrouter.ai/api`, `ANTHROPIC_AUTH_TOKEN=$OPENROUTER_API_KEY`, `ANTHROPIC_API_KEY=` (empty), `CLAUDE_CODE_MAX_OUTPUT_TOKENS=4000`, and an L7 policy rule for the native `claude.exe`; see the smoke test skill's SMOKETEST.md, "Running claude through openrouter".

OpenShell's providers do not hold a Claude **subscription**.
- The docs say subscription users need a separate Console API key.
- `--type claude-code --from-existing` reads only `ANTHROPIC_API_KEY` or `CLAUDE_API_KEY`.
- `openshell provider list-profiles` (0.1.5) lists only `openrouter`.

Profiles can declare gateway-side OAuth refresh (`refresh: strategy: oauth2_refresh_token`). A custom Claude profile built that way is possible in principle but unverified. Do not offer it until a spike proves it.

Alternatives to the subscription login, each needing the user's approval:
1. **Docker Sandboxes.** The subscription login there keeps the tokens in the host secret store, and the guest sees only placeholders (see `../docker/CREDENTIALS.md`). Recommend it when the token must stay out of the guest.
2. **An OpenRouter or Anthropic Console API key held by a gateway provider.** The guest sees a placeholder. Billing is separate from a subscription.
3. **Skip the agent.** Run the acceptance steps that need no model with `openshell sandbox exec`, and defer the agent run.

Never put a key or token into the sandbox environment (`--env`, `--env-from`). The agent can read it, and the login above is the better choice.

## Other credential types

Use the same pattern: name the provider, the endpoints it is bound to, and the command the user runs. For a Git provider, bind it to the specific host and repository scope, and record it in `DECISIONS.md`.
