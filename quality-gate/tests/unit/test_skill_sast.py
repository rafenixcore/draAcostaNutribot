import json
from pathlib import Path
from unittest.mock import patch

from orchestrator.core import RunContext, Status
from orchestrator.toolrunner import ExecResult
from skills.security_testing import SastSkill


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


def test_sast_counts_only_high_severity(tmp_path):
    payload = {
        "results": [
            {"extra": {"severity": "ERROR"}},
            {"extra": {"severity": "ERROR"}},
            {"extra": {"severity": "WARNING"}},
        ]
    }
    with patch(
        "skills.security_testing.venv_exec",
        return_value=ExecResult(0, json.dumps(payload), ""),
    ):
        res = SastSkill().run(_ctx(tmp_path))
    assert res.metrics["semgrep.high_count"] == 2.0
    assert res.evidence_path is not None and res.evidence_path.exists()


def test_sast_unparseable_output_is_error_not_pass(tmp_path):
    with patch(
        "skills.security_testing.venv_exec",
        return_value=ExecResult(2, "", "semgrep fatal: no valid config"),
    ):
        res = SastSkill().run(_ctx(tmp_path))
    assert res.status is Status.FAIL  # on_error policy, not a silent PASS
    assert res.metrics == {}
