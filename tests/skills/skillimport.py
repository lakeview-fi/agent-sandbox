"""Put a skill folder on sys.path so its smoketest package can be imported (the folder names have hyphens)."""
import sys
from pathlib import Path

SKILLS = Path(__file__).resolve().parents[2] / ".claude" / "skills"


def add_skill(folder: str) -> None:
    path = str(SKILLS / folder)
    if path not in sys.path:
        sys.path.insert(0, path)
