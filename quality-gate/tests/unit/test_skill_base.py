from orchestrator.core import RunContext, Status
from skills.base import Skill
from skills.project_discovery import DiscoverySkill


def test_discovery_skill_writes_profile(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\ndependencies = ["fastapi"]\n')
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("x = 1\n")
    qg = tmp_path / "qg"
    (qg / "config").mkdir(parents=True)
    (qg / "config" / "rules.yml").write_text("rules: []\nskills: {}\n")
    (qg / "artifacts").mkdir(parents=True)
    ctx = RunContext(
        project_root=tmp_path,
        qg_root=qg,
        artifacts_dir=qg / "artifacts",
        reports_dir=qg / "reports",
    )
    skill = DiscoverySkill()
    result = skill.run(ctx)
    assert result.status == Status.PASS
    assert (qg / "artifacts" / "project-profile.json").exists()


def test_skill_error_in_raw_maps_to_policy_not_pass(tmp_path):
    """A tool that reports _error must never yield PASS (silent green)."""

    class BoomSkill(Skill):
        name = "boom"

        def _execute(self, ctx):
            return {"_error": "tool died"}

    qg = tmp_path / "qg"
    (qg / "config").mkdir(parents=True)
    (qg / "config" / "rules.yml").write_text("rules: []\nskills: {}\n")
    ctx = RunContext(
        project_root=tmp_path,
        qg_root=qg,
        artifacts_dir=qg / "artifacts",
        reports_dir=qg / "reports",
    )
    res = BoomSkill().run(ctx)
    assert res.status is Status.FAIL  # default on_error policy, NOT PASS
    assert res.metrics == {}
