"""Stack adapters: per-framework knowledge of how to run things."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class StackAdapter(ABC):
    framework: str = "unsupported"

    @abstractmethod
    def detect(self, project_root: Path) -> bool:
        """True if this adapter's framework is present in project_root."""

    @abstractmethod
    def get_dependencies(self, project_root: Path) -> list[str]:
        """Declared dependencies of the analyzed project."""

    @abstractmethod
    def run_linter(self, project_root: Path) -> list[str]:
        """Command to run the linter (ruff/black) for this stack."""

    @abstractmethod
    def run_tests(self, project_root: Path) -> list[str]:
        """Command to run the test suite (pytest or manage.py)."""

    @abstractmethod
    def run_security_scan(self, project_root: Path) -> list[str]:
        """Command for the stack's security scan (semgrep)."""


def get_adapter(framework: str) -> type[StackAdapter]:
    from orchestrator.adapters.python_django import PythonDjangoAdapter
    from orchestrator.adapters.python_fastapi import PythonFastAPIAdapter

    table = {"fastapi": PythonFastAPIAdapter, "django": PythonDjangoAdapter}
    if framework not in table:
        raise ValueError(f"unsupported framework: {framework}")
    return table[framework]
