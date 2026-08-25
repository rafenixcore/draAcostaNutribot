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
            errors="replace",
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def git_fingerprint(project_root: Path) -> dict:
    """Branch / commit / dirtiness of the working tree under analysis.

    A failed git command and empty output are conflated: both fall back to
    "(detached)", "(unknown)", and dirty=False.
    """
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


def check_run_guards(analyzed: dict, settings: dict) -> str | None:
    """Return an error message when a run guard blocks, else None.

    Guards are execution preconditions (config-driven), never quality
    metrics — they cannot influence the PASS/FAIL verdict.

    Expected settings shape: ``{"project": {"require_branch": [...],
    "require_clean": bool}}``. Hand-edit mistakes are normalized so a
    guard never fails open: a bare string ``require_branch`` is treated
    as a one-element list, and only the boolean ``True`` enables
    ``require_clean`` (string ``"false"`` does not). A ``require_branch``
    that is neither a string nor a list of strings is a misconfiguration
    and blocks the run with a clean error instead of raising.
    """
    project = settings.get("project", {}) or {}
    require_branch = project.get("require_branch") or []
    if isinstance(require_branch, str):
        require_branch = [require_branch]
    elif not isinstance(require_branch, list) or not all(
        isinstance(b, str) for b in require_branch
    ):
        return (
            "misconfigured require_branch in settings.json: expected "
            "string or list"
        )
    require_clean = project.get("require_clean") is True
    if require_branch and not analyzed["in_git"]:
        return "require_branch is set but this is not a git repository"
    if require_branch and analyzed["branch"] not in require_branch:
        return (
            f"require_branch {require_branch} — current branch is "
            f"{analyzed['branch']}; refusing to run"
        )
    if require_clean and not analyzed["in_git"]:
        return "require_clean is set but this is not a git repository"
    if require_clean and analyzed["dirty"]:
        return "require_clean — working tree has uncommitted changes; refusing to run"
    return None


def state_banner(analyzed: dict) -> str:
    """One-line WARNING identifying the analyzed branch/commit state."""
    if not analyzed["in_git"]:
        return (
            "WARNING: not a git repository — the analyzed state cannot be "
            "attributed to a branch/commit. Verify the working tree by hand."
        )
    dirty = " (dirty: uncommitted changes present)" if analyzed["dirty"] else ""
    return (
        f"WARNING: analyzing branch '{analyzed['branch']}' @ "
        f"{analyzed['commit']}{dirty}. If this is not the state you intend "
        "to validate, cancel now."
    )
