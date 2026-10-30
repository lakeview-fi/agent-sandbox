# OpenShell specifics

Read with [../SKILL.md](../SKILL.md), which holds the shared rules. Docs index: https://docs.nvidia.com/openshell/latest/llms.txt . Verify flags with `openshell <cmd> --help`, and trust live docs over this file. Host-specific traps (Windows via WSL2, macOS, Linux) are in [PLATFORM-NOTES.md](PLATFORM-NOTES.md). Credentials are in [CREDENTIALS.md](CREDENTIALS.md).

## Templates

[templates/](templates/) is generalized from a tested project sandbox: a Python and `uv` project with Claude Code, on openshell 0.1.5 with the Docker driver on WSL2. Copy it as described in the shared skill, section 3.

| File | Role | Usually adapt |
|---|---|---|
| `run.sh` | Steps: `build`, `stage`, `create`, `login`, `baseline`, `test`, `agent`, `negative`, `safety`, `pull`, `teardown` (`pull` calls [`scripts/pull_openshell_changes.py`](../../../../scripts/pull_openshell_changes.py)) | the variable block (including `AGENT_SANDBOX_SCRIPTS`), `project_checks`, `RUN_ENV` |
| `Dockerfile` | Agent CLI, toolchain, OpenShell supervisor, workload user | the toolchain block, pinned versions |
| `policy.yaml` | Filesystem, landlock, process, network (deny by default) | project network rules |
| `boundary.yaml` | The most access you accept (prover input) | keep in step with the reviewed `policy.yaml` |
| `TASK.md` | Acceptance task prompt for `run.sh agent` | all of it |
| `DECISIONS.md` | One line per grant, deviation and pending decision | all sections |
| `README.md` | Steps for the developer | names only |
| `gitattributes`, `gitignore` | LF endings; ignore `.stage-path` and `effective.yaml` | nothing |

Formats and image traps (UID 1000, root-baked caches, interpreter permissions): [config file reference](../../../../docs/guides/how-to/config-file-reference.md#openshell). Do not restate them here.

## Rules specific to OpenShell

- **Git remote:** OpenShell has no clone mode. Ask the user whether the sandbox gets only an uploaded copy (no way to push) or also a least-privilege Git provider so the agent can push or fetch. Ask every time unless the user has already said which one they want. Default recommendation: uploaded copy only, with no Git provider. The user pulls changes back with `openshell sandbox download` and reviews them.
- **Repo mode: upload only, unlike Docker's direct-mount default.** Copy the project in with `--upload`. Uploaded copies keep the host `sandbox/` files out of the agent's reach. OpenShell 0.1.5 has no per-sandbox mount flag. A live host mount needs the gateway operator to set `allow_driver_config = true` and `enable_bind_mounts = true` in the gateway TOML, which applies to every sandbox on that gateway, and then `--driver-config-json` on each create. NVIDIA warns that it "can bypass workspace isolation and filesystem policy", and the prover boundary then no longer covers the repo. The templates do not support it, and it is not verified. If the user wants the agent's commits on the host branch at once, recommend Docker. Details: [OpenShell analysis](../../../../docs/analysis/execution/nvidia-openshell-analysis.md#live-host-mount-versus-copy-in-differs-from-docker-sandboxes).
- **Stage, don't upload the repo root.** Inside a git work tree, `--upload` applies `.gitignore` but still uploads untracked, non-ignored data (for example run output or a second project next to the repo). `run.sh stage` copies the tracked and untracked, non-ignored regular files into a temp directory. It always excludes `sandbox/` and `.claude/`, plus the project paths in `STAGE_EXCLUDE`. `.git` stays out, and `run.sh baseline` makes a baseline commit inside the sandbox.

## Workflow

Session and permission commands (build, create with `--upload`, exec, logs, policy get/update, recreate, delete): [OpenShell how-to](../../../../docs/guides/how-to/openshell-how-to.md) sections 1-5 and 7. `run.sh` wraps them.

Order: `build`, `stage`, `create`, then `login`, `baseline`, `test`, `agent`, `negative`, `safety`, `pull`. Commit or stash local changes before `stage`: `pull` makes its patch against the staged state. The user runs `login` in their own terminal (see CREDENTIALS.md).

`exec` does not inherit the image's `ENV`, so `run_in_sandbox` passes non-secret variables with `--env KEY=VALUE`.

## Triage notes

- **Network denied:** try the rule live or review a Policy Advisor proposal ([how-to](../../../../docs/guides/how-to/openshell-how-to.md), section 4), then **copy the rule into `policy.yaml`** (section 5). Live edits are lost on recreate.
- **Filesystem denial:** edit `policy.yaml` and recreate. An upload failure such as `tar: ... Cannot mkdir: Permission denied` is a policy denial on the upload target or a parent, not a copy problem (how-to, section 9).
- **Host commands from the managing agent's own bash sandbox:** the Docker socket and the gateway endpoint can be refused there while they work in the user's shell (seen on WSL2 with Docker Desktop). That failure is caused by the sandbox. Run `docker` and `openshell` with the sandbox bypass only after the user approves each such command. Restarting Docker Desktop is a user action (see the setup skill's WSL notes).
- Do not attach a Git provider unless the user accepted it under the Git remote rule.
- **Safety gate (required):** `run.sh safety` saves the effective policy and compares it with the boundary using `openshell-prover check` ([how-to](../../../../docs/guides/how-to/openshell-how-to.md), section 5).

Prover results:
- `within_boundary` passes.
- `exceeds_boundary` prints a counterexample (the rule that is outside the boundary).
- `unsupported` prints a reason (for example an unresolved image workdir) and does not pass either.

Check the prover itself with one deliberately out-of-boundary candidate, so a pass means something.

A pass does not prove the policy is minimal or enforced. Still run `run.sh negative`: an unlisted host is blocked, host paths are not visible, and a write to a read-only path fails.
