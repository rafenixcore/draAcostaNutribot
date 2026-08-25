import json
from unittest.mock import patch

from orchestrator.toolrunner import venv_exec


def test_venv_exec_success(tmp_path, monkeypatch):
    monkeypatch.setenv("QG_VENV", str(tmp_path / ".venv"))
    calls = {}

    def fake_run(cmd, **kw):
        calls["cmd"] = cmd

        class R:
            returncode = 0
            stdout = '{"ok": 1}'
            stderr = ""

        return R()

    with patch("subprocess.run", side_effect=fake_run):
        out = venv_exec(["ruff", "check", "."], cwd=tmp_path)
    assert calls["cmd"][0].endswith("bin/ruff")
    assert out.returncode == 0 and json.loads(out.stdout)["ok"] == 1
