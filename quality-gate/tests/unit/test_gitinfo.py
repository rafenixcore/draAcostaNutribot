"""tests/unit/test_gitinfo.py"""
import subprocess

from orchestrator.gitinfo import git_fingerprint


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
