import json

from orchestrator.core import RunContext, SkillResult, Status
from orchestrator.run import global_status, run_gate, select_skills


def _make_result(skill: str, status: Status) -> SkillResult:
    return SkillResult(
        skill=skill,
        tool="t",
        tool_layer="venv",
        status=status,
        metrics={},
        duration_ms=1,
    )


def test_select_skills_from_triggers(tmp_path):
    triggers = tmp_path / "triggers.yml"
    triggers.write_text("pre_merge:\n  - sast\n  - deps\n")
    from orchestrator.profile import ProjectProfile

    assert select_skills("pre_merge", ProjectProfile(), triggers) == ["sast", "deps"]


def test_global_status():
    assert global_status([_make_result("a", Status.PASS)]) == "PASS"
    assert global_status([_make_result("a", Status.WARN)]) == "WARN"
    assert (
        global_status([_make_result("a", Status.FAIL), _make_result("b", Status.WARN)])
        == "FAIL"
    )
    assert global_status([_make_result("a", Status.ERROR)]) == "ERROR"


def test_run_gate_skips_docker_gated_without_docker(tmp_path, monkeypatch):
    qg = tmp_path / "qg"
    (qg / "config").mkdir(parents=True)
    (qg / "config" / "triggers.yml").write_text(
        "pre_production:\n  - linting\n  - trivy\n  - performance\n"
    )
    (qg / "config" / "rules.yml").write_text("rules: []\nskills: {}\n")
    (tmp_path / "pyproject.toml").write_text('[project]\ndependencies = ["fastapi"]\n')
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("x = 1\n")
    ctx = RunContext(
        project_root=tmp_path,
        qg_root=qg,
        artifacts_dir=qg / "artifacts" / "run1",
        reports_dir=qg / "reports",
    )
    monkeypatch.setattr(
        "orchestrator.run.get_skills",
        lambda: {
            "linting": type(
                "Fake",
                (),
                {"run": lambda self, c: _make_result("linting", Status.PASS)},
            ),
        },
    )
    results, status = run_gate(ctx)
    assert status == "PASS"
    names = [r.skill for r in results]
    assert "trivy" in names and "performance" in names
    assert all(
        r.status is Status.SKIPPED
        for r in results
        if r.skill in ("trivy", "performance")
    )
    results_json = json.loads((ctx.artifacts_dir / "results.json").read_text())
    assert results_json[0]["skill"] == "linting"
    assert (qg / "artifacts" / "last_run.txt").read_text() == "run1"
