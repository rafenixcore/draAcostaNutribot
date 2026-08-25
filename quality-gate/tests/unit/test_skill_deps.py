import json
from unittest.mock import patch

from orchestrator.core import RunContext
from orchestrator.toolrunner import ExecResult
from skills.security_testing import DepsSkill


def test_deps_counts_critical(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\ndependencies = ["fastapi", "requests"]\n'
    )
    qg = tmp_path / "qg"
    (qg / "config").mkdir(parents=True)
    (qg / "config" / "rules.yml").write_text("rules: []\nskills: {}\n")
    ctx = RunContext(
        project_root=tmp_path,
        qg_root=qg,
        artifacts_dir=qg / "artifacts",
        reports_dir=qg / "reports",
        profile={"framework": "fastapi"},
    )
    payload = {
        "vulnerabilities": [
            {"id": "VULN-1", "severity": "critical"},
            {"id": "VULN-2", "severity": "high"},
        ]
    }
    calls = {}

    def fake(cmd, cwd, extra_env=None):
        calls["cmd"] = cmd
        return ExecResult(0, json.dumps(payload), "")

    with patch("skills.security_testing.venv_exec", side_effect=fake):
        res = DepsSkill().run(ctx)
    assert res.metrics["pip_audit.critical_count"] == 1.0
    assert calls["cmd"][0].endswith("pip-audit")
    assert calls["cmd"][-1].endswith("requirements.txt")
