#!/usr/bin/env python3
"""Docker Sandboxes smoke test: create a clone-mode sandbox, run the checks, tear down.

Run:   python -I smoketest.py [--record] [--keep] [--no-inference]
Exit:  0 = no FAIL, 1 = at least one FAIL, 2 = could not start (sbx unusable or name taken).

Failure policy: a check that fails or cannot run is recorded (FAIL or SKIP with the reason)
and the remaining checks still run. Only a missing/unusable sbx or a failed `sbx create`
stops the tests, because nothing exists to test. The run ends with a list to report to
the user. Checks and pass criteria: SMOKETEST.md; preflight and teardown: CHECKS.md.
Only the sandbox this script creates is ever stopped or removed. No installs, no login,
no credential handling; credential values are never printed (names, lengths, hashes only).

Thin entry point; the code lives in the sibling package sbx_smoketest/ (see its modules).
"""
import sys
from pathlib import Path

# `python -I` does not put the script directory on sys.path, so add it explicitly.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sbx_smoketest.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(__doc__.splitlines()[0]))
