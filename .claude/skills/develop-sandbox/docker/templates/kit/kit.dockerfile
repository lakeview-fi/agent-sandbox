# syntax=docker/dockerfile:1
# Sandbox image: the built-in Claude Code image plus the project's root and system installs, run
# once at build time instead of by setup-in-sandbox.sh on every create (GUIDE.md, "Image").
# Contract (sbx): curl, git, CA certificates, /bin/sh and /bin/bash; USER agent; ENTRYPOINT starts the agent.
# ADAPT: the base image the built-in agent uses (the `Image:` line of `sbx create` output), so the
# kit differs from the verified setup only by what is added below.
FROM docker/sandbox-templates:claude-code-docker
USER root

# The base image lists apt sources for download.docker.com and cli.github.com. A deny-by-default
# runtime policy blocks them, and `apt-get update` then fails. Park them unless the agent needs them.
RUN mkdir -p /etc/apt/sources.list.disabled \
    && for f in docker.list github-cli.list; do \
         if [ -f "/etc/apt/sources.list.d/$f" ]; then mv "/etc/apt/sources.list.d/$f" /etc/apt/sources.list.disabled/; fi; \
       done

# --- ADAPT: root and system installs, moved here from setup once they work there -----------------
# Pin anything that must match a repo lockfile, write the pinned version to a marker file, and let
# setup-in-sandbox.sh fail with a rebuild hint when the lockfile moves on. Example (Playwright
# Chromium and its apt libraries; the version equals the one in the repo's lockfile):
#   ARG PLAYWRIGHT_VERSION=<version from the lockfile>
#   ENV PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright
#   RUN npx -y "playwright@${PLAYWRIGHT_VERSION}" install --with-deps chromium \
#       && chmod -R a+rX /opt/ms-playwright \
#       && echo "${PLAYWRIGHT_VERSION}" > /opt/ms-playwright/.playwright-version \
#       && rm -rf /var/lib/apt/lists/* /root/.npm
# Plain system packages:
#   RUN apt-get update && apt-get install -y --no-install-recommends <packages> \
#       && rm -rf /var/lib/apt/lists/*
# --- end of installs ---------------------------------------------------------------------------

USER agent
# As the built-in claude agent: permission prompts bypassed; the microVM, mounts and network policy
# are the boundary. start.ps1 passes the same flag to `claude -p` runs.
ENTRYPOINT ["claude", "--dangerously-skip-permissions"]
CMD []
