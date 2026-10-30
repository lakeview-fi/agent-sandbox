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
    base: dict
    args: argparse.Namespace
    proj: Path
    created: bool = False
    client: str = ""
    client_path: str = ""
    provider: str = ""
    provider_type: str = ""
    tmp_dirs: list = field(default_factory=list)
