# syntax=docker/dockerfile:1
# pi coding agent on the sbx claude-code base image (Ubuntu, non-root `agent`). Needs Node 22+.
FROM docker/sandbox-templates:claude-code
USER root
RUN node -e 'process.exit(+process.versions.node.split(".")[0] >= 22 ? 0 : 1)' && npm install -g @mariozechner/pi-coding-agent
USER agent
ENTRYPOINT ["pi"]
CMD []
