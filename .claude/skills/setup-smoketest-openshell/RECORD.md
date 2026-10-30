# Recording a trial

The record lives in the repo that contains this skill (the skill's own `docs/`), not in whichever repo the shell happens to be in: `docs/trials/openshell-<os>.md`, with `<os>` one of `windows-wsl2`, `macos`, `linux`. `docs/index.md` must mention `trials/`.

## Rules

- **Append, never overwrite.** A file may already hold an earlier run. Add a `## Run N (<date>, ...)` section; an existing file with no `## Run` headings counts as run 1.
- `python3 -I smoketest.py --record` does this: it writes the Run section with the `openshell` version, host OS, date, every check with its result, and the full base and effective policy text. It creates the file when missing.
- Add by hand, under the run: **Findings** (anything unexpected, with the evidence), **Docs check** (see [CHECKS.md](CHECKS.md)), the route and driver (`/dev/kvm` result, Docker or MicroVM), the image tag, Node and Claude Code versions and supervisor tag, the sandbox name and creation command, the approvals given (including the bash-sandbox bypass), and what was torn down and what was left (including sandboxes this run did not create).
- Do not paste secrets or token values. Names, lengths and short hashes only.

## Findings

Anything unexpected is a finding: a FAIL, an INFO observation that turns out to be a hole, a SKIP caused by the platform or image, a doc that disagrees with the live docs. Write what was observed, how to reproduce it, and whether it is resolved. Unresolved items carry forward: list them again in the next run until classified.
