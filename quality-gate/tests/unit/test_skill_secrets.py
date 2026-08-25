from pathlib import Path
from unittest.mock import patch

from orchestrator.core import RunContext, Status
from skills.security_testing import SecretsSkill


def _ctx(tmp_path: Path, rules: str = "rules: []\nskills: {}\n") -> RunContext:
    qg = tmp_path / "qg"
    (qg / "config").mkdir(parents=True)
    (qg / "config" / "rules.yml").write_text(rules)
    return RunContext(
        project_root=tmp_path,
        qg_root=qg,
        artifacts_dir=qg / "artifacts",
        reports_dir=qg / "reports",
    )


def test_secrets_scope_working_tree_and_readonly_mount(tmp_path):
    (tmp_path / "app.py").write_text("x = 1\n")
    out = (
        '{"SecretType": "AWS", "Raw": "AKIAIOSFODNN7EXAMPLE", '
        '"DetectorName": "AWS", "SourceMetadata": {"Data": {"file": "app.py"}}}\n'
    )
    calls = {}

    def fake(image_ref, cmd, cwd, mounts=None, env=None, network="none"):
        calls["cmd"] = cmd
        calls["mounts"] = mounts
        calls["image"] = image_ref

        class R:
            returncode = 0
            stdout = out
            stderr = ""

        return R()

    ctx = _ctx(tmp_path)
    with patch("orchestrator.toolrunner.container_exec", side_effect=fake):
        res = SecretsSkill().run(ctx)
    assert res.metrics["secrets.count"] == 1.0
    assert "readonly" in calls["mounts"][0]
    assert "sha256:" in calls["image"]
    assert res.evidence_path is not None
    raw = res.evidence_path.read_text()
    assert '"scope": "working-tree-only"' in raw
    assert "AKIAIOSFODNN7EXAMPLE" not in raw  # values redacted from evidence
    assert res.audit["secrets_accessed"] == ["AWS@app.py"]  # names, never values


def test_secrets_docker_failure_is_error_not_pass(tmp_path):
    (tmp_path / "app.py").write_text("x = 1\n")

    class R:
        returncode = 125
        stdout = ""
        stderr = "docker: network not found"

    def fake(image_ref, cmd, cwd, mounts=None, env=None, network="none"):
        return R()

    with patch("orchestrator.toolrunner.container_exec", side_effect=fake):
        res = SecretsSkill().run(_ctx(tmp_path))
    assert res.status is Status.FAIL  # on_error policy, not a silent PASS
    assert res.metrics == {}
