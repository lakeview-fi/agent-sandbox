"""Argument parsing and the top-level flow: preflight, create repo, run checks, teardown, report, record."""
import argparse
import datetime
import sys

from .config import DEFAULT_MODEL
from .model import FAIL, Ctx
from .preflight import preflight
from .record import append_record
from .repo import make_repo
from .report import agent_verified, print_report, print_table
from .runner import run_checks
from .teardown import teardown


def main(description: str) -> int:
    ap = argparse.ArgumentParser(description=description)
    ap.add_argument("--name", default=f"trial-{datetime.datetime.now():%H%M%S}")
    ap.add_argument("--agent", default="claude", help="claude, codex or pi (names the CLI the checks run)")
    ap.add_argument("--kit", default="", help="sandbox kit reference (e.g. ./kit) passed to sbx create instead of the agent name; required for pi")
    ap.add_argument("--allow-host", default="example.com")
    ap.add_argument("--other-host", default="example.org")
    ap.add_argument("--model", default=DEFAULT_MODEL, help="model for the raw API probe in check 8c-diag (default: %(default)s)")
    ap.add_argument("--no-inference",action="store_true", help="skip the LLM inference check (reported as SKIP)")
    ap.add_argument("--record", action="store_true", help="append a Run section to docs/trials/docker-sandboxes-<os>.md")
    ap.add_argument("--keep", action="store_true", help="skip teardown (you must run sbx rm --force yourself)")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    checks, base, can_continue = preflight(args.name)
    if not can_continue:
        print_table(checks)
        print_report(checks)
        return 2
    repo = make_repo()
    ctx = Ctx(args.name, repo, base, args)
    try:
        checks += run_checks(ctx)
    finally:
        if not args.keep:
            checks += teardown(args.name, repo, base)
    print_table(checks)
    print_report(checks)
    if args.record:
        print(f"\nRecord appended to {append_record(base, checks, args.name)}")
    return 1 if any(c.status == FAIL for c in checks) or not agent_verified(checks) else 0
