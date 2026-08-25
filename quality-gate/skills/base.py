"""Skill base: uniform run() → SkillResult pipeline."""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from pathlib import Path

from orchestrator.core import RunContext, SkillResult, Status
from orchestrator.rules import SkillPolicy, load_policies, load_rules, verdict_for


class Skill(ABC):
    name: str = "skill"
    tool: str = "tool"
    tool_layer: str = "venv"  # "venv" | "container"
    rules_file: str = "config/rules.yml"
    evidence_filename: str = "raw.json"

    def run(self, ctx: RunContext) -> SkillResult:
        start = time.monotonic()
        self._cmd_log: list[str] = []
        self._exit_log: list[int] = []
        self._secret_log: list[str] = []
        raw: dict = {}
        status_override: Status | None = None
        try:
            raw = self._execute(ctx)
            if raw.get("_skipped"):
                status_override = Status.SKIPPED
                raw.pop("_skipped")
        except Exception as exc:  # noqa: BLE001 — tool died → policy decides
            raw = {"_error": str(exc)}
            status_override = Status.ERROR
        # A skill that reports _error (tool died / unparseable output) must
        # never fall through to a metrics verdict — that would PASS a scan
        # that never ran. on_error policy decides instead.
        if status_override is None and raw.get("_error"):
            status_override = Status.ERROR
        metrics = self._extract_metrics(raw) if raw and "_error" not in raw else {}
        # Per-skill status keeps the truth (SKIPPED stays SKIPPED, so the
        # report shows what actually happened); on_skip/on_error policies
        # are applied at orchestration/verdict level, not here.
        evidence_path = (
            None
            if status_override is Status.SKIPPED
            else self._write_evidence(ctx, raw)
        )
        rules = load_rules(str(ctx.qg_root / self.rules_file))
        policy = load_policies(str(ctx.qg_root / self.rules_file)).get(
            self.name, SkillPolicy()
        )
        if status_override is Status.SKIPPED:
            status = Status.SKIPPED
        elif status_override is Status.ERROR:
            status = Status(policy.on_error)
        else:
            status = Status(verdict_for(rules, metrics, policy))
        duration_ms = int((time.monotonic() - start) * 1000)
        return SkillResult(
            skill=self.name,
            tool=self.tool,
            tool_layer=self.tool_layer,
            status=status,
            metrics=metrics,
            duration_ms=duration_ms,
            evidence_path=evidence_path,
            audit={
                "commands": self._cmd_log,
                "exit_codes": self._exit_log,
                "secrets_accessed": self._secret_log,
            },
        )

    @abstractmethod
    def _execute(self, ctx: RunContext) -> dict:
        """Run the tool, return raw evidence as a dict."""

    def _extract_metrics(self, raw: dict) -> dict[str, float]:
        return {}

    # Skills record their commands / exit codes / secret names (never values)
    # via self._cmd_log / self._exit_log / self._secret_log inside _execute.

    def _write_evidence(self, ctx: RunContext, raw: dict) -> Path | None:
        if not raw:
            return None
        path = ctx.artifacts_dir / self.name / self.evidence_filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(raw, indent=2, default=str))
        return path
