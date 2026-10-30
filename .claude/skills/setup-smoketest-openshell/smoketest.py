#!/usr/bin/env python3
"""NVIDIA OpenShell smoke test: create a kept-alive sandbox, run the checks, tear down.

Run (in the shell where `openshell` works: Linux, macOS or WSL2):
       python3 -I smoketest.py [--record] [--keep] [--provider NAME] [--no-inference]
Exit:  0 = no FAIL, 1 = at least one FAIL, 2 = could not start (nothing to test against).

Failure policy: a check that fails or cannot run is recorded (FAIL, or SKIP with the reason)
and the remaining checks still run. Only a missing/unreachable openshell, a missing image or
a failed sandbox create stops the tests, because nothing exists to test. The run ends with a
list to report to the user. Checks and pass criteria: SMOKETEST.md; preflight and teardown:
CHECKS.md. Structure mirrors the Docker Sandboxes skill's smoketest.py on purpose; the two
scripts are self-contained so each skill can be copied alone.
Only the sandbox this script creates is ever deleted. No installs, no credentials handled;
credential values are never printed (names, lengths, hashes only).

Thin entry point; the code lives in the sibling package openshell_smoketest/ (see its modules).
"""
import sys
from pathlib import Path

# `python -I` does not put the script directory on sys.path, so add it explicitly.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from openshell_smoketest.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(__doc__.splitlines()[0]))
