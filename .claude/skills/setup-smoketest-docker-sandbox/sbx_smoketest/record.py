"""The --record output: a Run section appended to docs/trials/docker-sandboxes-<os>.md."""
import datetime
import platform
import re
from pathlib import Path

from .config import REPO_ROOT
from .helpers import host_label
from .model import Check


def render(name: str, base: dict, checks: list[Check], run_no: int) -> str:
    today = datetime.date.today().isoformat()
    lines = [f"## Run {run_no} ({today}, `{base['version']}`, {platform.platform()})", "",
             f"Sandbox `{name}` created with `sbx create --clone`, checked with `sbx exec` by `smoketest.py`.", "",
             "| Check | Result | Detail |", "|---|---|---|"]
    for c in checks:
        detail = c.detail.replace("\n", "<br>").replace("|", "\\|")[:400]
        lines.append(f"| {c.name} | {c.status} | {detail} |")
    lines += ["", "Full text of the multi-line items (kit hosts):", ""]
    for c in checks:
        if c.name.startswith("kit policy hosts"):
            lines += ["```", c.detail, "```"]
    return "\n".join(lines) + "\n"


def append_record(base: dict, checks: list[Check], name: str) -> Path:
    path = REPO_ROOT / "docs" / "trials" / f"docker-sandboxes-{host_label()}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    # An existing file without "## Run" headings is itself run 1.
    numbers = [int(n) for n in re.findall(r"^#{2,3} Run (\d+)", existing, re.M)]
    run_no = (max(numbers) if numbers else (1 if existing else 0)) + 1
    section = render(name, base, checks, run_no)
    header = "" if existing else f"# Docker Sandboxes trial: {host_label().title()}\n\nRecords appended by `smoketest.py`; add findings by hand under each run.\n\n"
    path.write_text(existing + ("\n" if existing else "") + header + section, encoding="utf-8")
    index = REPO_ROOT / "docs" / "index.md"
    if index.exists() and "trials" not in index.read_text(encoding="utf-8"):
        print("NOTE: docs/index.md does not mention trials/; add it.")
    return path
