"""Deterministic calculation: BMR (Mifflin-St Jeor), TDEE, BMI, target calories, and macros."""

from __future__ import annotations

from app.nutrition.clinical_rules import apply_basic_clinical_rules
from app.nutrition.contract import (
    ENGINE_SCHEMA_VERSION,
    DietStyle,
    MacroModePreference,
    MacroPreferenceLevel,
    MedicalConditionCode,
    NormalizedActivityLevel,
    NormalizedNutritionGoal,
    NutritionAlert,
    NutritionAlertSeverity,
    NutritionInput,
    NutritionResult,
    NutritionStrategyMode,
    SexForBmr,
)

# Factores de actividad estándar (TDEE = BMR × factor).
ACTIVITY_FACTOR: dict[NormalizedActivityLevel, float] = {
    NormalizedActivityLevel.SEDENTARY: 1.2,
    NormalizedActivityLevel.LIGHT: 1.375,
    NormalizedActivityLevel.MODERATE: 1.55,
    NormalizedActivityLevel.HIGH: 1.725,
    NormalizedActivityLevel.VERY_HIGH: 1.9,
}

# Multiplicador sobre TDEE según objetivo (antes de aplicar pisos de seguridad).
GOAL_TDEE_FACTOR: dict[NormalizedNutritionGoal, float] = {
    NormalizedNutritionGoal.FAT_LOSS: 0.80,
    NormalizedNutritionGoal.MAINTENANCE: 1.0,
    NormalizedNutritionGoal.MUSCLE_GAIN: 1.12,
    NormalizedNutritionGoal.WEIGHT_GAIN: 1.18,
}

# Fracción de grasa sobre calorías totales objetivo (resto a hidratos tras fijar proteína).
GOAL_FAT_CALORIE_FRACTION: dict[NormalizedNutritionGoal, float] = {
    NormalizedNutritionGoal.FAT_LOSS: 0.28,
    NormalizedNutritionGoal.MAINTENANCE: 0.30,
    NormalizedNutritionGoal.MUSCLE_GAIN: 0.27,
    NormalizedNutritionGoal.WEIGHT_GAIN: 0.30,
}

# Proteína (g/kg/d) según objetivo y actividad; se aplica tope blando antes del tope duro.
_PROTEIN_MAINTENANCE_BY_ACTIVITY: dict[NormalizedActivityLevel, float] = {
    NormalizedActivityLevel.SEDENTARY: 0.90,
    NormalizedActivityLevel.LIGHT: 1.00,
    NormalizedActivityLevel.MODERATE: 1.15,
    NormalizedActivityLevel.HIGH: 1.30,
    NormalizedActivityLevel.VERY_HIGH: 1.45,
}

# Tope blando (g/kg) — por encima se registra advertencia.
SOFT_CAP_PROTEIN_G_PER_KG = 2.2
# Tope duro (g/kg) — no se supera; por encima de esto se bloquea generación.
HARD_CAP_PROTEIN_G_PER_KG = 2.8

ABSOLUTE_MIN_KCAL = {
    SexForBmr.FEMALE: 1200,
    SexForBmr.MALE: 1500,
}

BMI_UNDERWEIGHT = 18.5
BMI_OVERWEIGHT = 25.0
BMI_OBESE = 30.0


def _bmr_mifflin_st_jeor(
    weight_kg: float,
    height_cm: float,
    age_years: int,
    sex: SexForBmr,
) -> float:
    base = 10.0 * weight_kg + 6.25 * height_cm - 5.0 * float(age_years)
    return base + (5.0 if sex == SexForBmr.MALE else -161.0)


def _bmi(weight_kg: float, height_cm: float) -> float:
    h_m = height_cm / 100.0
    return weight_kg / (h_m * h_m)


def _protein_g_per_kg_unclamped(
    goal: NormalizedNutritionGoal,
    activity: NormalizedActivityLevel,
) -> float:
    if goal == NormalizedNutritionGoal.FAT_LOSS:
        return 1.75
    if goal == NormalizedNutritionGoal.MUSCLE_GAIN:
        return 1.85
    if goal == NormalizedNutritionGoal.WEIGHT_GAIN:
        return 1.45
    return _PROTEIN_MAINTENANCE_BY_ACTIVITY[activity]


