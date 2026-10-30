# Docker Sandboxes (sbx) specifics

Read with [../SKILL.md](../SKILL.md), which holds the shared rules. Docs: https://docs.docker.com/ai/sandboxes/ . Kits need `sbx` v0.45 or later. Verify flags with `sbx <cmd> --help`, and trust live docs over this file. Host-specific traps (Windows, macOS, Linux) are in [PLATFORM-NOTES.md](PLATFORM-NOTES.md). Credentials and the Claude subscription login are in [CREDENTIALS.md](CREDENTIALS.md).

## Templates

[templates/](templates/) holds starter files. Copy them as described in the shared skill, section 3.

**Default: two env files plus scripts.** Tested with `sbx` v0.50.1 on Windows 11:
- Clone mode, end to end: a custom agent ran a task, committed, and the commit was pulled and merged on the host.
- Direct mode: setup, tests and a read-only agent check passed.

The default is a built-in `claude` agent with the subscription login. The definition is split in two:
- The global `~/.sbxenv.yaml` holds what is shared across repos (agent, shared mounts, sizing).
- A repo-root `sbxenv.yaml` holds the name, the workspace and the venv path.

`start.ps1` runs `sbx env create` from the repo root with no PATH, which is what makes sbx merge the two files. It then applies the allow list and runs the setup.

| File | Install at | Role | Usually adapt |
|---|---|---|---|
| `global-sbxenv.yaml` | `~/.sbxenv.yaml`, once per machine; merge if one exists | Agent, shared mounts (tool data, agents, CLI sources) and their env vars, sizing | the mounts and env |
| `sbxenv.yaml` | repo root | Name, `workspace: .`, `UV_PROJECT_ENVIRONMENT` | name, venv path |
| `start.ps1` | `sandbox/` | Create if missing (`-Clone` for clone mode), allow list, setup, start Claude Code (`-Agent`, `-Prompt`, `-Recreate`, `-Resetup`, `-SetupOnly`) | `$Agent` default, the run-time notice |
| `stop.ps1` | `sandbox/` | Pull (clone mode), then stop; `-Remove` deletes | nothing |
| `setup-in-sandbox.sh` | `sandbox/` | Runs inside after create: tools, agents and skills, git identity, hooks (clone), deps | the `ADAPT` blocks |
| `pull.ps1` | `sandbox/` | Clone mode: wrapper around `sandbox/scripts/pull_docker_commits.py`, a project copy of [`scripts/pull_docker_commits.py`](../../../../scripts/pull_docker_commits.py) and `sandbox_git_common.py`; direct mode: says there is nothing to pull | the copied scripts (review globs, branch names) |
| `scripts/*.py` | `sandbox/scripts/` | Copied from this repo's `scripts/` when installing: `pull_docker_commits.py`, `sandbox_git_common.py` | as needed for the repo |
| `allowed-hosts.txt` | `sandbox/` | Per-sandbox network allow list. A `<host> <METHODS> <path-glob>` line is an HTTP rule | the hosts |
| `watch-policy.ps1` | `sandbox/` | Started by `start.ps1` in the background (`-NoWatch` skips it). Polls `sbx policy log --json` and appends allowed and blocked requests as JSON lines to a file outside the repo (`%LOCALAPPDATA%\sbx-policy-logs\<name>.jsonl`). Limits: sbx aggregates per host (no paths or methods) and logs no filesystem denials | nothing |
| `kit/kit.yaml`, `kit/kit.dockerfile` | `sandbox/kit/` | Optional image: root and system installs at build time (see "Image" below) | base image, the installs, pinned versions |
| `TASK.md`, `DECISIONS.md`, `README.md`, `gitattributes` | `sandbox/` | Acceptance task, decisions, developer commands, LF endings | as before |

**Repo modes** (the user picks one; `start.ps1` uses direct unless `-Clone` is given; switching needs `-Recreate`):

