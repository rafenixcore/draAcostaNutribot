import json
from pathlib import Path

import yaml

from orchestrator.core import RunContext
from orchestrator.sandbox import compose_cmd, generate_app_override, write_override


def _ctx(tmp_path: Path) -> RunContext:
    qg = tmp_path / "qg"
    (qg / "sandbox").mkdir(parents=True)
    (qg / "sandbox" / "docker-compose.yml").write_text("name: qg_sandbox\n")
    return RunContext(
        project_root=tmp_path / "proj",
        qg_root=qg,
        artifacts_dir=qg / "artifacts",
        reports_dir=qg / "reports",
    )


def test_generate_app_override(tmp_path):
    (tmp_path / "proj").mkdir()
    override = generate_app_override(tmp_path / "proj")
    app = override["services"]["app"]
    assert "build" in app and "depends_on" in app
    assert app["depends_on"]["postgres"]["condition"] == "service_healthy"


def test_write_override_and_compose_cmd(tmp_path):
    ctx = _ctx(tmp_path)
    path = write_override(ctx)
    assert path.exists() and "app" in path.read_text()
    cmd = compose_cmd(ctx, ["up", "-d"])
    assert cmd[:2] == ["docker", "compose"]
    assert cmd[cmd.index("-f") + 1].endswith("docker-compose.yml")
    assert "up" in cmd and "-d" in cmd
    assert "--env-file" in cmd
    assert cmd[cmd.index("--env-file") + 1].endswith(".env.qg")


def test_override_without_env_has_no_environment_key(tmp_path):
    for sandbox_env in (None, {}):
        override = generate_app_override(tmp_path / "proj", sandbox_env=sandbox_env)
        assert "environment" not in override["services"]["app"]


def test_override_injects_sandbox_env(tmp_path):
    override = generate_app_override(
        tmp_path / "backend",
        port=8000,
        sandbox_env={"DATABASE_URL": "postgres://x"},
    )
    app = override["services"]["app"]
    assert app["environment"] == {"DATABASE_URL": "postgres://x"}


def test_write_override_injects_env_from_settings(tmp_path):
    ctx = _ctx(tmp_path)
    (ctx.qg_root / "settings.json").write_text(
        json.dumps(
            {"project": {"sandbox": {"env": {"DATABASE_URL": "postgres://x"}}}}
        )
    )
    data = yaml.safe_load(write_override(ctx).read_text())
    assert data["services"]["app"]["environment"] == {"DATABASE_URL": "postgres://x"}
