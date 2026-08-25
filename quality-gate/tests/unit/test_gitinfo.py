"""tests/unit/test_gitinfo.py"""
import subprocess

from orchestrator.gitinfo import check_run_guards, git_fingerprint


def _git_repo(tmp_path):
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True
    )
    subprocess.run(
        ["git", "config", "user.name", "t"], cwd=tmp_path, check=True
    )
    (tmp_path / "f.txt").write_text("x\n")
    subprocess.run(["git", "add", "f.txt"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True
    )


def test_fingerprint_clean_branch(tmp_path):
    _git_repo(tmp_path)
    fp = git_fingerprint(tmp_path)
    assert fp["in_git"] is True
    assert fp["branch"] == "main"
    assert fp["commit"]
    assert fp["dirty"] is False


def test_fingerprint_dirty_tree(tmp_path):
    _git_repo(tmp_path)
    (tmp_path / "f.txt").write_text("changed\n")
    fp = git_fingerprint(tmp_path)
    assert fp["dirty"] is True


def test_fingerprint_non_git(tmp_path):
    fp = git_fingerprint(tmp_path)
    assert fp == {"in_git": False, "branch": None, "commit": None, "dirty": None}


def test_fingerprint_detached_head(tmp_path):
    _git_repo(tmp_path)
    subprocess.run(["git", "checkout", "-q", "--detach"], cwd=tmp_path, check=True)
    fp = git_fingerprint(tmp_path)
    assert fp["branch"] == "(detached)"
    assert fp["commit"]


def _settings(**project):
    return {"project": project}


def test_guard_no_settings_passes():
    assert check_run_guards({"in_git": True, "branch": "dev", "dirty": True}, {}) is None


def test_guard_branch_mismatch():
    fp = {"in_git": True, "branch": "feature/x", "dirty": False}
    err = check_run_guards(fp, _settings(require_branch=["main", "dev"]))
    assert err and "feature/x" in err and "main" in err


def test_guard_branch_match_passes():
    fp = {"in_git": True, "branch": "dev", "dirty": False}
    assert check_run_guards(fp, _settings(require_branch=["main", "dev"])) is None


def test_guard_branch_requires_git():
    fp = {"in_git": False, "branch": None, "dirty": None}
    err = check_run_guards(fp, _settings(require_branch=["main"]))
    assert err and "not a git repository" in err


def test_guard_clean_dirty_fails():
    fp = {"in_git": True, "branch": "main", "dirty": True}
    err = check_run_guards(fp, _settings(require_clean=True))
    assert err and "uncommitted" in err


def test_guard_clean_clean_passes():
    fp = {"in_git": True, "branch": "main", "dirty": False}
    assert check_run_guards(fp, _settings(require_clean=True)) is None
