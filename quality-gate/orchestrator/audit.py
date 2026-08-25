"""Audit log: one JSON line per skill run (spec §8.4)."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from orchestrator.core import RunContext, SkillResult


def append_audit(ctx: RunContext, result: SkillResult, event: str = "run") -> None:
    path = ctx.artifacts_dir / "audit.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now(UTC).isoformat(timespec="seconds"),
        "event": event,
        "skill": result.skill,
        "commands": result.audit.get("commands", []),
        "exit_codes": result.audit.get("exit_codes", []),
        "secrets_accessed": result.audit.get("secrets_accessed", []),
        "duration_ms": result.duration_ms,
    }
    with path.open("a") as fh:
        fh.write(json.dumps(entry) + "\n")
