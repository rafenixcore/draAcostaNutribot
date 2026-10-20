from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

ENGINE_SCHEMA_VERSION = "1.0"


class NormalizedActivityLevel(str, Enum):
    """Normalized activity level for TDEE factor calculation."""

    SEDENTARY = "sedentary"
    LIGHT = "light"
    MODERATE = "moderate"
    HIGH = "high"
    VERY_HIGH = "very_high"


class NormalizedNutritionGoal(str, Enum):
    """Internal nutrition goal (post-mapping from profile text)."""

    FAT_LOSS = "fat_loss"
    MAINTENANCE = "maintenance"
    MUSCLE_GAIN = "muscle_gain"
    WEIGHT_GAIN = "weight_gain"


class NutritionStrategyMode(str, Enum):
    AUTO = "auto"
    GUIDED = "guided"
    MANUAL = "manual"


class DietStyle(str, Enum):
    BALANCED = "balanced"
    LOW_CARB = "low_carb"
    HIGH_CARB = "high_carb"
    HIGH_PROTEIN = "high_protein"
    MEDITERRANEAN = "mediterranean"


class MacroPreferenceLevel(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class MedicalConditionCode(str, Enum):
    """Conditions with explicit engine rules; others go through review flow."""

    DIABETES = "diabetes"
    HYPERTENSION = "hypertension"
    RENAL = "renal"
    DYSLIPIDEMIA = "dyslipidemia"
    OTHER_UNSPECIFIED = "other_unspecified"


class SexForBmr(str, Enum):
    """Biological sex for Mifflin-St Jeor equation (values expected after normalization)."""

    MALE = "male"
    FEMALE = "female"


class NutritionAlertSeverity(str, Enum):
    INFO = "info"
    WARN = "warn"
    BLOCK = "block"


@dataclass(frozen=True)
class NutritionAlert:
    """Clinical or safety alert emitted by the engine (UI text in Spanish)."""

    code: str
    severity: NutritionAlertSeverity
    message_es: str
    blocks_generation: bool = False


@dataclass
class PatientContextualFactors:
    """Contextual layer: does not alter base formulas; feeds plan composition and recommendations."""

    stress_level: Optional[int] = None
    sleep_quality: Optional[int] = None
    sleep_hours: Optional[float] = None
    adherence_level: Optional[int] = None
    budget_level: Optional[str] = None
    meal_schedule: Optional[Any] = None
    exercise_type: Optional[str] = None
    exercise_frequency_per_week: Optional[int] = None
    food_preferences: Optional[str] = None
    disliked_foods: Optional[str] = None
    extra_notes: Optional[str] = None
    water_intake_liters: Optional[float] = None


@dataclass
class NutritionCalculationInput:
    """Minimum inputs for BMR, TDEE, BMI, and caloric distribution."""

    weight_kg: float
    height_cm: float
    age_years: int
    sex: SexForBmr
    activity: NormalizedActivityLevel
    goal: NormalizedNutritionGoal
    condition_codes: frozenset[MedicalConditionCode] = field(default_factory=frozenset)
    food_allergies: Optional[str] = None
    foods_avoided: Optional[str] = None
    medications: Optional[str] = None
    diseases_raw: Optional[str] = None


@dataclass
class MacroModePreference:
    protein: Optional[MacroPreferenceLevel] = None
    carbs: Optional[MacroPreferenceLevel] = None
    fat: Optional[MacroPreferenceLevel] = None


@dataclass
class ManualTargets:
    daily_calories: Optional[float] = None
    protein_g: Optional[float] = None
    carbs_g: Optional[float] = None
    fat_g: Optional[float] = None


@dataclass
class NutritionPreferences:
    strategy_mode: NutritionStrategyMode = NutritionStrategyMode.AUTO
    diet_style: Optional[DietStyle] = None
    macro_mode: MacroModePreference = field(default_factory=MacroModePreference)
    manual_targets: Optional[ManualTargets] = None


@dataclass
class NutritionInput:
    """Complete engine input contract: calculation + context + traceability."""

    calculation: NutritionCalculationInput
    contextual: PatientContextualFactors = field(default_factory=PatientContextualFactors)
    preferences: NutritionPreferences = field(default_factory=NutritionPreferences)
    patient_id: Optional[int] = None
    normalization_notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class NutritionResult:
    """Deterministic engine output; the official source of numbers for prompt and plan."""

    engine_schema_version: str
    bmr_kcal: Optional[float] = None
    tdee_kcal: Optional[float] = None
    activity_factor: Optional[float] = None
    target_daily_calories: Optional[int] = None
    bmi: Optional[float] = None
    protein_g: Optional[float] = None
    carbs_g: Optional[float] = None
    fat_g: Optional[float] = None
    protein_pct: Optional[float] = None
    carbs_pct: Optional[float] = None
    fat_pct: Optional[float] = None
    alerts: tuple[NutritionAlert, ...] = ()
    clinical_rules_applied: tuple[str, ...] = ()
    applied_mode: NutritionStrategyMode = NutritionStrategyMode.AUTO
    applied_preferences: dict[str, Any] = field(default_factory=dict)
    manual_override_used: bool = False
    override_warnings: tuple[str, ...] = ()

    def blocks_generation(self) -> bool:
        return any(a.blocks_generation for a in self.alerts)

    def to_plan_engine_dict(self) -> dict[str, Any]:
        """Suggested subdocument for structured_plan_json['nutrition_engine']."""
        return {
            "engine_schema_version": self.engine_schema_version,
            "bmr_kcal": self.bmr_kcal,
            "tdee_kcal": self.tdee_kcal,
            "bmi": self.bmi,
            "activity_factor": self.activity_factor,
            "goal_calories": self.target_daily_calories,
            "applied_mode": self.applied_mode.value,
            "applied_preferences": self.applied_preferences,
            "manual_override_used": self.manual_override_used,
            "override_warnings": list(self.override_warnings),
        }

    def to_plan_macro_grams_dict(self) -> dict[str, Any]:
        return {
            "protein_g": self.protein_g,
            "carbs_g": self.carbs_g,
            "fat_g": self.fat_g,
        }

    def to_plan_macro_pct_dict(self) -> dict[str, Any]:
        return {
            "protein": self.protein_pct,
            "carbs": self.carbs_pct,
            "fat": self.fat_pct,
        }

    def alerts_as_json(self) -> list[dict[str, Any]]:
        return [
            {
                "code": a.code,
                "severity": a.severity.value,
                "message_es": a.message_es,
                "blocks_generation": a.blocks_generation,
            }
            for a in self.alerts
        ]
