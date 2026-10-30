"""The --record output: a Run section appended to docs/trials/openshell-<os>.md."""
import datetime
import platform
import re
from pathlib import Path

from .config import REPO_ROOT
from .helpers import host_label
from .model import Check


def render(name: str, base: dict, checks: list[Check], run_no: int, args) -> str:
    today = datetime.date.today().isoformat()
    lines = [f"## Run {run_no} ({today}, `{base['version']}`, {platform.platform()})", "",
             f"Sandbox `{name}` from image `{args.image}`, created with `openshell sandbox create ... -- sleep infinity`, checked with `openshell sandbox exec` by `smoketest.py`.", "",
             "| Check | Result | Detail |", "|---|---|---|"]
    for c in checks:
        lines.append(f"| {c.name} | {c.status} | {c.detail.replace(chr(10), '<br>').replace('|', chr(92) + '|')[:400]} |")
    lines += ["", "Full text of the policy listings:", ""]
    for c in checks:
        if c.name.startswith("effective network policy"):
            lines += [f"{c.name}:", "```", c.detail, "```"]
    return "\n".join(lines) + "\n"


def append_record(base: dict, checks: list[Check], name: str, args) -> Path:
    path = REPO_ROOT / "docs" / "trials" / f"openshell-{host_label()}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    # An existing file without "## Run" headings is itself run 1.
    numbers = [int(n) for n in re.findall(r"^#{2,3} Run (\d+)", existing, re.M)]
    run_no = (max(numbers) if numbers else (1 if existing else 0)) + 1
    header = "" if existing else f"# OpenShell trial: {host_label()}\n\nRecords appended by `smoketest.py`; add findings by hand under each run.\n\n"
    path.write_text(existing + ("\n" if existing else "") + header + render(name, base, checks, run_no, args), encoding="utf-8")
    return path
