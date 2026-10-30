# NVIDIA OpenShell how-to

Commands checked against `openshell` 0.1.5 (`openshell <cmd> --help`). Install, gateway and first run: `setup-smoketest-openshell` skill. File syntax: [config file reference](config-file-reference.md). On Windows run every `openshell` command inside WSL2.

## 1. Prerequisites

A running gateway (`openshell sandbox list` works) and an image that contains the agent CLI. `--from` takes an image reference, not a Dockerfile: build and tag it with the engine the gateway uses.

```sh
docker build -t myproj-sbx:dev sandbox/
```

## 2. Start a session

Stage only the files the task needs, then create the sandbox with the policy and the upload:

```sh
STAGE=$(mktemp -d); cp -r src tests pyproject.toml "$STAGE"/      # exclude sandbox/, .git, host agent config
openshell sandbox create --name myproj --from myproj-sbx:dev \
  --policy sandbox/policy.yaml --provider <name> --upload "$STAGE:/sandbox/"
```

Do not upload the repo root: `.gitignore` is applied, but untracked files that are not ignored are still sent. Do not add a trailing command together with `--upload`. Add `--cpu`, `--memory` as needed. Without `--no-keep`, the sandbox persists after its first command exits.

## 3. Work in the session

```sh
openshell sandbox list
openshell sandbox connect myproj                            # interactive shell
openshell sandbox exec -n myproj --workdir /sandbox/src --no-login-shell \
  -- claude -p "run the tests and fix failures"             # one-off non-interactive run
openshell sandbox stop myproj                               # preserves the workspace
openshell sandbox start myproj
```

`exec` does not inherit the image's `ENV`. Pass non-secret variables with `--env KEY=VALUE`. Secrets go through a provider.

## 4. Change permissions

Filesystem, Landlock and process settings are fixed at start. Network policy reloads live.

| Need | Command | Applies |
|---|---|---|
| See the effective policy | `openshell policy get myproj --full` (`--base` omits provider rules) | n/a |
| Save it for review | `openshell sandbox get myproj --policy-only > sandbox/effective.yaml` | n/a |
| See denials | `openshell logs myproj --since 10m --source sandbox` (`--tail` to stream) | n/a |
| Allow an endpoint | `openshell policy update myproj --rule-name X --binary /usr/bin/npm --add-endpoint registry.npmjs.org:443:read-only:rest:enforce --wait` | Live |
| Preview a change | add `--dry-run` | n/a |
| Remove a rule | `openshell policy update myproj --remove-rule X` | Live |
| Replace the whole network policy | `openshell policy set myproj --policy sandbox/policy.yaml --wait` | Live |
| Review an agent's request (Policy Advisor) | `openshell rule get myproj --status pending`, then `rule approve` or `rule reject` | Live |
| Add or remove a path, change user or Landlock mode | edit `policy.yaml`, recreate | Recreate |
| Add or change a credential | create or update a provider in your own shell, re-attach with `--provider` | Recreate |

The endpoint format is `host:port[:access[:protocol[:enforcement]]]`. Set `enforce` explicitly: enforcement defaults to `audit`, which logs but does not block.

## 5. Make a live change permanent

Live edits are lost when the sandbox is deleted. Copy every rule you added into `sandbox/policy.yaml`, then prove it:

```sh
openshell sandbox get myproj --policy-only > sandbox/effective.yaml
openshell-prover check sandbox/effective.yaml --boundary sandbox/boundary.yaml   # only `within_boundary` passes
openshell sandbox delete myproj
# re-run the create command from section 2, then repeat the task
```

Add a line to `sandbox/DECISIONS.md` for each widening. Keep `boundary.yaml` as the most access you would ever accept; widen it only deliberately.

## 6. Get results out, and the git workflow

OpenShell never touches your repository. The sandbox holds a **copy** of the files you uploaded, and nothing syncs back. [`scripts/pull_openshell_changes.py`](../../../scripts/pull_openshell_changes.py) does the return trip: it packages the changes inside the sandbox, downloads them, and applies them on a **new local branch** with git. You review with normal git tools; there is no hand copying of files.

