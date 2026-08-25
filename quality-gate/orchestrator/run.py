"""Run pipeline: select skills (trigger ∩ profile), execute, consolidate (spec §5)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import yaml

from orchestrator.audit import append_audit
from orchestrator.core import RunContext, SkillResult, Status
from orchestrator.profile import ProjectProfile
from skills import get_skills

GATED_BY_DOCKER = ("trivy", "performance")


def select_skills(
    trigger: str, profile: ProjectProfile, triggers_path: Path
) -> list[str]:
    triggers = yaml.safe_load(triggers_path.read_text())
    return list(triggers.get(trigger, []))


def new_run_id() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")


def global_status(results: list[SkillResult]) -> str:
    if any(r.status is Status.FAIL for r in results):
        return "FAIL"
    if any(r.status is Status.ERROR for r in results):
        return "ERROR"
    if any(r.status is Status.WARN for r in results):
        return "WARN"
    return "PASS"


def run_gate(
    ctx: RunContext, trigger: str = "pre_production"
) -> tuple[list[SkillResult], str]:
    if ctx.profile is None:
        from orchestrator.discovery import discover

        profile = discover(ctx.project_root)
        ctx.profile = profile.to_dict()
        profile.save(ctx.artifacts_dir / "project-profile.json")
    profile = ProjectProfile(**ctx.profile)
    if profile.framework == "unsupported":
        return [], "ERROR"
    names = select_skills(trigger, profile, ctx.qg_root / "config" / "triggers.yml")
    results: list[SkillResult] = []
    for name in names:
        if not profile.docker and name in GATED_BY_DOCKER:
            results.append(
                SkillResult(
                    skill=name,
                    tool="",
                    tool_layer="",
                    status=Status.SKIPPED,
                    metrics={},
                    duration_ms=0,
                    message="no Dockerfile present",
                )
            )
            continue
        skill = get_skills().get(name)
        if skill is None:
            results.append(
                SkillResult(
                    skill=name,
                    tool="",
                    tool_layer="",
                    status=Status.ERROR,
                    metrics={},
                    duration_ms=0,
                    message=f"unknown skill: {name}",
                )
            )
            continue
        result = skill().run(ctx)
        results.append(result)
        append_audit(ctx, result)
    path = ctx.artifacts_dir / "results.json"
    path.write_text(json.dumps([r.to_dict() for r in results], indent=2))
    (ctx.artifacts_dir.parent / "last_run.txt").write_text(ctx.artifacts_dir.name)
    return results, global_status(results)
