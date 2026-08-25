import json

from orchestrator.discovery import discover


def _write(tmp_path, name, content=None):
    if content is None:
        path, content = tmp_path, name
    else:
        path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def test_detect_fastapi(tmp_path):
    _write(
        tmp_path, "pyproject.toml", '[project]\ndependencies = ["fastapi", "uvicorn"]\n'
    )
    (tmp_path / "app").mkdir()
    _write(tmp_path / "app" / "main.py", "from fastapi import FastAPI\n")
    _write(tmp_path, "Dockerfile", "FROM python:3.12-slim\n")
    (tmp_path / "openapi.json").write_text('{"paths": {"/health": {"get": {}}}}')
    profile = discover(tmp_path)
    assert profile.framework == "fastapi"
    assert profile.docker is True
    assert profile.test_system == "pytest"
    assert profile.endpoints == [{"method": "GET", "path": "/health"}]


def test_detect_django_uses_manage(tmp_path):
    _write(tmp_path, "pyproject.toml", '[project]\ndependencies = ["django"]\n')
    _write(tmp_path, "manage.py", "#!/usr/bin/env python\n")
    (tmp_path / "core").mkdir()
    profile = discover(tmp_path)
    assert profile.framework == "django"


def test_unsupported(tmp_path):
    _write(tmp_path, "pyproject.toml", "[project]\ndependencies = []\n")
    profile = discover(tmp_path)
    assert profile.framework == "unsupported"


def test_deps_fallback_to_requirements_when_pyproject_has_no_project(
    tmp_path,
):
    _write(tmp_path, "pyproject.toml", "[tool.ruff]\nline-length = 100\n")
    _write(tmp_path, "requirements.txt", "fastapi>=0.110\npsycopg2-binary>=2.9\n")
    (tmp_path / "app").mkdir()
    _write(tmp_path / "app" / "main.py", "x = 1\n")
    profile = discover(tmp_path)
    assert profile.framework == "fastapi"
    assert profile.db == "postgres"


def test_discover_writes_profile_json(tmp_path):
    _write(tmp_path, "pyproject.toml", '[project]\ndependencies = ["fastapi"]\n')
    (tmp_path / "app").mkdir()
    _write(tmp_path / "app" / "main.py", "x = 1\n")
    out = tmp_path / "artifacts" / "project-profile.json"
    discover(tmp_path, out_path=out)
    assert json.loads(out.read_text())["framework"] == "fastapi"


def test_profile_defaults_to_root_app(tmp_path):
    _write(tmp_path, "pyproject.toml", '[project]\ndependencies = ["fastapi"]\n')
    (tmp_path / "app").mkdir()
    _write(tmp_path / "app" / "main.py", "x = 1\n")
    profile = discover(tmp_path)
    assert profile.app_root == "."


def test_profile_writes_app_root(tmp_path):
    _write(tmp_path, "pyproject.toml", '[project]\ndependencies = ["fastapi"]\n')
    (tmp_path / "app").mkdir()
    _write(tmp_path / "app" / "main.py", "x = 1\n")
    out = tmp_path / "artifacts" / "project-profile.json"
    profile = discover(tmp_path, out_path=out)
    profile.app_root = "backend"
    profile.save(out)
    assert json.loads(out.read_text())["app_root"] == "backend"
