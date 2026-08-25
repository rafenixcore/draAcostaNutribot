import json

from orchestrator.core import RunContext, SkillResult, Status
from orchestrator.reporting import LIMITATIONS, write_summary


def _result() -> SkillResult:
    return SkillResult(
        skill="sast",
        tool="semgrep",
        tool_layer="venv",
        status=Status.FAIL,
        metrics={"semgrep.high_count": 2.0},
        duration_ms=10,
        message="2 high findings",
    )


def test_summary_contains_status_and_limitations(tmp_path):
    qg = tmp_path / "qg"
    ctx = RunContext(
        project_root=tmp_path,
        qg_root=qg,
        artifacts_dir=qg / "artifacts" / "20260825T120000",
        reports_dir=qg / "reports" / "20260825T120000",
    )
    md, js = write_summary(ctx, [_result()], "FAIL", "pre_production")
    assert md.exists() and js.exists()
    data = json.loads(js.read_text())
    assert data["status"] == "FAIL"
    assert data["results"][0]["metrics"]["semgrep.high_count"] == 2.0
    assert data["limitations"] == LIMITATIONS
    assert "working tree only" in md.read_text()
    assert "**Status:** FAIL" in md.read_text()


def test_summary_includes_analyzed_state(tmp_path):
    ctx = RunContext(
        project_root=tmp_path,
        qg_root=tmp_path / "qg",
        artifacts_dir=tmp_path / "artifacts",
        reports_dir=tmp_path / "reports",
        analyzed={"in_git": True, "branch": "main", "commit": "abc1234", "dirty": False},
    )
    mpath, jpath = write_summary(ctx, [], "PASS", "pre_production")
    payload = json.loads(jpath.read_text())
    assert payload["analyzed_state"] == ctx.analyzed
    assert "main" in mpath.read_text() and "abc1234" in mpath.read_text()
