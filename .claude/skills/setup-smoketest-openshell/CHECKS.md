# Checks around the smoke test

`smoketest.py` performs the preflight, post-create and teardown checks below and stops only when nothing exists to test. Read this file to know what they cover and to do the ones a script cannot.

## Before creating the sandbox

Scripted:
- `openshell --version` works and `openshell status` shows `Connected`. A `Connection refused` or `permission denied` may be the agent's bash sandbox, not the gateway: see "Running Docker and gateway commands" in SKILL.md.
- The sandbox name is free (`trial-<HHMMSS>`). Record every existing sandbox; never delete one this run did not create (for example the user's own sandboxes).
- `/dev/kvm` is reported (MicroVM possible or Docker/Podman driver only, a weaker boundary).
- The image exists (`docker image inspect`). If it is missing, build it per [SANDBOX-IMAGE.md](SANDBOX-IMAGE.md), which needs network access and the user's yes, or use `--image default` and expect SKIPs.
- Providers in the gateway are listed; the first (or `--provider`) is attached for the inference check.

By hand:
- **Live docs.** Compare the commands in this skill with https://docs.nvidia.com/openshell/latest/ and with `openshell sandbox create --help` and `openshell policy update --help`. Record "docs checked <date>, no differences" or list the differences. Do not rely on `openshell doctor check`; it is not in the docs.
- **Existing record.** Look for `docs/trials/openshell-<os>.md` in the repo that holds this skill. It is appended to, never overwritten ([RECORD.md](RECORD.md)).
- **Approval.** Ask once for approval to run `openshell` and `docker` with the agent's bash sandbox bypassed, and record the answer.
- **Non-interactive verbs.** Before telling the user to run something, check `openshell <verb> --help` for a form that works without a terminal.

## Right after creating

Scripted: the sandbox reaches `Ready` and survives the create process ending; the base and full effective policy are captured (the full one shows provider-added rules such as `_provider_openrouter`); a guest HTTP client (node, curl or python3) and its real path are found, because a network rule is scoped to a binary path.

## After teardown

Scripted: the sandbox is deleted and gone from `openshell sandbox list` ("cleanup is pending" can take a few seconds); every other sandbox is unchanged; the temp project and download directories are removed. The image is left in place; remove it with `docker rmi trial-claude:local` only if asked, after checking no container uses it.

By hand: confirm the record file exists and `docs/index.md` mentions `trials/`.
