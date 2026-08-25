"""Reports: summary.md + summary.json with published limitations (spec §15)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from orchestrator.core import RunContext, SkillResult

LIMITATIONS = [
    "secrets scan: working tree only, git history not scanned (v0.1)",
    "performance: k6 smoke + load only (no stress/spike/soak)",
    "supported stacks: python + fastapi, python + django only",
    "scheduled_nightly trigger: designed, not implemented (v0.1)",
]


def write_summary(
    ctx: RunContext, results: list[SkillResult], global_status_: str, trigger: str
) -> tuple[Path, Path]:
    """Write summary.json (full payload) + summary.md; returns (md, json) paths."""
    ctx.reports_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_id": ctx.artifacts_dir.name,
        "timestamp": datetime.now(UTC).isoformat(timespec="seconds"),
        "trigger": trigger,
        "status": global_status_,
        "results": [r.to_dict() for r in results],
        "limitations": list(LIMITATIONS),
        "analyzed_state": ctx.analyzed,
    }
    jpath = ctx.reports_dir / "summary.json"
    jpath.write_text(json.dumps(payload, indent=2))
    lines = [
        f"# Quality Gate — {payload['run_id']}",
        f"\n**Status:** {global_status_}  **Trigger:** {trigger}",
    ]
    if ctx.analyzed:
        a = ctx.analyzed
        if a.get("in_git"):
            analyzed_line = (
                f"**Analyzed:** {a.get('branch')} @ {a.get('commit')}"
                + (" (dirty)" if a.get("dirty") else "")
            )
        else:
            analyzed_line = "**Analyzed:** not a git repository"
        lines.append(analyzed_line)
    lines.append("\n## Skills")
    for r in results:
        lines.append(
            f"- **{r.skill}** [{r.status.value}] {r.tool} ({r.duration_ms} ms)"
            + (f" — {r.message}" if r.message else "")
        )
    lines.append("\n## Limitations")
    lines += [f"- {l}" for l in LIMITATIONS]
    mpath = ctx.reports_dir / "summary.md"
    mpath.write_text("\n".join(lines) + "\n")
    return mpath, jpath
