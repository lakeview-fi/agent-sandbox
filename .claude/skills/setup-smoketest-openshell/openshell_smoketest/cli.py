"""Argument parsing and the top-level flow: preflight, create project, run checks, teardown, report, record."""
import argparse
import datetime
import tempfile
from pathlib import Path

from .model import FAIL, Ctx
from .preflight import preflight
from .record import append_record
from .report import agent_verified, print_report, print_table
from .runner import run_checks
from .teardown import teardown


def main(description: str) -> int:
    ap = argparse.ArgumentParser(description=description)
    ap.add_argument("--name", default=f"trial-{datetime.datetime.now():%H%M%S}")
    ap.add_argument("--agent", default="claude", help="claude or pi (the CLI that checks 8a and 8e run)")
    ap.add_argument("--image", default="", help="local image tag (default trial-<agent>:local), or 'default' for OpenShell's default workload")
    ap.add_argument("--provider", default="", help="gateway provider to attach (default: the first one listed)")
    ap.add_argument("--model", default="", help="model for the openrouter inference check (default: first free model)")
    ap.add_argument("--allow-host", default="example.com")
    ap.add_argument("--other-host", default="example.org")
    ap.add_argument("--create-timeout", type=int, default=240)
    ap.add_argument("--no-inference", action="store_true", help="skip the LLM inference check (reported as SKIP)")
    ap.add_argument("--record", action="store_true", help="append a Run section to docs/trials/openshell-<os>.md")
    ap.add_argument("--keep", action="store_true", help="skip teardown (you must run openshell sandbox delete yourself)")
    args = ap.parse_args()
    args.image = args.image or f"trial-{args.agent}:local"

    checks, base, can_continue = preflight(args.name, args)
    if not can_continue:
        print_table(checks)
        print_report(checks)
        return 2
    proj = Path(tempfile.mkdtemp(prefix="osh-proj-"))
    (proj / "README.md").write_text("# throwaway project for openshell smoke test\n")
    (proj / "hello.py").write_text("print('hello')\n")
    ctx = Ctx(args.name, base, args, proj)
    try:
        checks += run_checks(ctx)
    finally:
        if not args.keep:
            checks += teardown(ctx)
    print_table(checks)
    print_report(checks)
    if args.record:
        print(f"\nRecord appended to {append_record(base, checks, args.name, args)}")
    return 1 if any(c.status == FAIL for c in checks) or not agent_verified(checks) else 0
