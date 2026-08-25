import json
from pathlib import Path
from unittest.mock import patch

from orchestrator.core import RunContext
from orchestrator.toolrunner import ExecResult
from skills.functional_testing import FunctionalTestingSkill


def _fake_run(cmd, cwd, extra_env=None):
    if cmd[0].endswith("coverage") and "json" in cmd:
        out = Path(extra_env["COVERAGE_FILE"]).with_name("coverage.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"totals": {"percent_covered": 92.5}}))
    return ExecResult(0, "", "")


def test_functional_metrics_and_redirection(tmp_path):
    qg = tmp_path / "qg"
    (qg / "config").mkdir(parents=True)
    (qg / "config" / "rules.yml").write_text("rules: []\nskills: {}\n")
    ctx = RunContext(
        project_root=tmp_path,
        qg_root=qg,
        artifacts_dir=qg / "artifacts",
        reports_dir=qg / "reports",
    )
    captured = {}

    def spy(cmd, cwd, extra_env=None):
        if "cmd" not in captured:
            captured["cmd"] = cmd
            captured["env"] = extra_env
        return _fake_run(cmd, cwd, extra_env)

    with patch("skills.functional_testing.venv_exec", side_effect=spy):
        res = FunctionalTestingSkill().run(ctx)
    assert res.metrics["coverage.line_percent"] == 92.5
    assert captured["cmd"] == [
        "coverage",
        "run",
        "-m",
        "pytest",
        "-q",
        "--tb=short",
        ".",
    ]
    assert ".coverage" in captured["env"]["COVERAGE_FILE"]
    assert "-p no:cacheprovider" in captured["env"]["PYTEST_ADDOPTS"]


def _deps_bin(qg):
    deps_bin = qg / "artifacts" / "deps-venv" / "bin"
    deps_bin.mkdir(parents=True)
    (deps_bin / "python").write_text("")
    return deps_bin


def test_functional_prefers_deps_venv_coverage_when_installed(tmp_path):
    qg = tmp_path / "qg"
    (qg / "config").mkdir(parents=True)
    (qg / "config" / "rules.yml").write_text("rules: []\nskills: {}\n")
    deps_bin = _deps_bin(qg)
    (deps_bin / "coverage").write_text("")
    ctx = RunContext(
        project_root=tmp_path,
        qg_root=qg,
        artifacts_dir=qg / "artifacts",
        reports_dir=qg / "reports",
    )
    cmds = []

    def spy(cmd, cwd, extra_env=None):
        cmds.append(cmd)
        return _fake_run(cmd, cwd, extra_env)

    with patch("skills.functional_testing.venv_exec", side_effect=spy):
        res = FunctionalTestingSkill().run(ctx)
    # Both the run and the json-report calls go through the deps venv's
    # coverage binary (its interpreter runs the project's own pinned deps).
    assert res.metrics["coverage.line_percent"] == 92.5
    assert len(cmds) == 2
    assert cmds[0][0] == str(deps_bin / "coverage")
    assert cmds[0][1] == "run"
    assert cmds[1][0] == str(deps_bin / "coverage")
    assert cmds[1][1] == "json"


def test_functional_falls_back_to_gate_venv_when_deps_venv_missing_coverage(
    tmp_path,
):
    # `qg setup` provisions the deps venv best-effort: python may exist
    # while the coverage install failed. The skill must fall back to the
    # gate venv's coverage instead of crashing on a missing binary.
    qg = tmp_path / "qg"
    (qg / "config").mkdir(parents=True)
    (qg / "config" / "rules.yml").write_text("rules: []\nskills: {}\n")
    _deps_bin(qg)  # python only — no coverage binary
    ctx = RunContext(
        project_root=tmp_path,
        qg_root=qg,
        artifacts_dir=qg / "artifacts",
        reports_dir=qg / "reports",
    )
    cmds = []

    def spy(cmd, cwd, extra_env=None):
        cmds.append(cmd)
        return _fake_run(cmd, cwd, extra_env)

    with patch("skills.functional_testing.venv_exec", side_effect=spy):
        res = FunctionalTestingSkill().run(ctx)
    assert res.metrics["coverage.line_percent"] == 92.5
    assert len(cmds) == 2
    assert cmds[0][0] == "coverage"
    assert cmds[0][1] == "run"
    assert cmds[1][0] == "coverage"
    assert cmds[1][1] == "json"