def _validate_physiology(
    weight_kg: float,
    height_cm: float,
    age_years: int,
) -> NutritionAlert | None:
    if weight_kg <= 0 or weight_kg > 400:
        return NutritionAlert(
            code="invalid_weight",
            severity=NutritionAlertSeverity.BLOCK,
            message_es="Peso fuera de rango válido para el cálculo.",
            blocks_generation=True,
        )
    if height_cm < 80 or height_cm > 250:
        return NutritionAlert(
            code="invalid_height",
            severity=NutritionAlertSeverity.BLOCK,
            message_es="Estatura fuera de rango válido para el cálculo.",
            blocks_generation=True,
        )
    if age_years < 14 or age_years > 100:
        return NutritionAlert(
            code="invalid_age",
            severity=NutritionAlertSeverity.BLOCK,
            message_es="La edad debe estar entre 14 y 100 años.",
            blocks_generation=True,
        )
    return None


def _bmi_alerts(bmi: float) -> list[NutritionAlert]:
    out: list[NutritionAlert] = []
    if bmi < BMI_UNDERWEIGHT:
        out.append(
            NutritionAlert(
                code="bmi_low",
                severity=NutritionAlertSeverity.WARN,
                message_es=f"IMC bajo ({bmi:.1f}). Conviene valoración clínica antes de restricciones.",
                blocks_generation=False,
            )
        )
    elif bmi >= BMI_OBESE:
        out.append(
            NutritionAlert(
                code="bmi_high",
                severity=NutritionAlertSeverity.WARN,
                message_es=f"IMC en obesidad ({bmi:.1f}). Ajustar expectativas y seguimiento médico.",
                blocks_generation=False,
            )
        )
    elif bmi >= BMI_OVERWEIGHT:
        out.append(
            NutritionAlert(
                code="bmi_overweight",
                severity=NutritionAlertSeverity.WARN,
                message_es=f"IMC en sobrepeso ({bmi:.1f}).",
                blocks_generation=False,
            )
        )
    return out


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _apply_guided_preferences(
    prot_per_kg_desired: float,
    fat_frac: float,
    diet_style: DietStyle | None,
    macro_mode: MacroModePreference,
) -> tuple[float, float, list[str]]:
    applied: list[str] = []
    if diet_style == DietStyle.LOW_CARB:
        fat_frac += 0.07
        prot_per_kg_desired += 0.10
        applied.append("style_low_carb")
    elif diet_style == DietStyle.HIGH_CARB:
        fat_frac -= 0.06
        applied.append("style_high_carb")
    elif diet_style == DietStyle.HIGH_PROTEIN:
        prot_per_kg_desired += 0.25
        fat_frac += 0.02
        applied.append("style_high_protein")
    elif diet_style == DietStyle.MEDITERRANEAN:
        fat_frac += 0.02
        applied.append("style_mediterranean")

    if macro_mode.protein == MacroPreferenceLevel.LOW:
        prot_per_kg_desired -= 0.20
        applied.append("macro_protein_low")
    elif macro_mode.protein == MacroPreferenceLevel.HIGH:
        prot_per_kg_desired += 0.25
        applied.append("macro_protein_high")

    if macro_mode.carbs == MacroPreferenceLevel.LOW:
        fat_frac += 0.07
        applied.append("macro_carbs_low")
    elif macro_mode.carbs == MacroPreferenceLevel.HIGH:
        fat_frac -= 0.06
        applied.append("macro_carbs_high")

    if macro_mode.fat == MacroPreferenceLevel.LOW:
        fat_frac -= 0.05
        applied.append("macro_fat_low")
    elif macro_mode.fat == MacroPreferenceLevel.HIGH:
        fat_frac += 0.06
        applied.append("macro_fat_high")

    prot_per_kg_desired = _clamp(prot_per_kg_desired, 0.8, HARD_CAP_PROTEIN_G_PER_KG)
    fat_frac = _clamp(fat_frac, 0.20, 0.45)
    return prot_per_kg_desired, fat_frac, applied


