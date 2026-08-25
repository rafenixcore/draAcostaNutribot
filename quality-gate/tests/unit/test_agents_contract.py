from pathlib import Path


def test_agents_contract_mentions_whitelist():
    text = Path("AGENTS.md").read_text()
    assert "qg <subcommand>" in text or "qg " in text
    assert "never" in text.lower() and "pass" in text.lower() and "fail" in text.lower()


def test_settings_example_whitelists_qg():
    text = Path("settings.json.example").read_text()
    assert "Bash(qg run:*)" in text
    assert "Bash(qg discover:*)" in text
