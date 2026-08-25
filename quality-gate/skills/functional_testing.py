"""Functional testing skill: pytest under coverage, redirected to artifacts."""

from __future__ import annotations

import json

from orchestrator.core import RunContext
from orchestrator.toolrunner import venv_exec
from skills.base import Skill


class FunctionalTestingSkill(Skill):
    name = "functional_testing"
    tool = "pytest + coverage"
    tool_layer = "venv"

    def _execute(self, ctx: RunContext) -> dict:
        cov_dir = ctx.artifacts_dir / self.name
        cov_dir.mkdir(parents=True, exist_ok=True)
        env = {
            "COVERAGE_FILE": str(cov_dir / ".coverage"),
            "PYTEST_ADDOPTS": "-p no:cacheprovider",
        }
        # Prefer the project's dedicated deps venv (created by `qg setup`):
        # pytest then runs under the project's own pinned deps instead of the
        # gate venv's, and the gate's pinned tools can never be clobbered by
        # project requirements. Fall back to the gate venv when it wasn't
        # provisioned (no profile yet / no declared deps). venv_exec prepends
        # its venv bin dir to an absolute binary path unchanged, so passing
        # the deps-venv coverage path uses exactly that interpreter.
        deps_python = ctx.qg_root / "artifacts" / "deps-venv" / "bin" / "python"
        # Use the deps-venv coverage only when the binary actually exists:
        # `qg setup` installs it best-effort, and a failed install must fall
        # back to the gate venv's coverage rather than crash with ENOENT.
        coverage_bin = (
            str(deps_python.parent / "coverage")
            if (deps_python.parent / "coverage").exists()
            else "coverage"
        )
        run = venv_exec(
            [coverage_bin, "run", "-m", "pytest", "-q", "--tb=short", "."],
            cwd=ctx.project_root,
            extra_env=env,
        )
        self._cmd_log.append("coverage run -m pytest -q --tb=short .")
        self._exit_log.append(run.returncode)
        report = venv_exec(
            [coverage_bin, "json", "--quiet", "-o", str(cov_dir / "coverage.json")],
            cwd=ctx.project_root,
            extra_env=env,
        )
        self._cmd_log.append("coverage json --quiet")
        self._exit_log.append(report.returncode)
        data = json.loads((cov_dir / "coverage.json").read_text())
        return {"coverage": data.get("totals", {})}

    def _extract_metrics(self, raw: dict) -> dict[str, float]:
        return {
            "coverage.line_percent": float(raw["coverage"].get("percent_covered", 0.0))
        }
