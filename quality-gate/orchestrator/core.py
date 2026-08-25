"""Core types shared by orchestrator and skills."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class Status(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    SKIPPED = "SKIPPED"
    ERROR = "ERROR"


class ExitCodes:
    PASS = 0
    WARN = 0
    FAIL = 1
    INFRA = 2


@dataclass
class SkillResult:
    skill: str
    tool: str
    tool_layer: str
    status: Status
    metrics: dict[str, float]
    duration_ms: int
    audit: dict[str, list] = field(
        default_factory=lambda: {
            "commands": [],
            "exit_codes": [],
            "secrets_accessed": [],
        }
    )
    evidence_path: Path | None = None
    message: str = ""

    def to_dict(self) -> dict:
        return {
            "skill": self.skill,
            "tool": self.tool,
            "tool_layer": self.tool_layer,
            "status": self.status.value,
            "metrics": self.metrics,
            "duration_ms": self.duration_ms,
            "audit": self.audit,
            "evidence_path": str(self.evidence_path) if self.evidence_path else None,
            "message": self.message,
        }


@dataclass
class RunContext:
    project_root: Path
    qg_root: Path
    artifacts_dir: Path
    reports_dir: Path
    profile: dict | None = None
    analyzed: dict | None = None  # git state fingerprint (spec §10.2)
    env: dict[str, str] = field(default_factory=lambda: dict(os.environ))
