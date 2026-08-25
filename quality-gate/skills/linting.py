"""Linting skill: ruff check (JSON) + black --check (diff)."""

from __future__ import annotations

import json

from orchestrator.core import RunContext
from orchestrator.toolrunner import venv_exec
from skills.base import Skill


class LintingSkill(Skill):
    name = "linting"
    tool = "ruff + black"
    tool_layer = "venv"

    def _execute(self, ctx: RunContext) -> dict:
        ruff = venv_exec(
            [
                "ruff",
                "check",
                "--exit-zero",
                "--output-format",
                "json",
                "--no-cache",
                ".",
            ],
            cwd=ctx.project_root,
        )
        self._cmd_log.append("ruff check --exit-zero --output-format json --no-cache .")
        self._exit_log.append(ruff.returncode)
        try:
            findings = json.loads(ruff.stdout or "[]")
        except json.JSONDecodeError:
            return {"_error": ruff.stderr or f"ruff exited {ruff.returncode}"}
        black = venv_exec(["black", "--check", "--diff", "."], cwd=ctx.project_root)
        self._cmd_log.append("black --check --diff .")
        self._exit_log.append(black.returncode)
        # black exit 1 = "would reformat" (a lint finding); anything else non-zero
        # is a crash (e.g. 123 internal error) and must not yield a metrics verdict.
        if black.returncode not in (0, 1):
            return {"_error": black.stderr or f"black exited {black.returncode}"}
        reformat = [
            l for l in black.stdout.splitlines() if l.startswith("would reformat")
        ]
        return {"ruff": findings, "black_would_reformat": reformat}

    def _extract_metrics(self, raw: dict) -> dict[str, float]:
        return {
            "lint.error_count": float(
                len(raw["ruff"]) + len(raw["black_would_reformat"])
            )
        }
