"""App-root resolution: settings override > heuristic > root (spec §10.1)."""

import json

import pytest

from orchestrator.discovery import (
    DiscoveryError,
    find_app_root,
    load_project_settings,
)


def _mkapp(base, rel):
    """Make `rel` look like a Python app: deps file + app/main.py."""
    target = base / rel if rel != "." else base
    (target / "pyproject.toml").parent.mkdir(parents=True, exist_ok=True)
    (target / "pyproject.toml").write_text(
        '[project]\ndependencies = ["fastapi"]\n'
    )
    (target / "app").mkdir(parents=True, exist_ok=True)
    (target / "app" / "main.py").write_text("x = 1\n")
    return target


def _mkqg(base, settings=None):
    qg = base / "qg"
    qg.mkdir(parents=True, exist_ok=True)
    if settings is not None:
        (qg / "settings.json").write_text(json.dumps(settings))
    return qg


def test_root_is_used_when_root_is_the_only_app(tmp_path):
    _mkapp(tmp_path, ".")
    app_root, source = find_app_root(tmp_path)
    assert app_root == tmp_path
    assert source == "root"


def test_backend_is_resolved_in_monorepo(tmp_path):
    _mkapp(tmp_path, "backend")
    app_root, source = find_app_root(tmp_path)
    assert app_root == tmp_path / "backend"
    assert source == "heuristic"


def test_src_layout_is_resolved(tmp_path):
    _mkapp(tmp_path, "src")
    app_root, _ = find_app_root(tmp_path)
    assert app_root == tmp_path / "src"


def test_ambiguous_layout_raises(tmp_path):
    _mkapp(tmp_path, ".")
    _mkapp(tmp_path, "backend")
    with pytest.raises(DiscoveryError):
        find_app_root(tmp_path)


def test_settings_override_wins_over_heuristic(tmp_path):
    _mkapp(tmp_path, ".")
    _mkapp(tmp_path, "backend")
    qg = _mkqg(tmp_path, {"project": {"app_root": "backend"}})
    app_root, source = find_app_root(tmp_path, qg)
    assert app_root == tmp_path / "backend"
    assert source == "settings"


def test_settings_override_missing_dir_raises(tmp_path):
    qg = _mkqg(tmp_path, {"project": {"app_root": "nope"}})
    with pytest.raises(DiscoveryError):
        find_app_root(tmp_path, qg)


def test_load_settings_empty_when_missing(tmp_path):
    assert load_project_settings(tmp_path / "qg") == {}


def test_load_settings_parses_project_app_root(tmp_path, capsys):
    qg = _mkqg(tmp_path, {"project": {"app_root": "backend"}})
    assert load_project_settings(qg) == {"app_root": "backend"}
    # a valid settings.json must not emit the malformed-file warning
    assert "WARNING" not in capsys.readouterr().err


def test_load_settings_tolerates_invalid_json_with_warning(tmp_path, capsys):
    qg = tmp_path / "qg"
    qg.mkdir(parents=True, exist_ok=True)
    (qg / "settings.json").write_text("{not json")
    assert load_project_settings(qg) == {}
    err = capsys.readouterr().err
    assert "WARNING" in err
    assert "invalid JSON" in err


def test_no_candidate_falls_back_to_root(tmp_path):
    (tmp_path / "README.md").write_text("not an app")
    app_root, source = find_app_root(tmp_path)
    assert app_root == tmp_path
    assert source == "root"
