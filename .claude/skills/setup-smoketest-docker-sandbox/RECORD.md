# Recording a trial

The record lives in the repo that contains this skill (the skill's own `docs/`), not in whichever repo the shell happens to be in: `docs/trials/docker-sandboxes-<os>.md`, with `<os>` one of `windows`, `macos`, `linux`. `docs/index.md` must mention `trials/`.

## Rules

- **Append, never overwrite.** A file may already hold an earlier run. Add a `## Run N (<date>, same host and sbx version)` section; an existing file with no `## Run` headings counts as run 1.
- `python -I smoketest.py --record` does this: it writes the Run section with `sbx version`, host OS and version, date, every check with its result, and the full kit-host listing. It creates the file (and `docs/trials/`) when missing.
- Add by hand, under the run: **Findings** (anything unexpected, with the evidence), **Docs check** (see [CHECKS.md](CHECKS.md)), the host as WSL2 on Windows 11 when that applies, and that tests ran via `sbx exec` and the agent's own `/login` was not exercised.
- Do not paste secrets or token values. Names and value lengths only.

## Findings

Anything unexpected is a finding: an INFO observation that turns out to be a hole, a kit host you did not expect, a FAIL, a doc that disagrees with the live docs. Write what was observed, how to reproduce it, and whether it is resolved. Unresolved items carry forward: list them again in the next run until classified.
