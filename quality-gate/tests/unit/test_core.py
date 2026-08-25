from pathlib import Path

from orchestrator.core import ExitCodes, RunContext, SkillResult, Status


def test_status_members():
    assert [s.value for s in Status] == ["PASS", "WARN", "FAIL", "SKIPPED", "ERROR"]


def test_exit_codes():
    assert ExitCodes.PASS == 0 and ExitCodes.WARN == 0
    assert ExitCodes.FAIL == 1 and ExitCodes.INFRA == 2


def test_skill_result_fields():
    r = SkillResult(
        skill="sast",
        tool="semgrep==1.0",
        tool_layer="venv",
        status=Status.FAIL,
        metrics={"semgrep.high_count": 2},
        evidence_path=Path("x.json"),
        duration_ms=12,
        audit={"commands": [], "exit_codes": [], "secrets_accessed": []},
    )
    assert r.status == Status.FAIL and r.metrics["semgrep.high_count"] == 2


def test_run_context_defaults(tmp_path):
    ctx = RunContext(
        project_root=tmp_path,
        qg_root=tmp_path / "qg",
        artifacts_dir=tmp_path / "a",
        reports_dir=tmp_path / "r",
    )
    assert isinstance(ctx.env, dict)
    assert "PATH" in ctx.env  # inherits process environment
