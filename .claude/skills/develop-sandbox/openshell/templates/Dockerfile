# OpenShell image: Claude Code on Node 22, the project toolchain, and the OpenShell supervisor.
#
# Build-time network is not governed by the sandbox policy; runtime network is (policy.yaml).
# The workload user comes from policy.yaml (process.run_as_user), not from USER here: the
# supervisor starts as root.
#
# Build: sh sandbox/run.sh build
# ADAPT: pin the versions below to the ones you tested; record them in DECISIONS.md.
FROM node:22-bookworm-slim

COPY --from=ghcr.io/nvidia/openshell/sandbox:0.1.5 /openshell-sandbox /openshell-sandbox

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g @anthropic-ai/claude-code@2.1.312 \
    && claude --version

# --- ADAPT: project toolchain (default: uv with a managed Python 3.12) ------------------------
# Install interpreters at build time: at runtime no policy rule allows a download host.
# Anything the build writes under an ENV path (for example a cache under /tmp) is owned by root;
# delete it in the same RUN, or the sandbox user cannot write there. Keep run.sh RUN_ENV in step.
COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /uvx /usr/local/bin/
ENV UV_PYTHON_INSTALL_DIR=/opt/uv-python \
    UV_PYTHON=3.12 \
    UV_PYTHON_DOWNLOADS=never \
    UV_CACHE_DIR=/tmp/uv-cache
RUN UV_PYTHON_DOWNLOADS=automatic uv python install 3.12 \
    && chmod -R a+rX /opt/uv-python \
    && rm -rf /tmp/uv-cache
# --- end of toolchain -------------------------------------------------------------------------

# The policy's run_as_user is "sandbox"; the user must exist in the image.
# UID 1001: the node base image already uses UID 1000 for its "node" user.
RUN useradd --create-home --uid 1001 sandbox \
    && mkdir -p /sandbox \
    && chown sandbox:sandbox /sandbox

WORKDIR /sandbox
ENTRYPOINT ["/openshell-sandbox"]
