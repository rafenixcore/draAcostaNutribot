import json
from pathlib import Path
from unittest.mock import patch

from orchestrator.core import RunContext, Status
from orchestrator.toolrunner import ExecResult
from skills.linting import LintingSkill


def _ctx(tmp_path: Path) -> RunContext:
    qg = tmp_path / "qg"
    (qg / "config").mkdir(parents=True)
    (qg / "config" / "rules.yml").write_text("rules: []\nskills: {}\n")
    return RunContext(
        project_root=tmp_path,
        qg_root=qg,
        artifacts_dir=qg / "artifacts",
        reports_dir=qg / "reports",
    )


def test_linting_metrics_and_audit(tmp_path):
    ruff_out = json.dumps(
        [
            {
                "code": "E501",
                "message": "line too long",
                "location": {"path": "a.py", "line": 1},
            }
        ]
    )
    black_out = "would reformat b.py\nwould reformat c.py\n"
    ctx = _ctx(tmp_path)
    results = [ExecResult(0, ruff_out, ""), ExecResult(1, black_out, "")]
    with patch("skills.linting.venv_exec", side_effect=results):
        res = LintingSkill().run(ctx)
    assert res.metrics["lint.error_count"] == 3.0
    assert len(res.audit["commands"]) == 2
    assert res.audit["exit_codes"] == [0, 1]


def test_ruff_runs_without_cache_writes(tmp_path):
    """ruff must not leave .ruff_cache in the analyzed project (isolation)."""
    ctx = _ctx(tmp_path)
    commands: list[list[str]] = []

    def fake_exec(cmd, **kwargs):
        commands.append(cmd)
        return ExecResult(0, "[]", "")

    with patch("skills.linting.venv_exec", side_effect=fake_exec):
        LintingSkill().run(ctx)
    assert commands[0][0] == "ruff"
    assert "--no-cache" in commands[0]


def test_linting_black_crash_is_error_not_pass(tmp_path):
    ctx = _ctx(tmp_path)
    results = [ExecResult(0, "[]", ""), ExecResult(123, "", "black: internal error")]
    with patch("skills.linting.venv_exec", side_effect=results):
        res = LintingSkill().run(ctx)
    assert res.status is Status.FAIL  # on_error policy, not a silent PASS
    assert res.tool_layer == "venv"
