def test_readme_has_quickstart_and_isolation_table():
    with open("README.md") as fh:
        text = fh.read()
    assert "qg init" in text and "qg run" in text
    assert "venv" in text and "container" in text
    assert "read-only" in text or "readonly" in text
