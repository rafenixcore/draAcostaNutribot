import pytest

from orchestrator.adapters.base import StackAdapter, get_adapter


def test_abc_methods():
    for m in (
        "detect",
        "get_dependencies",
        "run_linter",
        "run_tests",
        "run_security_scan",
    ):
        assert m in StackAdapter.__abstractmethods__


def test_get_adapter_unknown():
    with pytest.raises(ValueError):
        get_adapter("rust")


def test_get_adapter_known():
    from orchestrator.adapters.python_fastapi import PythonFastAPIAdapter

    assert get_adapter("fastapi") is PythonFastAPIAdapter


def test_fastapi_linter_runs_without_cache_writes(tmp_path):
    from orchestrator.adapters.python_fastapi import PythonFastAPIAdapter

    cmd = PythonFastAPIAdapter().run_linter(tmp_path)
    assert "--no-cache" in cmd


def test_django_linter_runs_without_cache_writes(tmp_path):
    from orchestrator.adapters.python_django import PythonDjangoAdapter

    cmd = PythonDjangoAdapter().run_linter(tmp_path)
    assert "--no-cache" in cmd
