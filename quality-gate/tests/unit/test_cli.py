import json
import subprocess

from orchestrator import cli


def test_parser_accepts_all_subcommands():
    for name in (
        "init",
        "discover",
        "setup",
        "run",
        "run-skill",
        "get-profile",
        "get-results",
        "get-report",
        "status",
        "cleanup",
    ):
        assert cli.build_parser().parse_args([name]).command == name


def test_run_trigger_default_and_flag():
    assert cli.build_parser().parse_args(["run"]).trigger == "pre_production"
    assert (
        cli.build_parser().parse_args(["run", "--trigger", "pre_merge"]).trigger
        == "pre_merge"
    )


def test_main_init_creates_env_and_dirs(tmp_path, monkeypatch):
    qg = tmp_path / "qg"
    (qg / "sandbox").mkdir(parents=True)
    (qg / "sandbox" / ".env.qg.template").write_text("POSTGRES_PASSWORD=change-me\n")
    monkeypatch.setattr(cli, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(cli, "QG_ROOT", qg)
    monkeypatch.setattr("shutil.which", lambda t: "/usr/bin/" + t)
    assert cli.main(["init"]) == 0
    assert (qg / ".env.qg").exists()
    assert (qg / "artifacts" / ".gitignore").exists()


def test_main_init_missing_host_tools(tmp_path, monkeypatch):
    qg = tmp_path / "qg"
    (qg / "sandbox").mkdir(parents=True)
    (qg / "sandbox" / ".env.qg.template").write_text("x=1\n")
    monkeypatch.setattr(cli, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(cli, "QG_ROOT", qg)
    monkeypatch.setattr("shutil.which", lambda t: None)
    assert cli.main(["init"]) == 2


def test_main_discover_unsupported_exit_2(tmp_path, monkeypatch):
    qg = tmp_path / "qg"
    (qg / "artifacts").mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text("[project]\ndependencies = []\n")
    monkeypatch.setattr(cli, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(cli, "QG_ROOT", qg)
    assert cli.main(["discover"]) == 2


def test_main_run_fail_exit_1(tmp_path, monkeypatch):
    qg = tmp_path / "qg"
    (qg / "config").mkdir(parents=True)
    (qg / "config" / "triggers.yml").write_text("pre_production: []\n")
    (qg / "config" / "rules.yml").write_text("rules: []\nskills: {}\n")
    (tmp_path / "pyproject.toml").write_text('[project]\ndependencies = ["fastapi"]\n')
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("x = 1\n")
    monkeypatch.setattr(cli, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(cli, "QG_ROOT", qg)
    from orchestrator.core import SkillResult, Status

    fake = lambda ctx, trigger="pre_production": (
        [
            SkillResult(
                skill="sast",
                tool="semgrep",
                tool_layer="venv",
                status=Status.FAIL,
                metrics={},
                duration_ms=1,
            )
        ],
        "FAIL",
    )
    monkeypatch.setattr("orchestrator.run.run_gate", fake)
    assert cli.main(["run"]) == 1


def test_main_run_unknown_trigger_exit_2(tmp_path, monkeypatch):
    qg = tmp_path / "qg"
    (qg / "config").mkdir(parents=True)
    (qg / "config" / "triggers.yml").write_text("pre_production: []\n")
    (qg / "config" / "rules.yml").write_text("rules: []\nskills: {}\n")
    (tmp_path / "pyproject.toml").write_text('[project]\ndependencies = ["fastapi"]\n')
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("x = 1\n")
    monkeypatch.setattr(cli, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(cli, "QG_ROOT", qg)
    assert cli.main(["run", "--trigger", "typo"]) == 2


def test_main_run_skill_no_arg_exit_2(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(cli, "QG_ROOT", tmp_path / "qg")
    assert cli.main(["run-skill"]) == 2


def _mkapp(tmp_path, rel):
    target = tmp_path / rel if rel != "." else tmp_path
    (target / "pyproject.toml").parent.mkdir(parents=True, exist_ok=True)
    (target / "pyproject.toml").write_text(
        '[project]\ndependencies = ["fastapi"]\n'
    )
    (target / "app").mkdir(parents=True, exist_ok=True)
    (target / "app" / "main.py").write_text("x = 1\n")


def test_main_discover_monorepo_exit_0(tmp_path, monkeypatch):
    qg = tmp_path / "qg"
    (qg / "artifacts").mkdir(parents=True)
    _mkapp(tmp_path, "backend")
    monkeypatch.setattr(cli, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(cli, "QG_ROOT", qg)
    assert cli.main(["discover"]) == 0
    profile = json.loads(
        (qg / "artifacts" / "project-profile.json").read_text()
    )
    assert profile["framework"] == "fastapi"
    assert profile["app_root"] == "backend"


def test_main_discover_ambiguous_exit_2(tmp_path, monkeypatch):
    qg = tmp_path / "qg"
    (qg / "artifacts").mkdir(parents=True)
    _mkapp(tmp_path, ".")
    _mkapp(tmp_path, "backend")
    monkeypatch.setattr(cli, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(cli, "QG_ROOT", qg)
    assert cli.main(["discover"]) == 2


def test_main_run_uses_app_root(tmp_path, monkeypatch):
    qg = tmp_path / "qg"
    (qg / "config").mkdir(parents=True)
    (qg / "config" / "triggers.yml").write_text("pre_production: []\n")
    (qg / "config" / "rules.yml").write_text("rules: []\nskills: {}\n")
    (qg / "artifacts").mkdir()
    _mkapp(tmp_path, "backend")
    monkeypatch.setattr(cli, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(cli, "QG_ROOT", qg)
    from orchestrator.core import SkillResult, Status

    captured = {}

    def fake(ctx, trigger="pre_production"):
        captured["root"] = ctx.project_root
        return (
            [
                SkillResult(
                    skill="sast",
                    tool="semgrep",
                    tool_layer="venv",
                    status=Status.PASS,
                    metrics={},
                    duration_ms=1,
                )
            ],
            "PASS",
        )

    monkeypatch.setattr("orchestrator.run.run_gate", fake)
    assert cli.main(["run"]) == 0
    assert captured["root"] == tmp_path / "backend"


def _git_repo(tmp_path):
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    (tmp_path / "f.txt").write_text("x\n")
    # -A: the app scaffold (_mkapp) already created backend/ in this tree;
    # stage everything so the tree is clean after the commit.
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)


def test_main_run_prints_banner_and_sets_analyzed(tmp_path, monkeypatch, capsys):
    qg = tmp_path / "qg"
    (qg / "config").mkdir(parents=True)
    (qg / "config" / "triggers.yml").write_text("pre_production: []\n")
    (qg / "config" / "rules.yml").write_text("rules: []\nskills: {}\n")
    (qg / "artifacts").mkdir()
    _mkapp(tmp_path, "backend")
    _git_repo(tmp_path)
    monkeypatch.setattr(cli, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(cli, "QG_ROOT", qg)
    captured = {}

    def fake(ctx, trigger="pre_production"):
        captured["analyzed"] = ctx.analyzed
        return [], "PASS"

    monkeypatch.setattr("orchestrator.run.run_gate", fake)
    assert cli.main(["run"]) == 0
    out = capsys.readouterr().out
    assert "WARNING: analyzing branch 'main'" in out
    assert captured["analyzed"]["branch"] == "main"
    assert captured["analyzed"]["dirty"] is False


def test_main_run_guard_branch_mismatch_blocks(tmp_path, monkeypatch):
    qg = tmp_path / "qg"
    (qg / "config").mkdir(parents=True)
    (qg / "config" / "triggers.yml").write_text("pre_production: []\n")
    (qg / "config" / "rules.yml").write_text("rules: []\nskills: {}\n")
    (qg / "artifacts").mkdir()
    (qg / "settings.json").write_text(
        '{"project": {"require_branch": ["main"]}}'
    )
    _mkapp(tmp_path, "backend")
    subprocess.run(["git", "init", "-q", "-b", "feature/x"], cwd=tmp_path, check=True)
    monkeypatch.setattr(cli, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(cli, "QG_ROOT", qg)
    called = []

    def fake(ctx, trigger="pre_production"):
        called.append(True)
        return [], "PASS"

    monkeypatch.setattr("orchestrator.run.run_gate", fake)
    assert cli.main(["run"]) == 2
    assert called == []
