# Synthesis index

Cross-cutting notes that combine the harness and execution analyses.

- [Recommended local agent sandbox options](recommended-local-agent-sandbox-options.md) — which outer boundary to choose for local Claude Code, Codex or Pi work, and the setup workflow.
- [Comparative sandboxing analysis](comparative-sandboxing-analysis.md) — layered matrix comparing harness and runtime options by boundary, handoff, network and credentials, and operational fit; includes Docker vs OpenShell tables for sharing network and filesystem policy through version control.
- [Coding-agent risk scenarios and sandbox mitigations](coding-agent-risk-scenarios-and-sandbox-mitigations.md) — maps common risks to the controls that address them, and lists risks no sandbox removes.
- [Host-guest file sharing and version control](host-guest-file-sharing-and-version-control.md) — how files get into a sandbox, how agent changes return and reach git, how to share files scattered across the host, and how an agent can write to a host-side database, for Docker Sandboxes and OpenShell.
- [Dynamic access requests comparison](dynamic-access-requests-comparison.md) — how an agent asks for a new path or network destination mid-task, and how each product handles the request.
- [Custom chat UI with policy management](custom-chat-ui-policy-management.md) — design proposal (October 29, 2026) for a chat front end that manages OpenShell permissions and optional APF governance.
