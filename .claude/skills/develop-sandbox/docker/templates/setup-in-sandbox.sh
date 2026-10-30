#!/bin/bash
# Runs INSIDE the Docker Sandbox as user `agent`, after create (start.ps1 pipes it in).
# Must be safe to run again (start.ps1 -Resetup). Arguments from start.ps1:
#   $1 repo path in the sandbox   $2 mode: direct | clone   $3 git user.name   $4 git user.email
#   $5 git core.hooksPath of the host repo ("" if unset)
set -euo pipefail
REPO=$1 MODE=$2 GIT_NAME=$3 GIT_EMAIL=$4 HOOKS_PATH=${5:-}
export PATH="$HOME/.local/bin:$PATH"

# --- ADAPT: tools, agents and skills -----------------------------------------------------------
# Paths of shared mounts come from env vars set in ~/.sbxenv.yaml. Examples:
#   CLI from a read-only sibling repo: the build writes into the source tree, so copy it first.
#     build_dir=$(mktemp -d)
#     tar -C "$SBX_TOOL_SRC" --exclude=.git --exclude=.venv -cf - . | tar -C "$build_dir" -xf -
#     uv tool install --quiet --force "$build_dir"; rm -rf "$build_dir"
#   `just` for justfile recipes and hooks:   uv tool install --quiet rust-just
#   Custom agents and skills at user level, so they never land in the repo's commits:
#     mkdir -p ~/.claude/agents && cp "$SBX_AGENTS_DIR"/*.md ~/.claude/agents/
#     mkdir -p ~/.claude/skills/mytool && cp -r "$SBX_TOOL_SRC/.github/skills/mytool/." ~/.claude/skills/mytool/
# User-level steps only. Anything needing sudo (apt packages, browsers, system libraries) goes into
# kit/kit.dockerfile once it works here (GUIDE.md, "Image"). With a kit, check versions baked into
# the image against the repo lockfile and fail with a rebuild hint, e.g. (Playwright):
#     baked=$(cat "$PLAYWRIGHT_BROWSERS_PATH/.playwright-version")
#     locked=$(node -p "require('./frontend/package-lock.json').packages['node_modules/playwright'].version")
#     [ "$baked" = "$locked" ] || { echo "ERROR: rebuild kit with Playwright $locked"; exit 1; }
# ------------------------------------------------------------------------------------------------

echo "== git ($MODE mode)"
# Identity and line endings go in the sandbox user's own ~/.gitconfig: on the host they usually come
# from global and system git config, which the sandbox does not see. Never write them into the
# repo's .git/config: in direct mode it is the host's own config.
git config --global user.name "$GIT_NAME"
git config --global user.email "$GIT_EMAIL"
# Windows hosts use core.autocrlf=true, so working-tree files may have CRLF. `input` commits LF.
git config --global core.autocrlf input
if [ "$MODE" = clone ] && [ -n "$HOOKS_PATH" ]; then
    # Only the clone has its own .git/config. (A direct mount shares the host's .git, which already
    # has core.hooksPath, and the mount shows every file as executable.)
    git -C "$REPO" config core.hooksPath "$HOOKS_PATH"
    # Hooks committed from Windows are often 100644; Linux git skips non-executable hooks silently.
    git -C "$REPO" config core.fileMode false
    find "$REPO/$HOOKS_PATH" -maxdepth 1 -type f -exec chmod +x {} +
fi

echo "== project dependencies"
cd "$REPO"
# ADAPT: git-ignored files the project expects (missing in a clone), for example tmp/ for
# pytest --basetemp. Use --frozen only if the lockfile is committed. The venv path comes from
# UV_PROJECT_ENVIRONMENT in sbxenv.yaml, outside the repo.
mkdir -p tmp
uv sync --quiet

echo "== checks"
claude auth status | grep -E '"(loggedIn|authMethod)"'
