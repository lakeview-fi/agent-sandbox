# Host-guest file sharing and getting changes into version control

How project files reach a sandbox, how agent changes come back and enter version control, and what to do when the files a task needs are scattered across the host. Covers Docker Sandboxes (`sbx` v0.50) and NVIDIA OpenShell (0.1.5). Documentation checked October 30, 2026; commands were checked with `--help`, not run end to end. Workspace modes, hard links and the environment file are already analysed in the [Docker analysis](../execution/docker-agent-sandbox.md) (sections 4 and "Sharing filesystem access"); `policy.yaml` paths are in the [OpenShell analysis](../execution/nvidia-openshell-analysis.md#sharing-filesystem-access-through-version-control). This note links to them and adds the handoff, the git workflow, the multi-path case and writing to a host-side file or database.

## 1. Mechanisms at a glance

| | Docker Sandboxes | OpenShell |
|---|---|---|
| Live shared directory | Yes: direct mount, same absolute path in the guest | Only by operator-enabled bind mount (off by default); not a project-level choice |
| Copy in | `sbx cp`, or a mountless sandbox that clones inside | `--upload` at create, `sandbox upload` later |
| Private working copy of a repo | `--clone`: host repo read-only at `/run/sandbox/source`, agent edits an in-VM clone | None: the upload is the working copy |
| Copy out | `sbx cp`, or `git fetch sandbox-<name>` | `sandbox download` only, within the sandbox working directory |
| Automatic sync | Direct mount only (it is the same files) | None documented |
| Git inside the guest | Yes in direct, clone and mountless modes. Not in a mounted host worktree (the `.git` pointer does not resolve) | Yes, but nothing sets it up; the repo arrives as files |

## 2. Docker Sandboxes: from guest to commit

- **Direct mount.** Edits are on the host immediately. Host and agent can both run git, so agree who creates branches and commits; switching branches on either side changes the files both see. The usual flow is a branch on the host, `sbx run`, then `git diff`, `git add -p`, `git commit`, `git push`. The agent can also edit `.git/hooks/`, CI and build files, which then run on the host: review those, not only the source diff.
- **Clone mode.** The clone follows whatever ref the host has checked out, and no branch is created automatically, so ask the agent to create one. The host repo gets a `sandbox-<name>` remote served by a git daemon in the sandbox. Review with `git fetch sandbox-<name>`, `git log` and `git diff main..sandbox-<name>/<branch>` (or let [`scripts/pull_docker_commits.py`](../../../scripts/pull_docker_commits.py) do the fetch, list the commits and create a local branch), then push to `origin` from the host, or ask the agent to push and open a pull request. Remotes such as `origin` are copied into the clone; local-path remotes are not.
- **What can go wrong.**
  - The daemon runs only while the sandbox runs. After `sbx stop`, `git fetch` fails until it restarts, and the port (and remote URL) changes, which the CLI updates.
  - `sbx rm` deletes the clone and the remote entry, so unfetched commits are lost.
  - `--clone` is rejected from a git worktree other than the main checkout.
  - The clone does not isolate parallel tasks from each other. Ask the agent for a worktree per task.
  - Clone mode adds a remote to the host repository's git config. The `develop-sandbox` templates default to a direct mount (no remote; the agent works in the host tree) and offer clone mode as the safer option (`start.ps1 -Clone`).
- **Pushing from inside.** The Docker git page describes no general mechanism for HTTPS credentials. It does say SSH agent forwarding is on by default when `SSH_AUTH_SOCK` is set, so the agent can sign commits and, as a consequence, use any key in that agent. Leaving it on is a credential decision (see the credentials sections of the develop skills).
- **Mountless.** The agent clones from a remote and pushes results back, which needs a network rule and a credential. Files persist across stops and vanish at `sbx rm`.
- **Ignore rules.** `.gitignore` does not limit what the agent can read in a mount. Only the primary repository root gets the ignore snapshot.

## 3. OpenShell: from guest to commit

OpenShell has no workspace mode and no git integration for the host repository. What follows is built from the documented transfer commands and is mostly a pattern, not a product feature.

- **Copy in.** `--upload <LOCAL>[:<SANDBOX_PATH>]` at create, or `sandbox upload`. Inside a git work tree `.gitignore` is applied, but untracked, non-ignored files are still sent; outside one, everything is sent with a warning. `--no-git-ignore` disables filtering. Directories keep their basename like `scp -r`; an existing target is merged and matching files are overwritten. Symlinks are preserved as symlinks to the same target path. A failed upload can leave partial files. Stage the copy rather than uploading the repository root, and leave `.git` out unless the agent needs history.
- **Git inside.** If the agent needs git, make a baseline commit inside the sandbox so `git diff` shows only the agent's work.
- **Copy out.** `sandbox download <name> <path> <dest>`. The source must resolve inside the sandbox's canonical working directory; paths that escape lexically or through a symlink are refused. Nothing syncs automatically.
- **Back into version control, two routes.**
  1. Export a patch from inside with `exec` (`git format-patch` or `git diff --cached --binary baseline`), download it and apply it on a new host branch. [`scripts/pull_openshell_changes.py`](../../../scripts/pull_openshell_changes.py) does this (see the [OpenShell how-to](../../guides/how-to/openshell-how-to.md)); it is a pattern built from documented commands, not a product feature, and the OpenShell setup skill tests it against a real sandbox (check 10). Review the result as untrusted code.
  2. Give the sandbox push access: a least-privilege GitHub provider plus a network rule that allows `git-receive-pack` for one repository only. The NVIDIA GitHub tutorial describes this, but I could not retrieve the page and relied on a search summary of it, so check it before use. Default policy gives read-only GitHub access.
- **Persistence.** `sandbox stop` keeps workspace data; `sandbox delete` purges it. With the Docker driver a custom `WORKDIR` lives in the container's writable layer: download what you need before deleting. A sandbox template stores image, environment and resources, not uploads or a git checkout, so it cannot carry the project files.

## 4. Scenario: files and folders scattered over the host

Example: a repo at `~/src/app`, shared libraries in `~/src/libs/core`, a spec in `~/docs/spec.pdf`, and one config at `~/.config/tool/settings.json`. The goal is to give the agent exactly these and nothing around them.

### Docker Sandboxes

- **Several directories.** `sbx run claude ~/src/app ~/src/libs/core:ro ~/docs:ro`. The first path is the primary workspace; extra paths follow, each `:ro` or writable. Each appears at its **same absolute path** in the guest. In `sbxenv.yaml` this is `additionalWorkspaces` with `readOnly: true`, using paths relative to the file.
- **Extras ignore clone mode.** Only the primary workspace is cloned. Additional workspaces are always mounted directly, so a writable extra is live host access even when the main repo is protected. Default every extra to `:ro`.
- **Single files.** The usage page does not cover single-file mounts. The CLI help says a `:ro` argument may name a single file, described as holding one path out of reach inside a workspace the sandbox can otherwise write. Whether a lone file outside any workspace can be mounted is not established; test it. For a single file, `sbx cp` (a copy, in either direction) is the documented route.
- **Do not aggregate with symlinks.** A staging folder of symlinks does not work: symlinks pointing outside the workspace are not followed. Hard links do reach outside, which is the exposure the hard-link warning describes, so do not use them as a shortcut either. A staging folder must hold copies.
- **Granularity.** The mounted unit is a directory, so mounting `~/docs` shares everything in it. To share two files from a busy directory, copy them to a small directory and mount that, or use `sbx cp`.
- **Policy.** Each mount is checked at creation. Locally every path is allowed; under organization governance each host path needs a read rule, and a writable one also a write rule.
- **Sharing the setup.** Relative host paths in a committed `sbxenv.yaml` work only if teammates keep the same layout. The file supports `${{ env.args.NAME }}`, `${{ env.projectDir }}` and `${{ env.fileDir }}` substitution, fed by `--env-arg` or `--env-args-file`, which could carry per-machine locations; use in path fields is not confirmed here. On Windows, path mapping into the guest is not documented. The `mounts:` map binds directories to paths a kit declares with `host-mount@1`, an alternative that keeps guest paths stable.

### OpenShell

- **Several sources by upload.** `--upload LOCAL:DEST` takes one source and destination; the docs say create "checks every upload", implying it can be repeated, which the help text does not show. Each source is a separate copy. Choose destinations that sit inside the policy's `read_write` paths: a destination or a parent the policy does not list fails with `Cannot mkdir: Permission denied`.
- **Control per source.** The policy is per path in the guest, so a reference folder can land under a `read_only` path while the code lands under `read_write`. Nothing marks an upload read-only; the guest path's policy does. That is stronger than a mount flag, but only if the path is not also writable.
- **Single files.** Uploads accept a single file, with `cp`-style placement. A single-file source is not supported by MicroVM bind mounts.
- **Bind mounts (operator only).** The Docker and Podman drivers accept `bind` mounts through `--driver-config-json`; Kubernetes uses PersistentVolumeClaims instead; the MicroVM driver shares directories by virtiofs (up to 32 mounts on arm64 and 3 on x86_64 per the docs; no single-file or symlink sources). All need `allow_driver_config` and `enable_bind_mounts` set by the gateway administrator, default to `read_only`, and "can bypass workspace isolation and filesystem policy". With libkrun a compromised guest kernel can reach host files outside the mounted directory. On Windows with WSL2 the "host" is the WSL file system.
- **Return path for scattered files.** `download` reaches only the sandbox working directory, so scattered outputs must be gathered into one folder inside it first. Mapping back to the original host locations is manual.
- **Sharing the setup.** The list of sources and destinations belongs in the committed `run.sh` or README, with host paths as variables, so a teammate can supply their own.

### Comparison for this scenario

| Question | Docker Sandboxes | OpenShell |
|---|---|---|
| Natural unit | Directory, mounted live | File or directory, copied |
| Many locations in one command | Yes, positional paths | Repeated `--upload` (implied, verify) |
| Read-only per source | `:ro` per mount | By the guest path's `filesystem_policy` |
| Edits visible on host | Immediately, for writable mounts | Only after `download` |
| Guest path | Same absolute path as host | Chosen by you |
| Host exposure if the guest is hostile | Every writable mount, plus hard links | Only what was copied; none without bind mounts |
| Returning changes | Already in place (mount), or `sbx cp` / `git fetch` | `download`, gathered into one folder |
| Committable setup | `sbxenv.yaml` `additionalWorkspaces` | Policy paths plus `run.sh` upload list |
| Weak point | Writable extras bypass clone protection | No sync; mapping back to origins is manual |

## 5. Scenario: the agent must modify a host-side file (a local database)

Example: a local task-tracker tool keeps a SQLite database at `~/.mytool/mytool.db`, and the agent should create and update tasks. The file is outside the repository, holds data for every project, and has no version control. Three ways to give access, from broadest to narrowest:

| Option | How | Problem |
|---|---|---|
| **Share the file** | Docker: mount `~/.mytool` as a writable extra workspace. OpenShell: not practical (bind mounts are operator-only) | The mount unit is the whole directory, so the agent gets raw write access to all projects, backups and anything else in it, and bypasses the application's own validation. A SQLite file written by the host and the guest at the same time through a VM file share is a known weak spot for file locking (general experience, not vendor-documented): test before trusting it. |
| **Copy in, copy out** | `sbx cp` or `--upload` a copy, work, copy back | Edits made on the host in between are overwritten or must be merged by hand. Acceptable for a throwaway experiment, not for live data. |
| **Call a host service over HTTP** | The application's own API on the host, reached through the sandbox's network policy | The agent only does what the API allows, and the network rule can narrow it further. Needs the service to be running and the guest to have a client. |

The tool's `serve` command is the third kind. Assume a small HTTP service on `127.0.0.1:8765` with `GET`, `POST`, `PATCH` and `DELETE` routes, no authentication, and a refusal to bind anywhere but loopback unless told to. Check for your tool that the API covers every operation its CLI does, and whether the CLI can act as a client of the server. A CLI that reads the SQLite file directly is of no use to an agent without the file, so the agent would call the HTTP API itself (for example with `curl`).

**Docker Sandboxes can do this safely.** A sandbox reaches the host by the name `host.docker.internal` (not `127.0.0.1`, and not the LAN address). The sandbox proxy rewrites that name to `localhost` before forwarding, so the allow rule names `localhost:<port>`. This works with a server bound only to loopback, which is how such a service usually runs by default. The rule can be limited by method and path and scoped to one sandbox:

```sh
sbx policy allow network --sandbox myproj localhost:8765 --method GET,POST,PATCH --path '/**'
curl http://host.docker.internal:8765/health          # test from inside the sandbox
```

Leaving `DELETE` out of the method list is the intended way to forbid deletes, but confirm it with a negative test. The trial in the develop-sandbox [GUIDE.md](../../../.claude/skills/develop-sandbox/docker/GUIDE.md) saw unlisted methods and paths get 403 at the proxy, but the Docker pages read do not spell the behavior out. Without authentication, the network rule is the only access control: anything in the guest that can reach the port can call every route the rule allows. Record the rule in `DECISIONS.md`, and keep a backup of the database. Sources: Docker [local policy](https://docs.docker.com/ai/sandboxes/governance/access-controls/local/), [troubleshooting](https://docs.docker.com/ai/sandboxes/troubleshooting/), [`sbx policy allow network`](https://docs.docker.com/reference/cli/sbx/policy/allow/network/).

**OpenShell is a poor fit today.** Network policy never authorizes a loopback destination, even with `allowed_ips`. The workaround reported by users is to bind the host service to a non-loopback address, reach it as `host.openshell.internal`, and list the address in `allowed_ips`. For an unauthenticated local service that means a non-loopback bind, which exposes an unauthenticated API beyond loopback (to every machine that can reach that interface unless a firewall blocks it). A proposal to have the supervisor proxy a host-local endpoint (GitHub issue 1633) is not confirmed as shipped. On Windows the gateway runs in WSL2, which adds another hop. Sources: OpenShell [Policy Schema](https://docs.nvidia.com/openshell/latest/how-it-works/policies/schema), [issue 1633](https://github.com/NVIDIA/OpenShell/issues/1633), [private-ip-routing example](https://github.com/NVIDIA/OpenShell/tree/main/examples/private-ip-routing); these are issues and examples of varying age, so check the installed version.

The general rule: for state that lives outside the repository and must be written, prefer a narrow service interface (an API with method and path limits) over sharing the file, and use a copy when the data does not need to be live. If the host service is an MCP server, path rules cannot tell tools apart (every call is `POST /mcp`); see [MCP servers and sandboxes](mcp-servers-and-sandboxes.md).

## 6. Gaps and what was not verified

- Docker: single-file mounts outside a workspace, file ownership of mounted files and HTTPS git credentials inside the sandbox are not covered by the pages read. Windows path mapping into the guest, git identity and hooks handling were observed on a Windows host with `sbx` v0.50.1 (see the [Docker how-to](../../guides/how-to/docker-sandbox-how-to.md) section 6), not on macOS or Linux.
- OpenShell: the GitHub push tutorial was not retrievable; repeatable `--upload` is implied, not shown in help; the patch route has been tested on a real sandbox only with `openshell` called directly in WSL2, not through `wsl -e` from a Windows shell; other setups are untested.
- Most commands were checked from `--help` and public pages, not run to completion. The pull scripts have run against real sandboxes (see the setup skills' pull checks). Treat details that touch credentials or host-writable paths as needing a trial in your environment (see the trial skills).

Sources: `sbx create/run/cp --help` (v0.50) and `openshell sandbox create/upload/download --help` (0.1.5); Docker [usage](https://docs.docker.com/ai/sandboxes/usage/), [Git with sandboxes](https://docs.docker.com/ai/sandboxes/workflows/git/), [isolation layers](https://docs.docker.com/ai/sandboxes/security/isolation/), [security defaults](https://docs.docker.com/ai/sandboxes/security/defaults/), [environment files](https://docs.docker.com/ai/sandboxes/configuration/environment-files/); OpenShell [sandboxes overview](https://docs.nvidia.com/openshell/latest/how-it-works/sandboxes/overview), [runtimes](https://docs.nvidia.com/openshell/latest/how-it-works/sandboxes/runtimes), [templates](https://docs.nvidia.com/openshell/how-it-works/sandboxes/templates), [GitHub push tutorial](https://docs.nvidia.com/openshell/get-started/tutorials/github-sandbox) (not retrieved).