def compute_nutrition(nutrition_input: NutritionInput) -> NutritionResult:
    """
    Executes the calculation pipeline on already-normalized inputs.
    Does not call DB or LLM.
    """
    c = nutrition_input.calculation
    prefs = nutrition_input.preferences
    alerts: list[NutritionAlert] = []
    clinical_rules: list[str] = []
    override_warnings: list[str] = []
    applied_pref_labels: list[str] = []
    manual_override_used = False

    bad = _validate_physiology(c.weight_kg, c.height_cm, c.age_years)
    if bad:
        return NutritionResult(
            engine_schema_version=ENGINE_SCHEMA_VERSION,
            alerts=(bad,),
            applied_mode=prefs.strategy_mode,
        )

    if MedicalConditionCode.OTHER_UNSPECIFIED in c.condition_codes:
        alerts.append(
            NutritionAlert(
                code="condition_unspecified",
                severity=NutritionAlertSeverity.BLOCK,
                message_es="El paciente tiene condiciones de salud que requieren revisión manual antes de generar la dieta.",
                blocks_generation=True,
            )
        )

    bmi = round(_bmi(c.weight_kg, c.height_cm), 2)
    alerts.extend(_bmi_alerts(bmi))

    bmr = _bmr_mifflin_st_jeor(c.weight_kg, c.height_cm, c.age_years, c.sex)
    af = ACTIVITY_FACTOR[c.activity]
    tdee = bmr * af

    raw_target = tdee * GOAL_TDEE_FACTOR[c.goal]
    min_kcal = ABSOLUTE_MIN_KCAL[c.sex]
    target_kcal = int(round(raw_target))
    if (
        prefs.strategy_mode == NutritionStrategyMode.MANUAL
        and prefs.manual_targets is not None
        and prefs.manual_targets.daily_calories is not None
    ):
        target_kcal = int(round(prefs.manual_targets.daily_calories))
        manual_override_used = True
        applied_pref_labels.append("manual_target_daily_calories")

    if target_kcal < min_kcal:
        if prefs.strategy_mode == NutritionStrategyMode.MANUAL:
            msg = (
                f"Modo manual: calorías objetivo ({target_kcal} kcal/día) por debajo del "
                f"mínimo de seguridad de referencia ({min_kcal} kcal/día)."
            )
            alerts.append(
                NutritionAlert(
                    code="manual_calories_below_safety_floor",
                    severity=NutritionAlertSeverity.WARN,
                    message_es=msg,
                    blocks_generation=False,
                )
            )
            override_warnings.append(msg)
        else:
            alerts.append(
                NutritionAlert(
                    code="calories_below_safety_floor",
                    severity=NutritionAlertSeverity.BLOCK,
                    message_es=f"Las calorías objetivo ({target_kcal} kcal/día) están por debajo del "
                    f"mínimo de seguridad usado por el sistema ({min_kcal} kcal/día).",
                    blocks_generation=True,
                )
            )
            return NutritionResult(
                engine_schema_version=ENGINE_SCHEMA_VERSION,
                bmr_kcal=round(bmr, 1),
                tdee_kcal=round(tdee, 1),
                activity_factor=af,
                target_daily_calories=target_kcal,
                bmi=bmi,
                alerts=tuple(alerts),
                clinical_rules_applied=tuple(clinical_rules),
                applied_mode=prefs.strategy_mode,
                applied_preferences={"labels": applied_pref_labels},
                manual_override_used=False,
                override_warnings=tuple(override_warnings),
            )

    # Déficit > ~24 % respecto a TDEE (p. ej. factor < 0.76) — aviso, no bloqueo.
    if c.goal == NormalizedNutritionGoal.FAT_LOSS and raw_target < tdee * 0.76:
        alerts.append(
            NutritionAlert(
                code="deficit_aggressive",
                severity=NutritionAlertSeverity.WARN,
                message_es="Déficit calórico marcado respecto al gasto estimado; conviene "
                "vigilar adherencia, saciedad y seguimiento clínico.",
                blocks_generation=False,
            )
        )

    base_fat_frac = GOAL_FAT_CALORIE_FRACTION[c.goal]
    prot_per_kg_desired = _protein_g_per_kg_unclamped(c.goal, c.activity)
    prot_per_kg_desired, fat_frac, clin_alerts, clin_rules = apply_basic_clinical_rules(
        c,
        prot_per_kg_desired,
        base_fat_frac,
    )
    alerts.extend(clin_alerts)
    clinical_rules.extend(clin_rules)

    if prefs.strategy_mode == NutritionStrategyMode.GUIDED:
        prot_per_kg_desired, fat_frac, applied_labels = _apply_guided_preferences(
            prot_per_kg_desired,
            fat_frac,
            prefs.diet_style,
            prefs.macro_mode,
        )
        applied_pref_labels.extend(applied_labels)

    if prot_per_kg_desired > SOFT_CAP_PROTEIN_G_PER_KG:
        alerts.append(
            NutritionAlert(
                code="protein_near_upper_bound",
                severity=NutritionAlertSeverity.WARN,
                message_es="Proteína objetivo en zona alta; vigilar tolerancia renal y hidratación.",
                blocks_generation=False,
            )
        )

    prot_per_kg = min(prot_per_kg_desired, HARD_CAP_PROTEIN_G_PER_KG)
    protein_g = round(c.weight_kg * prot_per_kg, 1)

    protein_kcal = protein_g * 4.0
    fat_kcal = target_kcal * fat_frac
    fat_g = round(fat_kcal / 9.0, 1)
    carb_kcal = max(0.0, float(target_kcal) - protein_kcal - fat_g * 9.0)
    carbs_g = round(carb_kcal / 4.0, 1)

    if prefs.strategy_mode == NutritionStrategyMode.MANUAL and prefs.manual_targets is not None:
        mt = prefs.manual_targets
        if mt.protein_g is not None:
            protein_g = round(float(mt.protein_g), 1)
            manual_override_used = True
            applied_pref_labels.append("manual_target_protein_g")
        if mt.fat_g is not None:
            fat_g = round(float(mt.fat_g), 1)
            manual_override_used = True
            applied_pref_labels.append("manual_target_fat_g")
        if mt.carbs_g is not None:
            carbs_g = round(float(mt.carbs_g), 1)
            manual_override_used = True
            applied_pref_labels.append("manual_target_carbs_g")
        if mt.protein_g is None or mt.fat_g is None or mt.carbs_g is None:
            remaining_kcal = max(0.0, float(target_kcal) - protein_g * 4.0 - fat_g * 9.0)
            if mt.carbs_g is None:
                carbs_g = round(remaining_kcal / 4.0, 1)
        macro_kcal_total = protein_g * 4.0 + carbs_g * 4.0 + fat_g * 9.0
        if abs(macro_kcal_total - float(target_kcal)) > 120:
            msg = (
                "Modo manual: la suma calórica de macros difiere de calorías objetivo; "
                "revisar coherencia clínica."
            )
            alerts.append(
                NutritionAlert(
                    code="manual_macro_calorie_mismatch",
                    severity=NutritionAlertSeverity.WARN,
                    message_es=msg,
                    blocks_generation=False,
                )
            )
            override_warnings.append(msg)
        carb_kcal = max(0.0, float(target_kcal) - protein_g * 4.0 - fat_g * 9.0)

    if carb_kcal < float(target_kcal) * 0.12:
        alerts.append(
            NutritionAlert(
                code="carbs_very_low",
                severity=NutritionAlertSeverity.WARN,
                message_es="Hidratos resultantes bajos respecto al total calórico; revisar equilibrio del plan.",
                blocks_generation=False,
            )
        )

    total_kcal_check = protein_g * 4.0 + carbs_g * 4.0 + fat_g * 9.0
    pct_p = round(100.0 * (protein_g * 4.0) / total_kcal_check, 1)
    pct_c = round(100.0 * (carbs_g * 4.0) / total_kcal_check, 1)
    pct_f = round(100.0 * (fat_g * 9.0) / total_kcal_check, 1)

    if pct_p > 35.0:
        alerts.append(
            NutritionAlert(
                code="protein_energy_fraction_high",
                severity=NutritionAlertSeverity.WARN,
                message_es="La proteína representa un porcentaje alto de la energía total; "
                "verificar tolerancia y equilibrio del plan.",
                blocks_generation=False,
            )
        )

    if (
        MedicalConditionCode.DIABETES in c.condition_codes
        and pct_c < 30.0
    ):
        alerts.append(
            NutritionAlert(
                code="diabetes_low_carb_fraction",
                severity=NutritionAlertSeverity.WARN,
                message_es="Con diabetes declarada, el reparto muestra hidratos bajos en % de energía; "
                "revisar riesgo de hipoglucemias y coherencia con tratamiento.",
                blocks_generation=False,
            )
        )

    return NutritionResult(
        engine_schema_version=ENGINE_SCHEMA_VERSION,
        bmr_kcal=round(bmr, 1),
        tdee_kcal=round(tdee, 1),
        activity_factor=af,
        target_daily_calories=target_kcal,
        bmi=bmi,
        protein_g=protein_g,
        carbs_g=carbs_g,
        fat_g=fat_g,
        protein_pct=pct_p,
        carbs_pct=pct_c,
        fat_pct=pct_f,
        alerts=tuple(alerts),
        clinical_rules_applied=tuple(clinical_rules),
        applied_mode=prefs.strategy_mode,
        applied_preferences={
            "strategy_mode": prefs.strategy_mode.value,
            "diet_style": prefs.diet_style.value if prefs.diet_style else None,
            "macro_mode": {
                "protein": prefs.macro_mode.protein.value if prefs.macro_mode.protein else None,
                "carbs": prefs.macro_mode.carbs.value if prefs.macro_mode.carbs else None,
                "fat": prefs.macro_mode.fat.value if prefs.macro_mode.fat else None,
            },
            "labels": applied_pref_labels,
        },
        manual_override_used=manual_override_used,
        override_warnings=tuple(override_warnings),
    )
