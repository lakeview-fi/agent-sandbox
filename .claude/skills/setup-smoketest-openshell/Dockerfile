# Trial image for setup-smoketest-openshell: Claude Code on Node 22, plus the
# OpenShell supervisor copied from the matching OpenShell sandbox base image.
#
# Build (from the skill folder, with the sandbox disabled if your shell needs it):
#   docker build -t trial-claude:local -f Dockerfile .
#
# Claude Code requires Node >= 22 (the build warns otherwise), so the base is
# a Node 22 image rather than Ubuntu's packaged Node.
FROM node:22-bookworm-slim

COPY --from=ghcr.io/nvidia/openshell/sandbox:0.1.5 /openshell-sandbox /openshell-sandbox

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates curl python3 python3-pip python3-venv \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g @anthropic-ai/claude-code@2.1.312 \
    && claude --version

WORKDIR /sandbox
ENTRYPOINT ["/openshell-sandbox"]
