from unittest.mock import patch

from orchestrator.toolrunner import container_exec


def test_container_exec_readonly_mount_and_digest(tmp_path):
    calls = {}

    def fake_run(cmd, **kw):
        calls["cmd"] = cmd

        class R:
            returncode = 0
            stdout = ""
            stderr = ""

        return R()

    with patch("subprocess.run", side_effect=fake_run):
        container_exec(
            "trufflesecurity/trufflehog@sha256:abc123",
            ["trufflehog", "filesystem", "."],
            cwd=tmp_path,
            mounts=[f"type=bind,src={tmp_path},dst=/src,readonly"],
        )
    assert calls["cmd"][0] == "docker"
    assert any("sha256:abc123" in c for c in calls["cmd"])
    assert "--network" in calls["cmd"] and "none" in calls["cmd"]
    assert any(
        "readonly" in m for m in calls["cmd"][calls["cmd"].index("--mount") + 1 :]
    )
