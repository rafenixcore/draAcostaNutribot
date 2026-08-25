import json
from unittest.mock import patch

from orchestrator.core import RunContext, Status
from orchestrator.toolrunner import ExecResult
from skills.performance_testing import K6Skill


def _k6_ctx(tmp_path):
    qg = tmp_path / "qg"
    (qg / "config").mkdir(parents=True)
    (qg / "config" / "rules.yml").write_text(
        "rules: []\nskills:\n  performance:\n    on_skip: WARN\n"
    )
    (qg / "sandbox" / "k6").mkdir(parents=True)
    return RunContext(
        project_root=tmp_path,
        qg_root=qg,
        artifacts_dir=qg / "artifacts",
        reports_dir=qg / "reports",
        profile={"framework": "fastapi", "docker": True},
    )


def test_k6_smoke_and_load(tmp_path):
    qg = tmp_path / "qg"
    ctx = _k6_ctx(tmp_path)

    def fake(image_ref, cmd, cwd, mounts=None, env=None, network="none"):
        # find which profile via the script path in cmd (substring: cmd holds
        # "/scripts/smoke.js", not the bare filename)
        profile_name = "smoke" if any("smoke.js" in c for c in cmd) else "load"
        out_dir = qg / "artifacts" / "performance"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"{profile_name}.json").write_text(json.dumps({"p95_ms": 42.5}))
        return ExecResult(0, "", "")

    with patch("orchestrator.toolrunner.container_exec", side_effect=fake) as m:
        with patch("skills.performance_testing._sandbox_network_up", return_value=True):
            res = K6Skill().run(ctx)
    assert res.metrics["k6.smoke_p95_ms"] == 42.5
    assert res.metrics["k6.load_p95_ms"] == 42.5
    assert "qg_sandbox" in m.call_args.kwargs["network"]


def test_k6_failure_is_error_not_pass(tmp_path):
    ctx = _k6_ctx(tmp_path)

    def fake(image_ref, cmd, cwd, mounts=None, env=None, network="none"):
        return ExecResult(125, "", "docker: network not found")

    # Sandbox network is up (missing network now pre-empts with SKIPPED);
    # this exercises the k6-run-failure path → on_error policy.
    with patch("orchestrator.toolrunner.container_exec", side_effect=fake):
        with patch("skills.performance_testing._sandbox_network_up", return_value=True):
            res = K6Skill().run(ctx)
    assert res.status is Status.FAIL  # on_error policy, not a silent PASS
    assert res.metrics == {}


def test_k6_stale_summary_does_not_contaminate_load(tmp_path):
    qg = tmp_path / "qg"
    ctx = _k6_ctx(tmp_path)
    out_dir = qg / "artifacts" / "performance"
    out_dir.mkdir(parents=True, exist_ok=True)
    # stale summary from a previous smoke run, before this run starts
    (out_dir / "summary.json").write_text(json.dumps({"p95_ms": 42.5}))

    def fake(image_ref, cmd, cwd, mounts=None, env=None, network="none"):
        if any("smoke.js" in c for c in cmd):
            (out_dir / "smoke.json").write_text(json.dumps({"p95_ms": 42.5}))
        return ExecResult(0, "", "")  # load run writes nothing

    with patch("orchestrator.toolrunner.container_exec", side_effect=fake):
        with patch("skills.performance_testing._sandbox_network_up", return_value=True):
            res = K6Skill().run(ctx)
    assert "k6.smoke_p95_ms" in res.metrics
    assert "k6.load_p95_ms" not in res.metrics  # no stale data leak
