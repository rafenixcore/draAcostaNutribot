"""Deterministic rules engine. No AI in the verdict (spec §6)."""

from __future__ import annotations

from dataclasses import dataclass

import yaml


@dataclass
class Rule:
    id: str
    metric: str
    operator: str  # gte | lte | eq
    threshold: float
    severity: str  # FAIL | WARN

    def breached(self, value: float) -> bool:
        """True when `value` violates the allowed range for this rule.

        "gte" means the metric must be >= threshold (breach when below);
        "lte" means the metric must be <= threshold (breach when above).
        """
        if self.operator == "gte":
            return value < self.threshold
        if self.operator == "lte":
            return value > self.threshold
        if self.operator == "eq":
            return value != self.threshold
        raise ValueError(f"unknown operator: {self.operator}")


@dataclass
class SkillPolicy:
    on_skip: str = "WARN"  # default when a skill has no rule verdict
    on_error: str = "FAIL"


def load_rules(path: str) -> list[Rule]:
    with open(path) as fh:
        data = yaml.safe_load(fh)
    return [Rule(**r) for r in data["rules"]]


def load_policies(path: str) -> dict[str, SkillPolicy]:
    with open(path) as fh:
        data = yaml.safe_load(fh)
    return {name: SkillPolicy(**p) for name, p in data.get("skills", {}).items()}


def verdict_for(
    rules: list[Rule], metrics: dict[str, float], policy: SkillPolicy
) -> str:
    """Worst rule breach wins. Empty verdicts fall back to PASS."""
    worst: str | None = None
    for rule in rules:
        value = metrics.get(rule.metric)
        if value is None:
            continue
        if rule.breached(value):
            if rule.severity == "FAIL":
                return "FAIL"
            worst = "WARN"
    if worst:
        return worst
    return "PASS"
