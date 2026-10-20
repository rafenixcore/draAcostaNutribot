"""Total plan duration in days (multiples of 7); weekly cycle in content."""

from __future__ import annotations

import re
from typing import Any

DEFAULT_PLAN_DURATION_DAYS = 7
MIN_PLAN_DURATION_DAYS = 7
MAX_PLAN_DURATION_DAYS = 364

# Atajos en Telegram y panel (múltiplos de 7, ≤ MAX). Fuente única para API y bot.
QUICK_PLAN_DURATION_DAYS: tuple[int, ...] = (
    7,
    14,
    21,
    28,
    42,
    56,
    84,
    112,
    168,
    364,
)


class DurationParseError(ValueError):
    """Invalid user input for duration."""


def validate_duration_days(value: int) -> int:
    if value < MIN_PLAN_DURATION_DAYS or value > MAX_PLAN_DURATION_DAYS:
        raise ValueError(
            f"La duración debe estar entre {MIN_PLAN_DURATION_DAYS} y {MAX_PLAN_DURATION_DAYS} días."
        )
    if value % 7 != 0:
        raise ValueError(
            "La duración debe ser un múltiplo de 7 (semanas completas), p. ej. 7, 14, 21."
        )
    return value


def parse_duration_text(text: str) -> int:
    """Parses free text from chat (simple Spanish)."""
    raw = (text or "").strip().lower()
    if raw in (
        "",
        "7",
        "default",
        "defecto",
        "una semana",
        "1 semana",
        "semana",
        "1",
    ):
        return DEFAULT_PLAN_DURATION_DAYS

    m = re.match(r"^(\d+)\s*semanas?$", raw)
    if m:
        return validate_duration_days(int(m.group(1)) * 7)

    m2 = re.match(r"^(\d+)\s*sem\.?$", raw)
    if m2:
        return validate_duration_days(int(m2.group(1)) * 7)

    try:
        n = int(float(raw.replace(",", ".").strip()))
    except ValueError as e:
        raise DurationParseError(
            "No reconocí la duración. Ejemplos: «7», «14», «21», «3 semanas»."
        ) from e

    try:
        return validate_duration_days(n)
    except ValueError as e:
        raise DurationParseError(str(e)) from e


def apply_plan_duration_metadata(plan: dict[str, Any], duration_days: int) -> dict[str, Any]:
    """Adds duration metadata to plan JSON without breaking legacy consumers."""
    d = validate_duration_days(duration_days)
    out = dict(plan)
    weeks = d // 7
    out["plan_duration_days"] = d
    out["plan_cycle_days"] = 7
    out["plan_duration_weeks"] = weeks
    out["plan_repeat_instruction_es"] = (
        f"Este documento describe un ciclo base de 7 días. Repítalo durante {d} días en total "
        f"({weeks} semana(s)), manteniendo el mismo patrón día a día salvo indicación médica distinta."
    )
    return out


def optional_plan_duration_days(plan: Any) -> int | None:
    """Duration in plan JSON if present and valid; None otherwise (e.g. legacy diets)."""
    if not isinstance(plan, dict):
        return None
    d = plan.get("plan_duration_days")
    if isinstance(d, int):
        try:
            return validate_duration_days(d)
        except ValueError:
            return None
    return None


def duration_from_existing_plan(plan: Any) -> int:
    """Reads duration from a saved plan or returns the default."""
    resolved = optional_plan_duration_days(plan)
    return resolved if resolved is not None else DEFAULT_PLAN_DURATION_DAYS
