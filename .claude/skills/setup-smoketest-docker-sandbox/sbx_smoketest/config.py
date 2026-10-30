"""Paths and constants. REPO_ROOT is computed from this file: <repo>/.claude/skills/<skill>/sbx_smoketest/config.py."""
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = SKILL_DIR.parents[2]  # <repo>/.claude/skills/<skill>
PULL_SCRIPT = REPO_ROOT / "scripts" / "pull_docker_commits.py"
DEFAULT_MODEL = "claude-haiku-5-5"  # small and cheap; used by the raw API probe in check 8c-diag
GIT_ID = ["-c", "user.name=trial", "-c", "user.email=trial@example.invalid"]
AGENT_CLI = {  # agent -> (version command, one-shot prompt command)
    "claude": (["claude", "--version"], ["claude", "-p", "Reply with the single word OK"]),
    "codex": (["codex", "--version"], ["codex", "exec", "Reply with the single word OK"]),
    "pi": (["pi", "--version"], ["pi", "--provider", "anthropic", "-p", "Reply with the single word OK"]),  # not an sbx built-in: needs --kit
}
# Extra `sbx exec` flags per agent (e.g. ["-e", "VAR=placeholder"]); none needed so far (pi gets its sentinel auth file from the kit).
AGENT_EXEC_ENV: dict[str, list[str]] = {}
