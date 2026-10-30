"""Check result types shared by every module: status names, command output, check, run context."""
import argparse
from dataclasses import dataclass, field
from pathlib import Path


PASS, FAIL, INFO, SKIP = "PASS", "FAIL", "INFO", "SKIP"


@dataclass
class Out:
    code: int
    stdout: str
    stderr: str

    @property
    def text(self) -> str:
        return (self.stdout + self.stderr).strip()


@dataclass
class Check:
    name: str
    status: str
    detail: str = ""


@dataclass
class Ctx:
    name: str
    repo: Path
    base: dict
    args: argparse.Namespace
    created: bool = False
    gws: str = ""
    head_before: str = ""
    remotes_before: set = field(default_factory=set)
    approvals_before: set = field(default_factory=set)
