# OpenShell sandbox for this project

Definition for running Claude Code on this project in an NVIDIA OpenShell sandbox. Access grants and their reasons are in [DECISIONS.md](DECISIONS.md).

| File | Purpose |
|---|---|
| `Dockerfile` | Image: Claude Code, the project toolchain, OpenShell supervisor |
| `policy.yaml` | Runtime policy: filesystem, landlock, process, network (deny by default) |
| `boundary.yaml` | Most access this sandbox may have; `openshell-prover` checks the policy against it |
| `run.sh` | Each step as a reproducible command |
| `TASK.md` | Acceptance task for the sandboxed agent |
| `DECISIONS.md` | Access grants, deviations, pending decisions |

## Steps

Run from the repo root in Linux or WSL2 (not PowerShell). Each step prints its commands. The gateway must report `Connected` (`openshell status`) first.

```sh
sh sandbox/run.sh build      # build the image
sh sandbox/run.sh stage      # copy the uploadable tree to a temp dir
sh sandbox/run.sh create     # create the sandbox and upload the staged tree to /sandbox/src
sh sandbox/run.sh login      # Claude subscription login inside the sandbox (interactive, see below)
sh sandbox/run.sh baseline   # inside the sandbox: git init and baseline commit
sh sandbox/run.sh test       # project checks inside the sandbox
sh sandbox/run.sh agent      # claude -p with TASK.md and an explicit tool allowlist
sh sandbox/run.sh negative   # blocked host, hidden host path, read-only write must fail
sh sandbox/run.sh safety     # save the effective policy; openshell-prover against boundary.yaml
sh sandbox/run.sh pull       # bring the agent's changes back as local branch agent/<name> (see below)
sh sandbox/run.sh teardown   # delete the sandbox and the staged tree
```

Recreate from these files to prove reproducibility: `teardown`, then the steps above.

## Claude login

`login` runs `claude auth login` inside the sandbox: the same subscription login as on your host. Run it in your own terminal (in a Claude Code session, type `! sh sandbox/run.sh login`). Open the printed URL in your browser, approve, and paste the one-time code back if asked. The tokens stay inside the sandbox and are discarded by `teardown`. Each new sandbox needs a new login.

Do not use `claude setup-token` or pass a token with `--env-from`.

## Getting results out

The sandbox works on an uploaded copy and nothing syncs back. `sh sandbox/run.sh pull` packages the agent's changes inside the sandbox, downloads them and applies them on a **new local branch** `agent/<name>` (built in a temporary worktree, so your working tree and current branch are untouched). It uses the agent's own commits when it committed everything, and one combined commit otherwise.

```sh
sh sandbox/run.sh pull --dry-run   # prove the patch applies; keep nothing
sh sandbox/run.sh pull             # create the branch, list commits and the files that need review
sh sandbox/run.sh pull --merge     # also fast-forward your current branch (hooks off; refuses otherwise)
```

Commit or stash your local changes before `stage`, and keep the repo at that commit until you have pulled: the patch is made against the uploaded state. Pull before `teardown`, which deletes the sandbox copy. Review the branch as untrusted code; the script lists CI, build, hook and `sandbox/` files it changed.
