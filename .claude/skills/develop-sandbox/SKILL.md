---
name: develop-sandbox
description: Develop, test and harden an application-specific agent sandbox for a project, with NVIDIA OpenShell or Docker Sandboxes (sbx). The skill copies starter templates (image, policy or environment file, run steps, DECISIONS.md, README.md, acceptance task) into the target repo, adapts them, runs the user's agent on a representative task, and iterates until the sandbox is safe and capable. Use when the user wants a project sandbox built or tuned, an OpenShell policy or sbxenv.yaml/kit written or debugged, or an agent's sandbox permissions tightened.
---

# Develop a sandbox for a project

Method (inputs, loop, safety and capability review, deliverables): [developing-an-app-sandbox.md](../../../docs/guides/developing-an-app-sandbox.md). **Read it first.** This file holds the rules shared by both sandbox types. Each type's specifics are in its own folder.

## 1. Starting message: type and customizations

Before reading deeply, skim the project (README, AGENTS.md or CLAUDE.md, justfile or Makefile, how issues and agents are used). Then send **one short `AskUserQuestion` call**. Ask only about what applies, and put your recommendation first.

1. **Sandbox type**, unless the user named it (table below). Never pick one silently. If the agent must commit and the commits must reach the host, recommend Docker. For Docker, then ask the repo mode: **direct mount** (default: results land in the host repo at once, but the agent can change files that later run on the host) or **clone** (safer: results come back as commits you pull and review). OpenShell has only an uploaded copy, whose changes come back with `run.sh pull` (see its GUIDE).
2. **Host data the tools need:** for example a local database or a cache in the home directory. Choose read-write, a copy, or read-only, and say what each choice breaks.
3. **Agent definitions and tooling outside the repo:** custom agents, skills, CLIs built from a sibling repo. Mount read-only and install at create time, or bake into the image.
4. **Extras:** git push credentials, other repos read-only, web access beyond package registries.

Customizations like these are normal. Each one becomes a mount, a setup step or a network rule, with a line in `DECISIONS.md`. If the user's answer raises a design question (for example "one sandbox for several repos?"), answer it in one or two sentences with a recommendation, then proceed.

### Sandbox types

| Type | Folder | Prerequisite | Notes |
|---|---|---|---|
| NVIDIA OpenShell | [openshell/](openshell/) | the matching `setup-smoketest-openshell` run has passed on the user's machine | Container with policy, prover and upload. Experimental on Windows (WSL2). |
| Docker Sandboxes (`sbx`) | [docker/](docker/) | the matching `setup-smoketest-docker-sandbox` run has passed on the user's machine | microVM. Claude subscription login with the token held by the proxy. Host scripts are PowerShell only; macOS and Linux are not yet supported ([PLATFORM-NOTES.md](docker/PLATFORM-NOTES.md)). |

**Maturity: Docker has been tested more, so it is likely the more mature type.** Tell the user when they choose, and recommend Docker unless they have a reason for OpenShell. Tested so far (`sbx` v0.50.1, `openshell` 0.1.5, Windows 11):
- **Docker, tested end to end:** subscription login held by the proxy; a custom agent completing a project task with its commit pulled and merged; both repo modes; recreating the sandbox from its files; negative tests; path-limited network rules; a kit image build; the policy-log watcher.
- **OpenShell, tested:** the templates, written against a Python project. Claude Code completed a task through an OpenRouter provider (smoketest).
- **OpenShell, not yet tested:** the Claude subscription login inside a sandbox (its CREDENTIALS.md); a full acceptance run with the pull script on a second project. It is also experimental on Windows.

**Checking which types are installed:** look where each CLI lives. On Windows, `sbx` is a Windows binary (check from PowerShell or Git Bash), but `openshell` is installed inside WSL2 and is not on the Windows PATH. Check it with `wsl -- bash -lc 'command -v openshell && openshell --version'`. Do not report OpenShell as missing from a Windows-side `which` alone. On macOS and Linux, check both on the host PATH.

