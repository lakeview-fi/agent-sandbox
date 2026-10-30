"""Console output: the check table and the final report to the user."""
from .model import FAIL, INFO, PASS, SKIP, Check


def print_table(checks: list[Check]) -> None:
    for c in checks:
        rows = c.detail.splitlines()
        print(f"[{c.status:4}] {c.name}: {(rows[0] if rows else '')[:160]}")
        if c.status == INFO:  # observations: show the whole text, the agent must read it
            for row in rows[1:60]:
                print(f"         {row[:200]}")


def agent_verified(checks: list[Check]) -> bool:
    """Hard requirement: the agent itself must have completed a task in the sandbox (check 8e PASS)."""
    agent = [c for c in checks if c.name.startswith("8e")]
    return bool(agent) and all(c.status == PASS for c in agent)


def print_report(checks: list[Check]) -> None:
    bad = [c for c in checks if c.status in (FAIL, SKIP)]
    if agent_verified(checks):
        print("\n=== SETUP VERIFIED: the coding agent completed a task inside the sandbox with credentials the guest does not hold ===")
    else:
        print("\n=== SETUP NOT VERIFIED: the coding agent did NOT complete a task inside the sandbox (check 8e). "
              "Do not call this setup working; tell the user ===")
    print(f"\n=== REPORT TO THE USER: {sum(c.status == FAIL for c in checks)} FAIL, "
          f"{sum(c.status == SKIP for c in checks)} SKIP, plus INFO lines that need a decision ===")
    for c in bad:
        print(f"- {c.status} {c.name}: {c.detail.splitlines()[0][:200] if c.detail else ''}")
    if not bad:
        print("- no FAIL or SKIP; still read the INFO items above and the open items in SMOKETEST.md")
