"""K6Skill contract: config-driven health path + SKIPPED when sandbox down."""

import json
from unittest.mock import patch

from orchestrator.core import RunContext
from orchestrator.toolrunner import ExecResult


def _ctx(tmp_path, profile=None):
    qg = tmp_path / "qg"
    (qg / "config").mkdir(parents=True)
    (qg / "config" / "rules.yml").write_text(
        "rules: []\nskills:\n  performance:\n    on_skip: WARN\n"
    )
    return RunContext(
        project_root=tmp_path / "backend",
        qg_root=qg,
        artifacts_dir=tmp_path / "artifacts",
        reports_dir=tmp_path / "reports",
        profile=profile or {"docker": True},
    )


def test_k6_passes_health_path_env(tmp_path):
    from skills.performance_testing import K6Skill

    ctx = _ctx(tmp_path)
    (ctx.qg_root / "settings.json").write_text(
        json.dumps({"project": {"sandbox": {"health_path": "/api/health"}}})
    )
    out = tmp_path / "artifacts" / "performance"
    out.mkdir(parents=True)
    captured = {}

    def fake_exec(image, cmd, cwd, mounts=None, env=None, network="none"):
        captured["cmd"] = cmd
        (out / "smoke.json").write_text(json.dumps({"p95_ms": 12}))
        (out / "load.json").write_text(json.dumps({"p95_ms": 30}))
        return ExecResult(0, "", "")

    with patch("orchestrator.toolrunner.container_exec", side_effect=fake_exec):
        with patch("skills.performance_testing._sandbox_network_up", return_value=True):
            result = K6Skill().run(ctx)

    assert "-e" in captured["cmd"]
    assert "HEALTH_PATH=/api/health" in captured["cmd"]


def test_k6_skips_when_sandbox_down(tmp_path):
    from skills.performance_testing import K6Skill

    with patch("skills.performance_testing._sandbox_network_up", return_value=False):
        result = K6Skill().run(_ctx(tmp_path))
    assert result.status.value == "SKIPPED"


def test_k6_health_path_defaults_to_slash_health(tmp_path):
    from skills.performance_testing import K6Skill

    ctx = _ctx(tmp_path)  # no settings.json → sandbox config absent
    out = tmp_path / "artifacts" / "performance"
    out.mkdir(parents=True)
    captured = {}

    def fake_exec(image, cmd, cwd, mounts=None, env=None, network="none"):
        captured["cmd"] = cmd
        (out / "smoke.json").write_text(json.dumps({"p95_ms": 12}))
        (out / "load.json").write_text(json.dumps({"p95_ms": 30}))
        return ExecResult(0, "", "")

    with patch("orchestrator.toolrunner.container_exec", side_effect=fake_exec):
        with patch("skills.performance_testing._sandbox_network_up", return_value=True):
            K6Skill().run(ctx)

    assert "HEALTH_PATH=/health" in captured["cmd"]


def test_sandbox_network_check_does_not_hang(tmp_path):
    from skills.performance_testing import _sandbox_network_up

    import subprocess

    def slow(*args, **kwargs):
        assert kwargs.get("timeout") is not None, "no timeout on docker network inspect"
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs["timeout"])

    with patch("subprocess.run", side_effect=slow):
        assert _sandbox_network_up() is False
