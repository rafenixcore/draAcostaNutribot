"""tests/unit/test_secrets.py"""
import json

from skills.security_testing import _parse_trufflehog_lines


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
    assert findings[0]["file"] == "config/secret.txt"
    assert findings[0]["verified"] is True


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