| | Direct mount (default) | Clone (`-Clone`) |
|---|---|---|
| Agent works in | The host working tree and `.git`, live | A private clone inside the sandbox |
| Results | Already on the host branch; nothing to transfer | `pull.ps1` creates `agent/<name>/<branch>`; `-Merge` fast-forwards |
| Agent can change | Everything in the repo, including uncommitted work, hooks, `sandbox/*.ps1`, build files and `.git/config`: files that later run on the host | Only its clone; changes reach the host as reviewed commits, with hooks off during the pull |
| Env file | The repo-root `sbxenv.yaml` is mounted read-only by sbx | Same |
| Choose when | The user wants speed and reviews `git diff`/`git log` before running host scripts | Untrusted tasks, or when the host repo must not change until review |

### Image: a kit with a Dockerfile (`kit/`)

`setup-in-sandbox.sh` is for user-level, per-checkout steps: CLIs in `~/.local`, agents and skills, git config, `uv sync`, `npm ci`. Anything that needs root or changes the system belongs in an image: apt packages, system libraries, browsers, changed apt sources, files outside `$HOME`. **Signs that it is time for a kit:** setup uses `sudo`; the allow list holds package-archive or binary-download hosts the agent's own work does not need; or each create re-downloads large binaries. A kit runs those installs once at build time. The runtime policy then drops their hosts, and creates get faster.

