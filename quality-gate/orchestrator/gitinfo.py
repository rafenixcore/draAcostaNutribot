"""orchestrator/gitinfo.py — what exactly was analyzed (spec §10.2)."""

from __future__ import annotations

import subprocess
from pathlib import Path


def _git(cwd: Path, args: list[str]) -> str | None:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def git_fingerprint(project_root: Path) -> dict:
    """Branch / commit / dirtiness of the working tree under analysis."""
    if _git(project_root, ["rev-parse", "--is-inside-work-tree"]) != "true":
        return {"in_git": False, "branch": None, "commit": None, "dirty": None}
    branch = _git(project_root, ["branch", "--show-current"]) or "(detached)"
    commit = _git(project_root, ["rev-parse", "--short", "HEAD"]) or "(unknown)"
    status = _git(project_root, ["status", "--porcelain"])
    return {
        "in_git": True,
        "branch": branch,
        "commit": commit,
        "dirty": bool(status),
    }
