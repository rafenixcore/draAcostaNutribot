from pathlib import Path

import pytest

from orchestrator.discovery import discover

# tests/integration/ -> parents[0]=integration, [1]=tests, [2]=quality-gate
QG_DIR = Path(__file__).resolve().parents[2]
FIXTURES = QG_DIR / "fixtures"


@pytest.mark.integration
def test_discover_fastapi_fixture():
    profile = discover(FIXTURES / "fastapi_sample")
    assert profile.framework == "fastapi"
    assert profile.docker is True


@pytest.mark.integration
def test_discover_django_fixture():
    profile = discover(FIXTURES / "django_sample")
    assert profile.framework == "django"
    assert profile.docker is True
