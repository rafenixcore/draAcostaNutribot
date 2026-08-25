import shutil
from pathlib import Path

import pytest

from orchestrator.core import RunContext
from orchestrator.run import run_gate

# tests/integration/ -> parents[0]=integration, [1]=tests, [2]=quality-gate
QG_DIR = Path(__file__).resolve().parents[2]
FIXTURES = QG_DIR / "fixtures"


@pytest.mark.integration
@pytest.mark.skipif(shutil.which("docker") is None, reason="docker required")
def test_gate_pre_production_fastapi(tmp_path):
    project = FIXTURES / "fastapi_sample"
    qg = tmp_path / "qg"
    for rel in ("config/rules.yml", "config/triggers.yml"):
        (qg / rel).parent.mkdir(parents=True, exist_ok=True)
        (qg / rel).write_text((QG_DIR / rel).read_text())
    ctx = RunContext(
        project_root=project,
        qg_root=qg,
        artifacts_dir=qg / "artifacts" / "it1",
        reports_dir=qg / "reports",
    )
    results, status = run_gate(ctx, trigger="pre_production")
    names = {r.skill: r.status.value for r in results}
    assert status == "FAIL"  # planted vuln + secret
    assert names["sast"] == "FAIL"  # semgrep flags shell=True
    assert names["secrets"] == "FAIL"  # truffleHog finds planted key
    assert "trivy" in names and "performance" in names
