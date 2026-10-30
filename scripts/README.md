# Scripts

Helper scripts for humans and agents. Python 3, standard library only. Run them from the shell where the sandbox tool works: PowerShell, macOS or Linux shell for Docker Sandboxes (`sbx`); WSL2 for OpenShell on Windows (or any shell, the OpenShell script finds `openshell` or `wsl -e openshell` itself).

| Script | Purpose |
|---|---|
| [`pull_docker_commits.py`](pull_docker_commits.py) | Bring the commits an agent made in a Docker Sandbox clone (`sbx --clone`) into a local branch of the host repo. |
| [`pull_openshell_changes.py`](pull_openshell_changes.py) | Bring the changes an agent made in an OpenShell sandbox copy into a local branch of the host repo, as the agent's commits or one combined commit. |
| [`sandbox_git_common.py`](sandbox_git_common.py) | Shared git helpers (not run directly). |

**In a project sandbox:** the `develop-sandbox` skill copies these scripts (without the tests) into the project's `sandbox/scripts/`, and the template `pull.ps1` and `run.sh pull` call that copy. This folder stays the source; a project copy is adapted per repo and does not follow later changes here.

## Docker Sandboxes

```sh
python scripts/pull_docker_commits.py my-sandbox --repo path/to/repo            # fetch, show, create branch agent/my-sandbox/<branch>
python scripts/pull_docker_commits.py my-sandbox --repo path/to/repo --merge    # also fast-forward the current branch
```

The sandbox must be running (`sbx run --name my-sandbox`): the `sandbox-<name>` remote is served from inside it. Fetch before `sbx rm`, which deletes the clone.

## OpenShell

Before the agent starts, make a baseline commit inside the uploaded copy (the upload has no `.git`):

```sh
openshell sandbox exec -n my-sandbox --workdir /sandbox/src -- sh -c 'git init -q && git add -A && git -c user.name=base -c user.email=base@x commit -qm baseline && git tag baseline'
```

After the agent is done, from the host repo (checked out at the commit you uploaded):

```sh
python scripts/pull_openshell_changes.py my-sandbox --repo path/to/repo               # new branch agent/my-sandbox
python scripts/pull_openshell_changes.py my-sandbox --repo path/to/repo --dry-run     # prove the patch applies, keep nothing
python scripts/pull_openshell_changes.py my-sandbox --repo path/to/repo --merge       # also fast-forward the current branch
```

`--mode commits` keeps the agent's commits, `--mode diff` makes one commit from everything changed since the baseline (including uncommitted and new files), `auto` (default) picks commits when the agent committed everything.

## What both scripts guarantee

- Your working tree and current branch are not changed unless you pass `--merge`, and then only by fast-forward. A dirty tracked tree is refused.
- Git hooks are disabled while pulled content is checked out or applied, so a hook script the agent committed does not run on the host.
- Files that execute or configure things later (CI, build files, hooks, `sandbox/` definition files, shell scripts) are listed for review. The pulled work is untrusted code: read it before running it.
- The last output line is `RESULT: ...`; exit codes are 0 ok (or nothing new), 1 error, 2 ambiguous branch (Docker), 3 not a fast-forward or patch does not apply.

## Tests

```sh
python -m unittest discover -s tests -t .
```

`tests/scripts/` mirrors this folder. The Docker and OpenShell setup skills also run the scripts against a real sandbox on a temporary branch (checks 9 and 10).
