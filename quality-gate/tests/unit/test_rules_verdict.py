from orchestrator.rules import Rule, SkillPolicy, verdict_for


def test_breached_fail():
    rules = [Rule("r", "m", "lte", 0, "FAIL")]
    assert verdict_for(rules, {"m": 2}, SkillPolicy()) == "FAIL"


def test_breached_warn_when_severity_warn():
    rules = [Rule("r", "m", "lte", 0, "WARN")]
    assert verdict_for(rules, {"m": 2}, SkillPolicy()) == "WARN"


def test_no_rule_met_pass():
    rules = [Rule("r", "m", "lte", 5, "FAIL")]
    assert verdict_for(rules, {"m": 1}, SkillPolicy()) == "PASS"


def test_fail_wins_over_warn():
    rules = [Rule("a", "m1", "lte", 0, "WARN"), Rule("b", "m2", "lte", 0, "FAIL")]
    assert verdict_for(rules, {"m1": 3, "m2": 3}, SkillPolicy()) == "FAIL"


def test_missing_metric_ignored():
    rules = [Rule("r", "m", "lte", 0, "FAIL")]
    assert verdict_for(rules, {}, SkillPolicy()) == "PASS"


def test_no_metrics_pass_default():
    assert verdict_for([], {}, SkillPolicy()) == "PASS"
