"""Builds NutritionInput from ORM models (no LLM involvement)."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from typing import Optional

from app.logic.profile import norm
from app.models import Patient, PatientMetrics, PatientProfile
from app.nutrition.contract import (
    DietStyle,
    MacroModePreference,
    MacroPreferenceLevel,
    ManualTargets,
    MedicalConditionCode,
    NormalizedActivityLevel,
    NormalizedNutritionGoal,
    NutritionCalculationInput,
    NutritionInput,
    NutritionPreferences,
    NutritionStrategyMode,
    PatientContextualFactors,
    SexForBmr,
)


def _merge_food_lists(a: str | None, b: str | None) -> str | None:
    """Merge two comma-separated food lists, deduplicating entries."""
    items: list[str] = []
    seen: set[str] = set()
    for raw in (a, b):
        if not raw or not raw.strip():
            continue
        for item in raw.split(","):
            cleaned = item.strip().lower()
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                items.append(item.strip())
    return ", ".join(items) if items else None


class NutritionInputBuildError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def _age_years(birth: date) -> int:
    today = date.today()
    return today.year - birth.year - (
        (today.month, today.day) < (birth.month, birth.day)
    )


def _float_metric(v: Optional[Decimal | float | int]) -> float:
    if v is None:
        raise NutritionInputBuildError("missing_metric", "Falta un valor numérico requerido para el cálculo.")
    return float(v)


def _normalize_sex(raw: Optional[str]) -> SexForBmr:
    s = norm(raw)
    if s in ("m", "male", "masculino", "hombre", "varon", "varón"):
        return SexForBmr.MALE
    if s in ("f", "female", "femenino", "mujer"):
        return SexForBmr.FEMALE
    # Default to female for unrecognized values (e.g. "Otro", "other")
    return SexForBmr.FEMALE


def _normalize_activity(raw: Optional[str]) -> tuple[NormalizedActivityLevel, str | None]:
    s = norm(raw)
    if s in ("sedentary", "sedentario", "inactive", "sin ejercicio", "sin_ejercicio"):
        return NormalizedActivityLevel.SEDENTARY, None
    if s in ("light", "low", "bajo", "ligero", "ligera", "poca", "1-2 dias/semana", "1_2_dias"):
        return NormalizedActivityLevel.LIGHT, None
    if s in ("moderate", "moderado", "moderada", "medium", "medio", "med",
             "3-4 dias/semana", "3_4_dias"):
        return NormalizedActivityLevel.MODERATE, None
    if s in ("high", "alto", "alta", "active", "activo", "activa",
             "5-6 dias/semana", "5_6_dias"):
        return NormalizedActivityLevel.HIGH, None
    if s in ("very_high", "muy_alto", "muy alta", "muy alto", "athlete", "atleta",
             "muy activo", "muy activa", "entrenamiento diario"):
        return NormalizedActivityLevel.VERY_HIGH, None
    # Mapeo por palabras clave cuando el valor es descriptivo (dropdown con descripción)
    if "sedentario" in s or "sin ejercicio" in s:
        return NormalizedActivityLevel.SEDENTARY, None
    if "ligero" in s or "1-2" in s:
        return NormalizedActivityLevel.LIGHT, None
    if "moderado" in s or "3-4" in s:
        return NormalizedActivityLevel.MODERATE, None
    if "muy alto" in s or "atleta" in s or "diario" in s or "5-6" in s:
        return NormalizedActivityLevel.VERY_HIGH, None
    if "alto" in s or "5" in s or "6" in s:
        return NormalizedActivityLevel.HIGH, None
    if not s:
        return NormalizedActivityLevel.MODERATE, "activity_default_moderate"
    return NormalizedActivityLevel.MODERATE, f"activity_unmapped:{raw!r}"


def _normalize_goal(raw: Optional[str]) -> tuple[NormalizedNutritionGoal, str | None]:
    s = norm(raw).replace(" ", "_").replace("-", "_")
    if s in (
        "fat_loss",
        "lose_weight",
        "loseweight",
        "weight_loss",
        "perdida",
        "pérdida",
        "perdida_de_peso",
        "pérdida_de_peso",
        "adelgazar",
        "deficit",
        "déficit",
        "bajar",
        "bajar_de_peso",
        "perder",
        "perder_peso",
        "perder_de_peso",
        "reducir",
        "reducir_peso",
        "reduccion",
        "reducción",
        "bajar_peso",
        "health_improvement",
        "mejora_de_salud",
        "mejora de salud",
    ):
        return NormalizedNutritionGoal.FAT_LOSS, None
    if s in ("muscle_gain", "gain_muscle", "gainmuscle", "hipertrofia", "masa", "musculo",
             "músculo", "ganar_musculo", "ganar_músculo", "ganar musculo", "ganar músculo",
             "sports_performance", "rendimiento_deportivo", "rendimiento deportivo"):
        return NormalizedNutritionGoal.MUSCLE_GAIN, None
    if s in ("weight_gain", "gain_weight", "gainweight", "aumento", "subir",
             "subir_de_peso", "subir de peso", "aumentar_peso", "aumentar peso"):
        return NormalizedNutritionGoal.WEIGHT_GAIN, None
    if s in ("maintenance", "maintain", "mantenimiento", "mantener", "estable"):
        return NormalizedNutritionGoal.MAINTENANCE, None
    if not s:
        return NormalizedNutritionGoal.MAINTENANCE, "goal_default_maintenance"
    return NormalizedNutritionGoal.MAINTENANCE, f"goal_unmapped:{raw!r}"


_DISEASE_PATTERNS: tuple[tuple[re.Pattern[str], MedicalConditionCode], ...] = (
    (re.compile(r"\b(diabetes|diabetico|diabético|dm1|dm2|dm\s*1|dm\s*2|glicemia)\b", re.I), MedicalConditionCode.DIABETES),
    (re.compile(r"\b(hipertension|hipertensión|presion\s+alta|presión\s+alta|hta)\b", re.I), MedicalConditionCode.HYPERTENSION),
    (re.compile(r"\b(renal|riñon|riñón|nefro|erc|insuficiencia\s+renal|ckd)\b", re.I), MedicalConditionCode.RENAL),
    (re.compile(r"\b(dislipidemia|hipercolesterol|colesterol|triglicer|lípidos|lipidos)\b", re.I), MedicalConditionCode.DYSLIPIDEMIA),
)


def _parse_condition_codes(diseases: Optional[str], medical_history: Optional[str]) -> frozenset[MedicalConditionCode]:
    blob = f"{diseases or ''}\n{medical_history or ''}"
    if not norm(blob) or norm(blob) in ("none", "ninguna", "n/a", "na", "-"):
        return frozenset()
    found: set[MedicalConditionCode] = set()
    for rx, code in _DISEASE_PATTERNS:
        if rx.search(blob):
            found.add(code)
    return frozenset(found)


def build_patient_contextual(profile: PatientProfile) -> PatientContextualFactors:
    return PatientContextualFactors(
        stress_level=profile.stress_level,
        sleep_quality=profile.sleep_quality,
        sleep_hours=float(profile.sleep_hours) if profile.sleep_hours is not None else None,
        adherence_level=profile.adherence_level,
        budget_level=profile.budget_level,
        meal_schedule=profile.meal_schedule,
        exercise_type=profile.exercise_type,
        exercise_frequency_per_week=profile.exercise_frequency_per_week,
        food_preferences=profile.food_preferences,
        disliked_foods=_merge_food_lists(profile.disliked_foods, profile.foods_avoided),
        extra_notes=profile.extra_notes,
        water_intake_liters=float(profile.water_intake_liters)
        if profile.water_intake_liters is not None
        else None,
    )


def _normalize_strategy_mode(raw: Optional[str]) -> tuple[NutritionStrategyMode, str | None]:
    s = norm(raw)
    if s in ("", "auto"):
        return NutritionStrategyMode.AUTO, None
    if s in ("guided", "guiado"):
        return NutritionStrategyMode.GUIDED, None
    if s in ("manual",):
        return NutritionStrategyMode.MANUAL, None
    return NutritionStrategyMode.AUTO, f"strategy_unmapped:{raw!r}"


def _normalize_diet_style(raw: Optional[str]) -> tuple[Optional[DietStyle], str | None]:
    s = norm(raw).replace(" ", "_").replace("-", "_")
    if not s:
        return None, None
    if s in ("balanced", "balanceada"):
        return DietStyle.BALANCED, None
    if s in ("low_carb", "baja_en_carbohidratos"):
        return DietStyle.LOW_CARB, None
    if s in ("high_carb", "alta_en_carbohidratos"):
        return DietStyle.HIGH_CARB, None
    if s in ("high_protein", "alta_en_proteina", "alta_en_proteínas"):
        return DietStyle.HIGH_PROTEIN, None
    if s in ("mediterranean", "mediterranea", "mediterránea"):
        return DietStyle.MEDITERRANEAN, None
    return None, f"diet_style_unmapped:{raw!r}"


def _to_macro_pref(v: Optional[str]) -> tuple[Optional[MacroPreferenceLevel], str | None]:
    s = norm(v)
    if not s:
        return None, None
    if s in ("low", "bajo", "baja"):
        return MacroPreferenceLevel.LOW, None
    if s in ("normal", "medio", "media", "moderado", "moderada"):
        return MacroPreferenceLevel.NORMAL, None
    if s in ("high", "alto", "alta"):
        return MacroPreferenceLevel.HIGH, None
    return None, f"macro_pref_unmapped:{v!r}"


def _normalize_macro_mode(raw: Optional[dict]) -> tuple[MacroModePreference, tuple[str, ...]]:
    if not isinstance(raw, dict):
        return MacroModePreference(), ()
    notes: list[str] = []
    protein, n1 = _to_macro_pref(raw.get("protein"))
    carbs, n2 = _to_macro_pref(raw.get("carbs"))
    fat, n3 = _to_macro_pref(raw.get("fat"))
    for n in (n1, n2, n3):
        if n:
            notes.append(n)
    return MacroModePreference(protein=protein, carbs=carbs, fat=fat), tuple(notes)


def _normalize_manual_targets(raw: Optional[dict]) -> Optional[ManualTargets]:
    if not isinstance(raw, dict):
        return None
    out = ManualTargets()
    for key in ("daily_calories", "protein_g", "carbs_g", "fat_g"):
        v = raw.get(key)
        if v is None:
            continue
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if f > 0:
            setattr(out, key, f)
    if out.daily_calories is None and out.protein_g is None and out.carbs_g is None and out.fat_g is None:
        return None
    return out


def build_nutrition_input_from_bundle(
    patient: Patient,
    profile: PatientProfile,
    metrics: PatientMetrics,
    *,
    patient_id: Optional[int] = None,
    strategy_mode: Optional[str] = None,
    diet_style: Optional[str] = None,
    macro_mode: Optional[dict] = None,
    manual_targets: Optional[dict] = None,
) -> NutritionInput:
    if patient.birth_date is None:
        raise NutritionInputBuildError("missing_birth_date", "Falta fecha de nacimiento.")
    age = _age_years(patient.birth_date)
    sex = _normalize_sex(patient.sex)
    weight_kg = _float_metric(metrics.weight_kg)
    height_cm = _float_metric(metrics.height_cm)

    act, act_note = _normalize_activity(profile.activity_level)
    goal, goal_note = _normalize_goal(profile.objective)
    notes: list[str] = []
    if act_note:
        notes.append(act_note)
    if goal_note:
        notes.append(goal_note)
    mode, mode_note = _normalize_strategy_mode(strategy_mode)
    if mode_note:
        notes.append(mode_note)
    style, style_note = _normalize_diet_style(diet_style)
    if style_note:
        notes.append(style_note)
    macro_pref, macro_notes = _normalize_macro_mode(macro_mode)
    notes.extend(macro_notes)
    manual = _normalize_manual_targets(manual_targets)

    calc = NutritionCalculationInput(
        weight_kg=weight_kg,
        height_cm=height_cm,
        age_years=age,
        sex=sex,
        activity=act,
        goal=goal,
        condition_codes=_parse_condition_codes(profile.diseases, profile.medical_history),
        food_allergies=profile.food_allergies,
        foods_avoided=profile.foods_avoided,
        medications=profile.medications,
        diseases_raw=profile.diseases,
    )
    return NutritionInput(
        calculation=calc,
        contextual=build_patient_contextual(profile),
        preferences=NutritionPreferences(
            strategy_mode=mode,
            diet_style=style,
            macro_mode=macro_pref,
            manual_targets=manual,
        ),
        patient_id=patient_id if patient_id is not None else patient.id,
        normalization_notes=tuple(notes),
    )
