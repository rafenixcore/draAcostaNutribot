"""Discovery skill: writes artifacts/project-profile.json."""

from __future__ import annotations

from orchestrator.core import RunContext
from orchestrator.discovery import discover
from skills.base import Skill


class DiscoverySkill(Skill):
    name = "discovery"
    tool = "builtin"
    tool_layer = "venv"
    evidence_filename = "project-profile.json"

    def _execute(self, ctx: RunContext) -> dict:
        profile = discover(
            ctx.project_root, out_path=ctx.artifacts_dir / "project-profile.json"
        )
        return profile.to_dict()
