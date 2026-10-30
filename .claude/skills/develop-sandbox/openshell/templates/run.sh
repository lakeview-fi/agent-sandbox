#!/bin/sh
# Build, create, upload, test and tear down this project's OpenShell sandbox.
# Run from anywhere inside the repo, in Linux or WSL2: sh sandbox/run.sh <step>
#   build     docker build the image
#   stage     copy the uploadable tree to a temp dir
#   create    create the sandbox from policy.yaml and upload the staged tree
#   login     Claude subscription login inside the sandbox (the user runs this in a real terminal)
#   baseline  inside the sandbox: git init and one baseline commit (the upload drops .git)
#   test      run the project checks inside the sandbox
#   agent     run Claude Code non-interactively on TASK.md
#   negative  run the negative tests (blocked host, hidden host path, read-only write)
#   safety    save the effective policy and run openshell-prover against boundary.yaml
#   pull      bring the agent's changes back as a local branch (extra args go to the script, e.g. --dry-run, --merge)
#   teardown  delete the sandbox and the staged tree
# Order: build, stage, create, login, baseline, test, agent, negative, safety, pull.
set -eu
set -x

ROOT=$(git rev-parse --show-toplevel)
SANDBOX_DIR="$ROOT/sandbox"
STAGE_FILE="$SANDBOX_DIR/.stage-path"   # local, git-ignored (see sandbox/.gitignore)

# --- ADAPT: project settings ------------------------------------------------------------------
PROJECT=$(basename "$ROOT")
NAME="$PROJECT-sbx"                      # sandbox name on the gateway
IMAGE="$PROJECT-sbx:dev"                 # image tag built by `build`
# The develop-sandbox skill copies the agent-sandbox repo's scripts/*.py here. Adapt the copy to this repo if needed.
AGENT_SANDBOX_SCRIPTS="$SANDBOX_DIR/scripts"
# Extra top-level paths to keep out of the upload (regex alternatives, for example 'data|runs').
# sandbox/ and .claude/ are always excluded.
STAGE_EXCLUDE=''
# Non-secret env for every exec: exec does not inherit the image's ENV. Keep in step with the Dockerfile.
RUN_ENV="UV_PYTHON=3.12 UV_PYTHON_INSTALL_DIR=/opt/uv-python UV_PYTHON_DOWNLOADS=never UV_CACHE_DIR=/tmp/uv-cache"
# Negative tests: a host no rule allows, and a host path that must not be visible.
NEG_HOST=https://example.com
NEG_PATH=/mnt/c                          # WSL2 drive mount; on macOS or Linux use a host-only path
NEG_WRITE=/usr/sandbox-write-test        # a path under a read_only entry

project_checks() {
    # ADAPT: the project's install, test, lint and type-check commands.
    run_in_sandbox uv sync --frozen
    run_in_sandbox uv run pytest
    run_in_sandbox uv run ruff check .
    run_in_sandbox uv run ruff format --check .
}

agent() {
    # Claude Code, non-interactive. Tools are an explicit allowlist, not --dangerously-skip-permissions.
    # ADAPT: the tools the acceptance task needs.
    run_in_sandbox claude -p \
        --allowedTools "Read" "Edit" "Write" "Grep" "Glob" "Bash(uv *)" "Bash(git *)" "Bash(curl *)" \
        "$(cat "$SANDBOX_DIR/TASK.md")"
}
# --- end of project settings ------------------------------------------------------------------

build() {
    docker build -t "$IMAGE" "$SANDBOX_DIR"
}

stage() {
    stage_dir=$(mktemp -d)
    mkdir "$stage_dir/src"
    exclude='sandbox|\.claude'
    if [ -n "$STAGE_EXCLUDE" ]; then
        exclude="$exclude|$STAGE_EXCLUDE"
    fi
    # Tracked and untracked, not git-ignored. Copies regular files only: a repo can hold device
    # nodes or sockets (for example a bind-mounted .zshrc) that tar cannot archive.
    git -C "$ROOT" ls-files -co --exclude-standard \
        | grep -v -E "^($exclude)/" \
        | while IFS= read -r file; do
            if [ -f "$ROOT/$file" ]; then
                mkdir -p "$stage_dir/src/$(dirname "$file")"
                cp -p "$ROOT/$file" "$stage_dir/src/$file"
            fi
        done
    printf '%s\n' "$stage_dir" > "$STAGE_FILE"
}

