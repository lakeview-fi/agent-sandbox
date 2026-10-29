# Harness analyses index

Agent harnesses run the model and expose its tools. These notes cover each harness's built-in sandbox, approval, and policy controls.

- [Claude Code Sandbox](claude-code-analysis.md) — OS-enforced shell sandbox (Seatbelt or bubblewrap), proxy-based network controls, and admin policy. Not available on native Windows.
- [Codex Sandbox](codex-analysis.md) — command sandbox with read-only, workspace-write, and full-access modes, plus approval settings. Compares local sandboxing with cloud execution.
- [Pi-dev Sandbox](pi-dev-analysis.md) — no built-in OS sandbox or per-tool prompts. Covers external isolation options and community permission extensions.

See also: [Execution analyses](../execution/index.md) and [Synthesis](../synthesis/index.md).
