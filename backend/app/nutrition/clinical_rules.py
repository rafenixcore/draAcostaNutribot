"""Basic non-substitutive clinical rules: conservative adjustments, alerts, and traceability."""

from __future__ import annotations

from app.nutrition.contract import (
    MedicalConditionCode,
    NormalizedNutritionGoal,
    NutritionAlert,
    NutritionAlertSeverity,
    NutritionCalculationInput,
)

# Tope conservador de proteína (g/kg/d) si hay enfermedad renal en el perfil.
RENAL_PROTEIN_G_PER_KG_MAX = 0.88

# Reduce la fracción calórica de grasa si hay dislipidemia (el resto tiende a hidratos).
DYSLIPIDEMIA_FAT_FRACTION_MULTIPLIER = 0.90


def apply_basic_clinical_rules(
    calc: NutritionCalculationInput,
    base_protein_g_per_kg: float,
    base_fat_calorie_fraction: float,
) -> tuple[float, float, list[NutritionAlert], list[str]]:
    """
    Ajusta proteína y fracción de grasa de forma acotada y emite alertas orientativas.
    No sustituye criterio médico ni estadios renales.
    """
    protein_g_per_kg = base_protein_g_per_kg
    fat_frac = base_fat_calorie_fraction
    alerts: list[NutritionAlert] = []
    rules: list[str] = []
    codes = calc.condition_codes

    if MedicalConditionCode.RENAL in codes:
        if protein_g_per_kg > RENAL_PROTEIN_G_PER_KG_MAX:
            protein_g_per_kg = RENAL_PROTEIN_G_PER_KG_MAX
            rules.append("renal_protein_ceiling_applied")
        alerts.append(
            NutritionAlert(
                code="renal_protein_policy",
                severity=NutritionAlertSeverity.WARN,
                message_es="Enfermedad renal declarada: se aplica un tope conservador de proteína; "
                "debe individualizarse con el equipo tratante (e.g. nefrología).",
                blocks_generation=False,
            )
        )
        if calc.goal in (
            NormalizedNutritionGoal.MUSCLE_GAIN,
            NormalizedNutritionGoal.WEIGHT_GAIN,
        ):
            alerts.append(
                NutritionAlert(
                    code="renal_high_protein_goal_conflict",
                    severity=NutritionAlertSeverity.WARN,
                    message_es="Objetivo de aumento de peso/masa con enfermedad renal: revisar "
                    "prioridades y seguridad proteica con supervisión clínica.",
                    blocks_generation=False,
                )
            )

    if MedicalConditionCode.DIABETES in codes:
        rules.append("diabetes_carb_distribution_low_gi")
        alerts.append(
            NutritionAlert(
                code="diabetes_meal_planning",
                severity=NutritionAlertSeverity.WARN,
                message_es="Diabetes: priorizar hidratos integrales y reparto en comidas; "
                "evitar azúcares añadidos y ajustar con criterio médico y farmacología.",
                blocks_generation=False,
            )
        )

    if MedicalConditionCode.HYPERTENSION in codes:
        rules.append("hypertension_sodium_moderation")
        alerts.append(
            NutritionAlert(
                code="hypertension_sodium",
                severity=NutritionAlertSeverity.WARN,
                message_es="Hipertensión: moderar sodio y ultraprocesados; patrón tipo DASH "
                "como referencia general (no sustituye tratamiento).",
                blocks_generation=False,
            )
        )

    if MedicalConditionCode.DYSLIPIDEMIA in codes:
        fat_frac = max(0.20, fat_frac * DYSLIPIDEMIA_FAT_FRACTION_MULTIPLIER)
        rules.append("dyslipidemia_reduced_fat_fraction")
        alerts.append(
            NutritionAlert(
                code="dyslipidemia_lipids",
                severity=NutritionAlertSeverity.WARN,
                message_es="Dislipidemia: limitar grasas saturadas y trans; favorecer grasas "
                "insaturadas y fibra según tolerancia.",
                blocks_generation=False,
            )
        )

    return protein_g_per_kg, fat_frac, alerts, rules
