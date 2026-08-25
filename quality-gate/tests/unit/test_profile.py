import json

from orchestrator.profile import ProjectProfile


def test_profile_fields():
    p = ProjectProfile(language="python", framework="fastapi")
    assert p.docker is False and p.endpoints == []


def test_save_load_roundtrip(tmp_path):
    p = ProjectProfile(
        language="python",
        framework="django",
        docker=True,
        db="postgres",
        cache="redis",
        test_system="pytest",
        endpoints=[{"method": "GET", "path": "/health"}],
    )
    path = tmp_path / "project-profile.json"
    p.save(path)
    loaded = ProjectProfile.load(path)
    assert loaded == p


def test_unsupported():
    p = ProjectProfile(language="python", framework="unsupported")
    assert json.loads(p.to_json())["framework"] == "unsupported"