stage_path() {
    if [ ! -f "$STAGE_FILE" ]; then
        echo "no staged tree; run: sh sandbox/run.sh stage" >&2
        exit 1
    fi
    cat "$STAGE_FILE"
}

create() {
    # No credential is passed here. Claude Code logs in with the developer's subscription in the
    # `login` step. Do not add --env-from with a token (see the skill's CREDENTIALS.md).
    # --upload copies the staged tree to /sandbox/src. It cannot be combined with a trailing command.
    openshell sandbox create --name "$NAME" --from "$IMAGE" \
        --policy "$SANDBOX_DIR/policy.yaml" \
        --upload "$(stage_path)/src:/sandbox/"
}

login() {
    # Interactive: prints a URL to open in the host browser, then may ask for a one-time code.
    # Tokens are stored in /home/sandbox/.claude inside the sandbox, never on the host or in this repo.
    run_in_sandbox --tty claude auth login --claudeai
    run_in_sandbox claude auth status
}

baseline() {
    # The upload drops .git, so the baseline repo is made inside the sandbox. It gives the agent
    # git status and diff without the host history.
    run_in_sandbox git init -q
    run_in_sandbox git add -A
    run_in_sandbox git -c user.name=sandbox-baseline -c user.email=baseline@sandbox.invalid \
        commit -q -m "Uploaded baseline"
    # `pull` diffs against this tag.
    run_in_sandbox git tag baseline
}

pull() {
    # Applies the agent's changes to a NEW local branch agent/$NAME in a temporary worktree. Your working
    # tree and current branch stay untouched unless you pass --merge (fast-forward only). The repo must be
    # at the commit you staged: commit or stash local changes before `stage`, and do not move on until pulled.
    python3 "$AGENT_SANDBOX_SCRIPTS/pull_openshell_changes.py" "$NAME" --repo "$ROOT" "$@"
}

negative() {
    # Each command must FAIL. The `!` inverts the exit status, so a success is an error.
    ! run_in_sandbox curl -sS -m 10 "$NEG_HOST"
    ! run_in_sandbox ls "$NEG_PATH"
    ! run_in_sandbox touch "$NEG_WRITE"
}

safety() {
    openshell sandbox get "$NAME" --policy-only > "$SANDBOX_DIR/effective.yaml"
    openshell-prover check "$SANDBOX_DIR/effective.yaml" --boundary "$SANDBOX_DIR/boundary.yaml"
}

teardown() {
    openshell sandbox delete "$NAME"
    if [ -f "$STAGE_FILE" ]; then
        rm -rf "$(stage_path)"
        rm -f "$STAGE_FILE"
    fi
}

run_in_sandbox() {
    # Usage: run_in_sandbox [--tty] <command...>
    tty_flag=--no-tty
    if [ "${1:-}" = "--tty" ]; then
        tty_flag=--tty
        shift
    fi
    env_flags=""
    for kv in $RUN_ENV; do
        env_flags="$env_flags --env $kv"
    done
    # $env_flags is split on purpose: each entry is KEY=VALUE without spaces.
    # shellcheck disable=SC2086
    openshell sandbox exec -n "$NAME" --workdir /sandbox/src --no-login-shell "$tty_flag" \
        $env_flags -- "$@"
}

case "${1:-}" in
    build) build ;;
    stage) stage ;;
    create) create ;;
    login) login ;;
    baseline) baseline ;;
    test) project_checks ;;
    agent) agent ;;
    negative) negative ;;
    safety) safety ;;
    pull) shift; pull "$@" ;;
    teardown) teardown ;;
    *) echo "usage: sh sandbox/run.sh {build|stage|create|login|baseline|test|agent|negative|safety|pull|teardown}" >&2; exit 2 ;;
esac
