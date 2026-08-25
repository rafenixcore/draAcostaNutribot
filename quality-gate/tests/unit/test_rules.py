from orchestrator.rules import Rule, load_rules


def test_load_rules_from_config(tmp_path):
    rules = load_rules("config/rules.yml")
    ids = [r.id for r in rules]
    assert "coverage-minimum" in ids and "sast-high" in ids


def test_rule_defaults():
    r = Rule(id="x", metric="m", operator="lte", threshold=1, severity="WARN")
    assert r.severity == "WARN"


def test_rule_parse(tmp_path):
    y = tmp_path / "r.yml"
    y.write_text(
        "rules:\n  - id: a\n    metric: m\n    operator: gte\n    threshold: 3\n    severity: FAIL\n"
    )
    rules = load_rules(str(y))
    assert rules[0].threshold == 3 and rules[0].operator == "gte"