Then read that folder's `GUIDE.md`, `CREDENTIALS.md` and `PLATFORM-NOTES.md` before drafting files.

## 2. Ground rules (both types)

- **Asking the user:** when you need a decision or missing input, ask with the `AskUserQuestion` tool, not in free prose. Give each question 2–4 concrete options, put your recommended option first and label it "(Recommended)", and say briefly why you recommend it. Ask several related questions in one call where possible.
- **Purpose of the sandbox:** unless the user says otherwise, or the project's `AGENTS.md`, `CLAUDE.md` or `README.md` makes the purpose clear, assume it is for **coding** (building, testing and changing the project's source code). Use that assumption to pick the default representative task, tools and network hosts, and state it in `DECISIONS.md`.
- Ask before installing, logging in, creating providers or secrets, or any step that widens access to credentials, host-write paths or broad egress.
- **Hard requirement:** the sandboxed agent (for example Claude Code) must itself complete the acceptance task inside the sandbox. Checks run with `exec` prove the plumbing but do not replace it. If the agent cannot authenticate or reach its model API, the sandbox is not done. Say so and stop at the credential step.
- **Credentials:** the user creates and stores every secret. Never ask them to paste one, and never read one. Follow the type's `CREDENTIALS.md`.
- **Claude Code authentication: use the developer's Claude subscription login** (`claude auth login`, the same flow as on the host), done by the user in a real terminal. **Do not use `claude setup-token`** and do not suggest it: it mints a long-lived token that ends up in an environment variable the agent can read, and it is not the developer's normal login. An API key (Console billing) is a fallback the user must choose explicitly.
- **Exposure risks:** explain the current exposure risks to the user twice: before the sandbox is launched, and again after the development is finished. Name each uploaded, mounted or writable path, each network endpoint and each credential, and what the sandboxed agent could do with it. Examples: a writable path lets the agent delete or overwrite files in it; an endpoint with write access lets the agent make harmful writes through that API. Say what is blocked, what is still reachable, and what the user can narrow.
- **Root installs belong in an image.** Setup scripts that run at create time are for user-level, per-checkout steps (CLIs in the home folder, agents and skills, git config, dependency sync). When the sandbox needs root or system changes (apt packages, system libraries, browsers, changed package sources), first make them work at create time with the narrowest network rules. Then move them into an image built from the type's image definition (Docker: a kit with `kit.dockerfile`, see its GUIDE "Image"; OpenShell: its Dockerfile). Base it on the image the verified setup used, pin versions that must match the repo's lockfiles, and drop the build-only hosts from the runtime policy. Tell the user when you switch, and record it in `DECISIONS.md`, including the commit to roll back to. Docker with Claude Code: a kit's subscription login failed in testing, so keep the root installs in setup until that is resolved (docker GUIDE, "Image", Status).
- Default definition directory is `sandbox/`. Create files there unless the user names another path. The sandboxed agent must not be able to edit it (see the type's guide).

## 3. Install the templates into the target repo

Start from the templates. Do not hand-write the files from scratch.

1. Copy `<type>/templates/` into `<target>/sandbox/`. Rename `gitattributes` to `.gitattributes` and `gitignore` to `.gitignore`. Skill packaging can drop dotfiles, so they are stored without the dot.
   **Docker: always create both env files.** `start.ps1` needs them, and sbx merges them only when it gets no PATH:
   - `sbxenv.yaml` → the **repo root**, not `sandbox/`: name, `workspace: .`, per-repo env such as the venv path. One per repo.
   - `global-sbxenv.yaml` → `~/.sbxenv.yaml`: agent, mounts shared by the user's repos (tool data, custom agents, CLI sources) and their env vars, sizing. One per machine. If it already exists, merge into it and show the user the diff before you write it: it affects every sandbox on the machine.
   - Put a value in the repo file only when it is specific to the repo. Check the merged result with `sbx env plan` from the repo root.
2. Read the project (language, package manager, build and test commands, registries, git host), then adapt the parts marked `ADAPT:` in each file. Leave the rest. The defaults are a Python project with `uv`, Claude Code as the agent, and deny-by-default network. The repo comes in as an uploaded copy (OpenShell), or as a direct mount with a clone option (Docker).
3. Write the project's acceptance task into `TASK.md` (section 5). Fill the "Environment" and "Scope" sections of `DECISIONS.md`.
   Copy the pull scripts into the project: this repo's [`scripts/`](../../../scripts/README.md) files `pull_docker_commits.py` (Docker) or `pull_openshell_changes.py` (OpenShell), plus `sandbox_git_common.py`, into `sandbox/scripts/` (resolve the source from this skill's own location, `../../../scripts`). `pull.ps1` and `run.sh` already point there. The copy belongs to the project, so adapt it when the repo needs it (a different default branch, extra review globs in `needs_review`) and record changes in `DECISIONS.md`. Tell the user the copy is host-run code: in direct mode the agent can edit `sandbox/scripts/`, so they review its diff like `sandbox/*.ps1` before every pull. Do not copy the tests.
