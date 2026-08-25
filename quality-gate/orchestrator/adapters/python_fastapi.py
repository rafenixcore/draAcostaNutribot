"""FastAPI adapter: detect via pyproject dependencies / fastapi import."""

from __future__ import annotations

import tomllib
from pathlib import Path

from orchestrator.adapters.base import StackAdapter


class PythonFastAPIAdapter(StackAdapter):
    framework = "fastapi"

    def detect(self, project_root: Path) -> bool:
        deps = self.get_dependencies(project_root)
        return (
            "fastapi" in deps
            or (project_root / "app").exists()
            and any((project_root / "app").glob("main.py"))
        )

    def get_dependencies(self, project_root: Path) -> list[str]:
        pyproject = project_root / "pyproject.toml"
        if pyproject.exists():
            data = tomllib.loads(pyproject.read_text())
            deps = data.get("project", {}).get("dependencies")
            if deps:
                return deps
            # pyproject exists but declares no [project].dependencies (e.g.
            # tool-only config) — fall through to requirements.txt below.
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
        return ["pytest", "-q", "--tb=short"]

    def run_security_scan(self, project_root: Path) -> list[str]:
        return ["semgrep", "scan", "--json", "--quiet", "."]