Method (example: Playwright Chromium and its apt libraries):
1. **Make it work in setup first.** Install with `sudo` in `setup-in-sandbox.sh`, and allow the download hosts as narrow HTTP rules (`<host> GET,HEAD /<path>/**` lines in `allowed-hosts.txt`; `sbx policy log <name>` shows redirect targets). This finds the exact packages, hosts and side fixes before an image build is involved.
2. **Move the root steps into `kit/kit.dockerfile`**, copied from [templates/kit/](templates/kit/). Take the base image from the `Image:` line of `sbx create` output for the built-in agent (`docker/sandbox-templates:claude-code-docker` on sbx v0.50.1). Then the kit differs from the verified setup only by what you add.
3. **Pin versions that must match the repo** (for example Playwright, whose release pins its own Chromium build) with an `ARG` that equals the lockfile. Write the baked version to a marker file, and make setup fail with a rebuild hint when the lockfile has moved on. The runtime policy can no longer download a matching build.
4. **Fix base-image traps in the image.** The built-in image lists apt sources for `download.docker.com` and `cli.github.com`; with those blocked, `apt-get update` fails. The template parks them.
5. **Keep the built-in agent's behaviour.** The built-in agent runs `claude --dangerously-skip-permissions`. The kit's `ENTRYPOINT` does the same, and `start.ps1` passes the flag to `claude -p` runs.
6. **Wire it up.** In the repo `sbxenv.yaml`, set `agent: <kit name>` plus `kits: [./sandbox/kit]`. The kit's name is its folder name (`kit`). That is the only form `sbx env create` v0.50.1 accepts. It rejects no `agent:` (`agent is required`), a path in `agent:` (`is not a known agent`), and `agent: claude` plus the kit (`does not match agent kit name`). The repo's `agent:` overrides the global `agent: claude`. Check with `sbx env plan`. Project hosts stay in `allowed-hosts.txt`, so there is one list and path rules work; the kit's `network-policy` holds only the Claude hosts. Remove the hosts that are now needed only at build time, and record that in `DECISIONS.md`.
7. **Build and validate without touching the sandbox:** `sbx kit validate <kit dir>` builds the image and checks the descriptor.
8. **Credential (user step).** sbx does not give a kit the Claude subscription until the user approves the binding once, in a real terminal: `sbx create --name <x> <kit dir>`, answer the prompt, then `sbx rm --force <x>`. Never write the bindings file yourself ([CREDENTIALS.md](CREDENTIALS.md)). Then `start.ps1 -Recreate`.
9. **Verify:** `claude auth status` reports `authMethod: claude.ai`, `.credentials.json` holds the two `proxy-managed` sentinels, `claude -p` replies, the baked tool works (run the project's own e2e or build command), and the build-only hosts are blocked. Keep the commit of the working setup-based version in `DECISIONS.md`, so a failed credential can be rolled back.

Status (`sbx` v0.50.1): kit build, validation and wiring verified. **The Claude login failed, so the kit was rolled back.** In a test project, the kit sandbox was created and setup passed. But Claude Code reported `loggedIn: false`, and sbx warned `no credential resolved for required service; sandbox will start without it`. `.credentials.json` held the two `proxy-managed` sentinels, and the global `anthropic (oauth configured)` secret was present. The user approved the binding in a real terminal (step 8) and created the sandbox interactively without `--force`, but no binding prompt appeared and the warning stayed. Not diagnosed: reading the sbx credential and bindings files is credential access, which the managing agent does not do.

Until someone finds out how a local workload kit's `credential@1` gets its binding through `sbx env`:
- with Claude Code, keep the root installs in setup (steps 1, 4 and 5 still apply there);
- treat steps 2–3 and 6–9 as an experiment;
- tell the user before starting it, and keep the setup-based commit to roll back to.

Notes:
- Built-in agent names select v2 kits that do not take v3 mixins, so the kit is a full v3 workload.
- In direct mode the kit directory is in the agent-writable mount, and the next build runs its Dockerfile. Review `git diff sandbox/kit` before every recreate, as for `sandbox/*.ps1`.

Formats, the Dockerfile contract, credential `secrets`/`bindings` and persona options: [config file reference](../../../../docs/guides/how-to/config-file-reference.md#docker-sandboxes). Do not restate them here.

## Rules specific to Docker Sandboxes

- **Repo mode:** ask in the starting message whether the agent works on the repo directly (default, results land at once) or on a private clone (safer, results come back with `pull.ps1`). State the direct-mode risk in the same question: the agent can change files that later run on the host.
- **Env file placement:** an env file must sit outside every mounted directory, or at the root of a direct-mounted workspace, which sbx mounts read-only. Never put it in a subfolder of a mount: the agent could swap it by renaming the folder. The repo file goes at the repo root.
- **Shared data on read-write mounts:** SQLite (and anything relying on file locks or shared memory) is unsafe with writers on both sides of the VM boundary, or in two sandboxes. Several agents inside one sandbox are fine. Tell the user, and prefer a single-writer service on the host. See "Host service" below.

## Host service instead of a shared data mount

Tested with a local HTTP service (here called `<tool> serve`) on Windows, `sbx` v0.50.1, from two repos' sandboxes:
- **Server:** it runs on the host, bound to `127.0.0.1` only. `start.ps1` checks a health URL and starts it hidden if it is down (`Start-Process ... -WindowStyle Hidden`, logs under `%LOCALAPPDATA%`). `stop.ps1` leaves it running, because other sandboxes share it. The data folder is not mounted at all.
- **Address from the guest:** `http://host.docker.internal:<port>`. The sbx proxy maps it to the host's `localhost`, so a loopback-only server is reachable.
- **Network rule:** the rule must name `localhost:<port>`, because a rule for `host.docker.internal:<port>` alone does not match. Make it an HTTP rule with only the methods and paths the client needs, for example `localhost:8765 GET,HEAD,POST,PATCH /api/**`. Everything else, such as the server's `DELETE` routes and non-API paths, then gets 403 at the proxy.
- **Client config:** put the URL in the env file under a name the tool does not read (`SBX_<TOOL>_URL`). In setup, write a wrapper for the installed CLI that sets the real variable (`<TOOL>_URL`) for that command only. A sandbox-wide `<TOOL>_URL` would also reach the repo's own tests and work-in-progress code, which may then write to the live data. Write the wrapper after `rm -f` of uv's link: writing through the symlink replaces uv's real entry point with the wrapper, which then execs itself forever.
- **Token:** sbx network rules cannot proxy-inject a custom header for a host (MCP gateway servers can, see below), so a token would sit in the guest where the agent can read it. Loopback binding plus the per-sandbox method and path rule is the boundary. Record the user's choice. For an MCP server this does not hold: every call is `POST /mcp`, and Docker's MCP gateway (`sbx mcp`) can keep the token on the host. See [MCP servers and sandboxes](../../../../docs/analysis/synthesis/mcp-servers-and-sandboxes.md).
- **Global env file:** for tools shared by several repos, put `SBX_<TOOL>_URL` in `~/.sbxenv.yaml`, and the health check, server start and network rule in each repo's scripts.
- **One repo per sandbox.** `--clone` needs a git repository, so a folder of several repos cannot be cloned. A direct mount of such a folder works, but the agent can then reach every repo's `.git`, and per-repo setup (venvs, hooks) multiplies.

## Workflow

Session and permission commands (plan, create, exec, policy, recreate, delete): [Docker Sandboxes how-to](../../../../docs/guides/how-to/docker-sandbox-how-to.md) sections 2-5 and 7. The template README lists them in order.

Run the acceptance task non-interactively with `claude -p` and the text of `TASK.md`. Check with `sbx env --help` and `sbx exec --help` which form accepts the sandbox name.

Docker launches agents with their own permission prompts bypassed. The microVM, mounts and network policy are therefore the safety boundary, and the safety review is mandatory.

## Traps seen in practice (Windows host, sbx v0.50.1)

- **Mounts keep their host path** (`C:\x` becomes `/c/x`), and the clone sits at the repo's own path. A mount of a **parent folder** of the repo covers the clone, so the agent silently works in the host's read-only working tree instead. Mount specific sibling repos, never a parent.
- The clone holds only commits. Uncommitted host work, and git-ignored files such as `uv.lock` or `tmp/`, are missing. Recreate what the project expects in setup.
- Local git config is not cloned, and the host's global and system git config are not visible. Setup writes identity and `core.autocrlf=input` to the sandbox user's `~/.gitconfig`, never to the repo's `.git/config`, which in direct mode is the host's own. In clone mode it also sets `core.hooksPath`. Hooks committed from Windows are mode 100644, and Linux git skips them silently, so setup `chmod +x`es them with `core.fileMode false`. A direct mount shows every file as executable.
- **The clone's `origin` is `/run/sandbox/source`**, a read-only snapshot of the host working tree (uncommitted files included, so the agent can read them). Tools that derive a repo identity from the origin URL see a local path. A CLI that keys its project data by the origin URL, for example, then falls back to a path hash and does not find the project. Prefer fixing the tool to skip local-path origins (a tool that then falls back to the root commit finds the project in the clone). As a workaround, setup can remove the origin: `pull_docker_commits.py` uses the host's `sandbox-<name>` remote, not this origin.
- **Direct mode: host build artifacts are in the mount.** A Windows `.venv`, or `node_modules` with Windows native binaries (for example `@rollup/rollup-win32-*`), would be replaced by `uv sync` or `npm ci` in the sandbox, which breaks the host. Two fixes:
  - `.venv` only: set `UV_PROJECT_ENVIRONMENT` to a path in the sandbox home.
  - Any folder: bind-mount a VM-local folder over it inside the guest (`sudo mount --bind ~/guest-overlays/<x> <repo>/<x>`). The agent sees Linux builds at the usual paths, so hooks that look for `.venv/bin/python` work, and the host copies are never touched. Bind mounts are lost when the VM stops, so `start.ps1` must reapply them on every start; tell the user to start with `start.ps1`, not `sbx run`. Put the `mount --bind` lines in a `sandbox/guest-overlays.sh` that `start.ps1` runs.
  Tests on the mount can be noticeably slower than on the clone's local disk (about 2x in one measured Windows project); prefer clone mode when test time matters.
- **Direct mode: CRLF scripts from a Windows checkout.** With `core.autocrlf=true`, or a checkout older than the repo's `eol=lf` rule, hooks and shell scripts in the mount have CRLF, and Linux `sh` fails (`Syntax error: "elif" unexpected`). The agent's commits then fail the pre-commit hook. Check with `git ls-files --eol <file>` (`w/crlf`). If the index has LF (`i/lf`), delete the file and `git checkout -- <file>`: only the line endings change and `git status` stays clean. Ask the user before rewriting more than the files the sandbox runs. A clone does not have this problem.
- **Clone-mode detection:** the host's `sandbox-<name>` remote can disappear while the sandbox exists. Read `Clone source:` from `sbx inspect <name>` instead (`-` means direct).
- `sbx exec` can print a stale "runs on an in-container clone" warning after a same-name sandbox was recreated in direct mode. `mount` inside shows the truth.
- **Persistence:** a stopped sandbox, including its clone and commits, survives `sbx stop` and host reboots. Only `sbx rm` deletes it.
- Read-only source mounts cannot be built in place (setuptools writes `egg-info`). Copy them to a temp dir first.
- Piping a script with `$text | sbx exec -i <name> -- bash -s` works, but PowerShell appends CRLF. Convert to LF and end on a comment line.
- **PowerShell splatting:** `$a = if ($x) { @('--clone') } else { @() }` gives a string, because `if` unwraps a one-element array. `@a` then passes its characters (`-`, `-`, `c`, ...), and `sbx env create` failed with `no sbxenv.yaml found at ...\-\sbxenv.yaml`. Use `$a = @(if ($x) { '--clone' })`. The template has the fix.
- `cmd | head -3` in setup fails under `set -o pipefail` when `cmd` is still writing (head closes the pipe early, which a slower HTTP-backed CLI hits). Use `sed -n 1,3p`, which reads all input.
- **Reinstalling a host tool while it serves (Windows):** `uv tool install --force` under a running server leaves only the locked `python.exe` in the tool environment. The CLI then fails with `No module named ...`, while the server keeps serving from memory. Stop the server, reinstall, start it again.
- SQLite on a read-write mount: locks do not cross the VM boundary. Tested: the host wrote while the guest held `BEGIN EXCLUSIVE`, and the guest's commit failed with `disk I/O error`. Prefer a host service ("Host service" above). Otherwise use one writer side at a time, and back up the DB before the first run.
- `sbx rm` deletes the clone. Pull first (`stop.ps1` and `start.ps1 -Recreate` do). Pulled branches survive under `refs/sandboxes/<name>/*`.
- `~/.sbxenv.yaml` is read only when `sbx env` gets no PATH. With explicit PATHs it is skipped, and `${{ env.projectDir }}` becomes the first file's directory. Run `sbx env create` from the repo root without PATH.

## Triage notes

- **Network denied:**
  - Add the host to `allowed-hosts.txt` (with or without a kit), narrowest form first: an HTTP rule `<host> GET,HEAD /<path>/**` when only one path is needed, for example one bucket on a shared storage host. `start.ps1` applies it with `sbx policy allow network --sandbox <name>`. `sbx policy allow` is global unless `--sandbox` is given.
  - A host needed only to install something as root belongs in the kit's image build, not in the runtime list (see "Image").
  - An org policy may still deny the host.
- **Held requests:** the Balanced and Locked Down profiles hold unmatched requests for developer approval. The user approves with `sbx policy approval`, and the agent retries. Record approved hosts in `DECISIONS.md`.
- **Path not visible:** add an `additionalWorkspaces` entry, read-only first. Mount changes need a recreated sandbox.
- **Clone mode** adds a `sandbox-<name>` git remote to the host repo (`sbx create --clone` help). Do not use it unless the user accepts that change to the host repo.
- **Negative tests (required):** an unlisted host is blocked; `~` and other host paths are not visible; a write to a read-only workspace fails.
