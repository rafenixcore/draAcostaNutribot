import json
from pathlib import Path
from unittest.mock import patch

from orchestrator.core import RunContext, Status
from orchestrator.toolrunner import ExecResult
from skills.performance_testing import TrivySkill


def _ctx(tmp_path: Path, docker: bool, rules: str) -> RunContext:
    qg = tmp_path / "qg"
    (qg / "config").mkdir(parents=True)
    (qg / "config" / "rules.yml").write_text(rules)
    return RunContext(
        project_root=tmp_path,
        qg_root=qg,
        artifacts_dir=qg / "artifacts",
        reports_dir=qg / "reports",
        profile={"framework": "fastapi", "docker": docker},
    )


def test_trivy_skipped_without_dockerfile(tmp_path):
    rules = "rules: []\nskills:\n  trivy:\n    on_skip: WARN\n"
    res = TrivySkill().run(_ctx(tmp_path, docker=False, rules=rules))
    assert res.status is Status.SKIPPED
    assert res.evidence_path is None


def test_trivy_counts_critical(tmp_path):
    rules = "rules: []\nskills:\n  trivy:\n    on_skip: WARN\n"
    payload = {
        "Results": [
            {
                "Vulnerabilities": [
                    {"Severity": "CRITICAL"},
                    {"Severity": "HIGH"},
                    {"Severity": "CRITICAL"},
                ]
            },
        ]
    }
    calls = {}

    def fake(image_ref, cmd, cwd, mounts=None, env=None, network="none"):
        calls["mounts"] = mounts
        return ExecResult(0, json.dumps(payload), "")

    with patch("skills.performance_testing.container_exec", side_effect=fake):
        res = TrivySkill().run(_ctx(tmp_path, docker=True, rules=rules))
    assert res.metrics["trivy.critical_count"] == 2.0
    assert "readonly" in calls["mounts"][0]


def test_trivy_failed_scan_is_error_not_pass(tmp_path):
    """DB download failure (no JSON output) must FAIL the gate, not PASS it."""
    rules = "rules: []\nskills:\n  trivy:\n    on_skip: WARN\n"

    def fake(image_ref, cmd, cwd, mounts=None, env=None, network="none"):
        return ExecResult(1, "", "FATAL failed to download vulnerability DB")

    with patch("skills.performance_testing.container_exec", side_effect=fake):
        res = TrivySkill().run(_ctx(tmp_path, docker=True, rules=rules))
    assert res.status is Status.FAIL
    assert res.metrics == {}
