"""tests/unit/test_secrets.py"""
import json
from pathlib import Path
from unittest.mock import patch

from orchestrator.core import RunContext
from skills.security_testing import SecretsSkill, _parse_trufflehog_lines


def _line(**data):
    return json.dumps(data)


def test_filesystem_shape_extracts_file():
    lines = [
        _line(
            SourceMetadata={"Data": {"Filesystem": {"file": "app/.env"}}},
            DetectorName="TelegramBotToken",
            Verified=False,
        )
    ]
    findings = _parse_trufflehog_lines(lines)
    assert findings == [
        {"detector": "TelegramBotToken", "file": "app/.env", "verified": False}
    ]


def test_legacy_shape_falls_back_to_data_file():
    lines = [
        _line(
            SourceMetadata={"Data": {"file": "config/secret.txt"}},
            DetectorName="OpenAIApiKey",
            Verified=True,
        )
    ]
    findings = _parse_trufflehog_lines(lines)
    assert findings == [
        {"detector": "OpenAIApiKey", "file": "config/secret.txt", "verified": True}
    ]


def test_non_json_lines_are_skipped():
    lines = ["not json", _line(DetectorName="X", Verified=False)]
    assert len(_parse_trufflehog_lines(lines)) == 1


def test_detector_falls_back_to_secret_type():
    lines = [_line(SecretType="PostgresCredentials", Verified=False)]
    findings = _parse_trufflehog_lines(lines)
    assert findings[0]["detector"] == "PostgresCredentials"


def test_malformed_json_line_is_skipped_not_crashing():
    lines = ["{broken json", _line(DetectorName="X", Verified=False)]
    assert len(_parse_trufflehog_lines(lines)) == 1


def test_non_dict_shapes_are_skipped_not_crashing():
    lines = [
        '{"SourceMetadata": {"Data": "oops"}}',
        '{"SourceMetadata": {"Data": {"Filesystem": "oops"}}}',
        _line(
            SourceMetadata={"Data": {"Filesystem": {"file": "app/.env"}}},
            DetectorName="TelegramBotToken",
            Verified=False,
        ),
    ]
    findings = _parse_trufflehog_lines(lines)
    assert findings == [
        {"detector": "TelegramBotToken", "file": "app/.env", "verified": False}
    ]


def test_empty_filesystem_file_falls_back_to_data_file():
    lines = [
        _line(
            SourceMetadata={
                "Data": {"Filesystem": {"file": ""}, "file": "config/secret.txt"}
            },
            DetectorName="OpenAIApiKey",
            Verified=True,
        )
    ]
    findings = _parse_trufflehog_lines(lines)
    assert findings[0]["file"] == "config/secret.txt"


def _skill_ctx(tmp_path: Path) -> RunContext:
    qg = tmp_path / "qg"
    (qg / "config").mkdir(parents=True)
    (qg / "config" / "rules.yml").write_text("rules: []\nskills: {}\n")
    return RunContext(
        project_root=tmp_path,
        qg_root=qg,
        artifacts_dir=qg / "artifacts",
        reports_dir=qg / "reports",
    )


def test_log_skips_secrets_without_detector(tmp_path):
    (tmp_path / "app.py").write_text("x = 1\n")
    out = (
        '{"SourceMetadata": {"Data": {"Filesystem": {"file": "app/.env"}}}}\n'
    )

    def fake(image_ref, cmd, cwd, mounts=None, env=None, network="none"):
        class R:
            returncode = 0
            stdout = out
            stderr = ""

        return R()

    with patch("orchestrator.toolrunner.container_exec", side_effect=fake):
        res = SecretsSkill().run(_skill_ctx(tmp_path))
    assert res.audit["secrets_accessed"] == []