4. Remove every `ADAPT:` marker you resolved. A marker left in a file means an open decision. List it under "Pending" in `DECISIONS.md`.

## 4. Workflow

Follow the method's loop with the type's commands (see its `GUIDE.md`).

### Reporting during the run

Tell the user as you go, in short lines, without stopping the build:
- each policy or access grant you apply (host, path, upload or mount, credential, host-side command or git change), with its reason, and the same line in `DECISIONS.md`;
- each problem you observe (failed build, denied request, permission error, upload, mount or ownership issue), with the exact error text, and what you did about it.

Report only what happened. Do not wait for an answer unless the step needs approval under the ground rules.

### Bringing the agent's work back

Use the project's copy of the pull scripts (`sandbox/scripts/`), never ad hoc `git fetch` or hand copying. They create a new local branch, leave the user's working tree alone, disable git hooks while applying, and list the files that need review ([scripts/README.md](../../../scripts/README.md)).

- Docker, direct mode (default): nothing to bring back. The agent's edits and commits are already in the host repo. Show the user `git log` and `git diff` instead, and point out any changed file that runs on the host (hooks, scripts, build files).
- Docker, clone mode: `pull.ps1` runs [`pull_docker_commits.py`](../../../scripts/pull_docker_commits.py). The sandbox must be running. `stop.ps1` and `start.ps1 -Recreate` pull before they stop or remove it.
- OpenShell: `run.sh pull` runs [`pull_openshell_changes.py`](../../../scripts/pull_openshell_changes.py). It needs the `baseline` tag from `run.sh baseline` and a repo at the staged commit.

Run the pull once with the acceptance task's result (`--dry-run` first for OpenShell), show the user the commit list and the review list, and let the user decide about `--merge`. Never merge for the user. Pulled work is untrusted: read the flagged files before running anything.

## 5. Suggested representative task (preliminary)

Use this when the user has not named an acceptance task yet, and always ask them to confirm it. It exercises a typical coding loop plus the sandbox's network and tool access:
1. Make a small, named code change in the sandbox copy and add or update a test for it.
2. Run the project's test command and report the result.
3. Install one language package the project needs, to prove package-registry access. A system package install needs root. Drop it unless the sandbox type runs it as root by design (see the type's guide).
4. Fetch the documentation of one library the change depends on, to prove general web access where the policy allows it.

If the project does not use Python, substitute its own tooling (for example npm, Go or Maven). For a non-code project, use a task that reads and writes its real files instead.

## 6. Finish

Run the type's safety checks and negative tests, then recreate from the committed files, run the acceptance task once more and pull its result with the pull script (the handoff is part of "capable"). Finish with the deliverables listed in the method doc, and give the second exposure-risk summary.
