"""Skill registry. Lazy: only resolves imports when the registry is used."""

_registry: dict[str, type] | None = None


def get_skills() -> dict[str, type]:
    global _registry
    if _registry is None:
        from skills.functional_testing import FunctionalTestingSkill
        from skills.linting import LintingSkill
        from skills.performance_testing import K6Skill, TrivySkill
        from skills.project_discovery import DiscoverySkill
        from skills.security_testing import DepsSkill, SastSkill, SecretsSkill

        _registry = {
            "discovery": DiscoverySkill,
            "linting": LintingSkill,
            "functional_testing": FunctionalTestingSkill,
            "sast": SastSkill,
            "secrets": SecretsSkill,
            "deps": DepsSkill,
            "trivy": TrivySkill,
            "performance": K6Skill,
        }
    return _registry
