#!/usr/bin/env python3
"""Pull the git commits an agent made inside a Docker Sandbox (sbx --clone) into a local branch.

Usage:  python scripts/pull_docker_commits.py SANDBOX [--repo PATH] [--branch NAME]
                                              [--target-branch NAME] [--merge] [--dry-run]

What it does (clone mode only; the sandbox must be running):
  1. git fetch from the host repo's `sandbox-<SANDBOX>` remote into refs/sandboxes/<SANDBOX>/*.
  2. Finds the sandbox branch with commits your current HEAD does not have (or use --branch).
  3. Shows the commits, file stats and the files that need a careful review.
  4. Creates a local branch (default agent/<SANDBOX>/<branch>) at the agent's tip. Your working
     tree and current branch are not touched.
  5. With --merge: fast-forwards your current branch to it (hooks disabled; refuses otherwise).

Exit: 0 ok (or nothing new), 1 error, 2 several candidate branches (pass --branch), 3 not a fast-forward.
The last line is machine-readable: `RESULT: ...`. Docs: docs/guides/how-to/docker-sandbox-how-to.md
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # also works under `python -I`
import sandbox_git_common as sg  # noqa: E402


def fetch_branches(repo: Path, sandbox: str) -> dict[str, str]:
    """Fetch every branch of the sandbox clone; return {branch: sha}."""
    remote = f"sandbox-{sandbox}"
    if remote not in sg.git(repo, "remote").stdout.split():
        raise sg.Fail(f"no git remote {remote!r} in {repo}. Was the sandbox created with --clone from this repo? (sbx ls)")
    dest = f"refs/sandboxes/{sandbox}"
    done = sg.git(repo, "fetch", "--quiet", remote, f"+refs/heads/*:{dest}/*", check=False)
    if done.returncode != 0:
        raise sg.Fail(f"git fetch {remote} failed: {done.stderr.strip()}\nIs the sandbox running? A stopped sandbox serves no commits (sbx run --name {sandbox}).")
    rows = sg.git(repo, "for-each-ref", "--format=%(refname)\t%(objectname)", f"{dest}/").stdout.splitlines()
    return {ref[len(dest) + 1:]: sha for ref, sha in (row.split("\t") for row in rows if row)}


def ahead(repo: Path, sha: str) -> int:
    return int(sg.git(repo, "rev-list", "--count", f"HEAD..{sha}").stdout.strip())


def choose_branch(repo: Path, refs: dict[str, str], wanted: str | None) -> str | None:
    if wanted:
        if wanted not in refs:
            raise sg.Fail(f"the sandbox has no branch {wanted!r}; it has: {', '.join(sorted(refs)) or 'none'}")
        return wanted
    news = {name: ahead(repo, sha) for name, sha in refs.items()}
    news = {name: count for name, count in news.items() if count > 0}
    if not news:
        return None
    if len(news) > 1:
        listing = ", ".join(f"{name} (+{count})" for name, count in sorted(news.items()))
        raise sg.Fail(f"several sandbox branches have new commits: {listing}. Pass --branch NAME.", code=2)
    return next(iter(news))


def pull(args: argparse.Namespace) -> str:
    repo = sg.repo_root(args.repo)
    refs = fetch_branches(repo, args.sandbox)
    branch = choose_branch(repo, refs, args.branch)
    if branch is None:
        return "RESULT: nothing-new"
    tip = refs[branch]
    count = ahead(repo, tip)
    print(f"sandbox branch {branch}: {count} commit(s) not in your HEAD\n")
    sg.show_new_work(repo, "HEAD", tip)
    target = args.target_branch or f"agent/{args.sandbox}/{branch}"
    existing = sg.branch_sha(repo, target)
    if existing not in (None, tip):
        raise sg.Fail(f"local branch {target!r} already exists at a different commit; delete it or pass --target-branch")
    if args.dry_run:
        return f"RESULT: dry-run branch={target} commits={count}"
    if existing is None:
        sg.git(repo, "branch", target, tip)
    merged = False
    if args.merge:
        sg.fast_forward(repo, target)
        merged = True
    print(f"\nbranch {target} is at the agent's tip." + (" Current branch fast-forwarded." if merged else f" Review it, then: git merge --ff-only {target}"))
    return f"RESULT: pulled branch={target} commits={count} merged={str(merged).lower()}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("sandbox", help="sandbox name (as in `sbx ls`)")
    parser.add_argument("--repo", default=".", help="host repository the sandbox was cloned from (default: current directory)")
    parser.add_argument("--branch", help="sandbox branch to pull (default: the only one with new commits)")
    parser.add_argument("--target-branch", help="local branch to create (default: agent/<sandbox>/<branch>)")
    parser.add_argument("--merge", action="store_true", help="fast-forward the current branch to the pulled commits")
    parser.add_argument("--dry-run", action="store_true", help="fetch and show, but create no branch and merge nothing")
    try:
        print(pull(parser.parse_args(argv)))
        return 0
    except sg.Fail as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exc.code


if __name__ == "__main__":
    sys.exit(main())
