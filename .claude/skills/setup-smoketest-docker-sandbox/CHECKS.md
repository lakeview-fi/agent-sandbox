# Checks around the smoke test

`smoketest.py` performs the preflight, post-create and teardown checks below and fails on the first preflight problem. Read this file to know what they cover and to do the ones a script cannot.

## Before creating the sandbox

Scripted:
- `sbx version`, `sbx ls`, `sbx policy ls` all succeed (this also proves the user is signed in and the daemon is up: skip asking for `sbx login` when they work).
- `default-deny-all` is listed. If it is, do not run `sbx policy init` again.
- The sandbox name is free. The script uses `trial-<HHMMSS>`. Never stop, remove or change a sandbox you did not create; other sandboxes on the machine belong to the user.
- `sbx diagnose --format json` runs and its report is read when anything fails. Never pass `--upload`: it sends data to Docker.

By hand:
- **Live docs.** Fetch https://docs.docker.com/ai/sandboxes/install/ and https://docs.docker.com/ai/sandboxes/get-started/ and compare the commands this skill uses with them and with `sbx create --help`. Record "docs checked <date>, no differences" or list the differences. Do not skip this: the skill says the live docs win.
- **Existing record.** Look for `docs/trials/docker-sandboxes-<os>.md` in the repo that holds this skill. It is appended to, never overwritten ([RECORD.md](RECORD.md)).
- **Hypervisor.** If the Windows feature query needs elevation, `sbx diagnose` stands in for it; do not block on elevation.
- **Non-interactive verbs.** Before telling the user to run something, check `sbx --help` and `sbx <verb> --help` for a verb that works without a terminal.

## Right after creating

Scripted:
- The source mount is read-only (`(ro)`).
- The kit policy hosts are listed with `sbx policy ls <name> --wide` and copied to the record.
- The guest working directory is the mirrored host path.
- A baseline of pending approvals is taken before the tests.

## After teardown

Scripted: `sbx rm --force` succeeded; the sandbox is gone from `sbx ls`; every other sandbox is unchanged; no policy scoped to the sandbox and no pending approval for it remains (the per-sandbox allow rule from test 2 is removed with the sandbox); the temp repo is deleted.

By hand: confirm the record file exists and `docs/index.md` mentions `trials/`.