```
your repo --upload--> copy in sandbox --agent edits--> patch(es) --download--> new host branch (temporary worktree) --> review, merge, push
```

```sh
# 1. Before the agent starts: give the uploaded copy a baseline commit and tag
openshell sandbox exec -n myproj --workdir /sandbox/src --no-login-shell -- sh -c \
  'git init -q && git add -A && git -c user.name=base -c user.email=base@x commit -qm baseline && git tag baseline'
# 2. ... the agent works ...
# 3. From your repo (at the commit you uploaded): prove the patch applies, then pull for real
python scripts/pull_openshell_changes.py myproj --repo . --dry-run
python scripts/pull_openshell_changes.py myproj --repo .            # creates branch agent/myproj
# 4. Review with git; merge when satisfied (or pass --merge to fast-forward in step 3)
git log --stat main..agent/myproj
git merge --ff-only agent/myproj
```

- Modes: `--mode commits` keeps the agent's own commits (`git format-patch` and `git am`), `--mode diff` makes one commit from everything changed since `baseline` including uncommitted and new files, and `auto` (default) picks commits when the agent committed everything.
- Your working tree and current branch are not touched unless you pass `--merge` (fast-forward only). Git hooks are disabled while the patch is applied, and the script lists CI, build, hook and `sandbox/` files it changed. Review the branch as untrusted code.
- The patch applies cleanly only if your repo is at the same commit you uploaded: commit or stash local changes before staging the upload and do not move on until you have pulled. A conflict exits 3 and leaves no branch behind.
- Upload without `.git`; the baseline commit gives the sandbox its own small history, separate from your repo. The sandbox image needs `git`.
- On Windows run it from WSL2, or from PowerShell: it finds `openshell` or `wsl -e openshell` itself (`--openshell` overrides). Options and exit codes: [scripts/README.md](../../../scripts/README.md).
- The script's `exec` and `download` calls are the documented commands: `download` reaches only the sandbox working directory, which is why the scratch folder is `/sandbox/.sandbox-pull`.
- **Alternative: let the agent push.** Attach a GitHub provider limited to one repository and add a network rule that allows pushes to that repository only (the NVIDIA GitHub tutorial describes this; verify it against the live docs). The agent pushes a branch and you review the pull request. This puts a write credential within the sandbox's reach, so the user decides.
- `openshell sandbox delete` purges everything not downloaded or pushed.

## 7. Stop and delete

```sh
openshell sandbox stop myproj        # keeps state
openshell sandbox delete myproj      # removes state; download first
```

## 8. Credentials

The user runs these in their own shell (WSL2 on Windows). `openshell provider create --name X --type T --from-existing` reads the secret from the shell's environment. The sandbox sees a placeholder. List with `openshell provider list`. OpenShell providers do not hold a Claude subscription. For Claude Code, log in with your subscription inside the sandbox (`claude auth login`; the template `run.sh login`). Do not use `claude setup-token`. Details: [develop-sandbox/openshell/CREDENTIALS.md](../../../.claude/skills/develop-sandbox/openshell/CREDENTIALS.md).

## 9. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Request blocked | No matching endpoint, or the calling binary is not listed | `openshell logs`, then add the endpoint with `--binary` for the real binary path (section 4), then persist (section 5) |
| `tar: ... Cannot mkdir: Permission denied` on upload | Filesystem policy denies the target or a parent | Add the path to `read_write` (parents need at least `read_only`), recreate |
| `exceeds_boundary` from the prover | Policy has access outside `boundary.yaml` (gateway defaults `/var/log`, `/dev/urandom`, `/dev/null` count) | Narrow the policy, or widen the boundary deliberately |
| `unsupported` from the prover | Unresolved image workdir | Set `include_workdir: false` and list paths |
| Tool not found in `exec` | `exec` skips image `ENV` | Pass `--env` or use absolute paths |
| `useradd` fails at image build | Base image already owns UID 1000 | Use another UID |
| Sandbox user cannot write a build-time cache | Build ran as root | Delete it in the same `RUN` |
| `docker` or `openshell` refused from an agent's own bash sandbox | Sandbox-caused (WSL2 with Docker Desktop) | Ask the user before running with the bypass |
