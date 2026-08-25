"""Django adapter: detect via manage.py; tests via pytest-django or manage.py test."""

from __future__ import annotations

import tomllib
from pathlib import Path

from orchestrator.adapters.base import StackAdapter


class PythonDjangoAdapter(StackAdapter):
    framework = "django"

    def detect(self, project_root: Path) -> bool:
        return (
            project_root / "manage.py"
        ).exists() and "django" in self.get_dependencies(project_root)

    def get_dependencies(self, project_root: Path) -> list[str]:
        pyproject = project_root / "pyproject.toml"
        if pyproject.exists():
            data = tomllib.loads(pyproject.read_text())
            return data.get("project", {}).get("dependencies", [])
        reqs = project_root / "requirements.txt"
        if reqs.exists():
            return [
                l.strip()
                for l in reqs.read_text().splitlines()
                if l.strip() and not l.startswith("#")
            ]
        return []

    def run_linter(self, project_root: Path) -> list[str]:
        # --no-cache: ruff must never write .ruff_cache into the analyzed
        # project — the linter layer claims "no escriben nada" on disk.
        return ["ruff", "check", ".", "--output-format", "json", "--no-cache"]

    def run_tests(self, project_root: Path) -> list[str]:
        if "pytest-django" in self.get_dependencies(project_root):
            return ["pytest", "-q", "--tb=short"]
        return ["python", "manage.py", "test", "--noinput"]

    def run_security_scan(self, project_root: Path) -> list[str]:
        return ["semgrep", "scan", "--json", "--quiet", "."]
