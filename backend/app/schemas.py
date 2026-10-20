from datetime import date, datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class VerifyTokenResponse(BaseModel):
    valid: bool
    email: Optional[str] = None


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str = "doctor"
    must_change_password: bool = False


class DoctorCreate(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    phone: Optional[str] = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class AdminDoctorCreate(BaseModel):
    full_name: str
    email: EmailStr
    temporary_password: Optional[str] = None
    phone: Optional[str] = None
    role: Literal["admin", "doctor"] = "doctor"


class AdminDoctorUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    role: Optional[Literal["admin", "doctor"]] = None
    is_active: Optional[bool] = None


class AdminPasswordReset(BaseModel):
    temporary_password: str = Field(min_length=8, max_length=128)


class DoctorOut(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    phone: Optional[str] = None
    role: str = "doctor"
    must_change_password: bool = False
    is_active: bool
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AdminDoctorCreateResponse(DoctorOut):
    generated_password: str


class PatientCreate(BaseModel):
    first_name: str
    last_name: str
    birth_date: Optional[date] = None
    sex: Optional[str] = None
    whatsapp: Optional[str] = None
    email: Optional[EmailStr] = None
    country: Optional[str] = None
    city: Optional[str] = None


class PatientOut(BaseModel):
    id: int
    doctor_id: int
    first_name: str
    last_name: str
    birth_date: Optional[date] = None
    sex: Optional[str] = None
    whatsapp: Optional[str] = None
    email: Optional[EmailStr] = None
    country: Optional[str] = None
    city: Optional[str] = None
    source: str
    is_active: bool
    is_archived: bool = False

    model_config = ConfigDict(from_attributes=True)


class PatientUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    birth_date: Optional[date] = None
    sex: Optional[str] = None
    whatsapp: Optional[str] = None
    email: Optional[EmailStr] = None
    country: Optional[str] = None
    city: Optional[str] = None
    is_active: Optional[bool] = None
    is_archived: Optional[bool] = None


class PatientProfileOut(BaseModel):
    id: int
    patient_id: int
    objective: Optional[str] = None
    diseases: Optional[str] = None
    medications: Optional[str] = None
    food_allergies: Optional[str] = None
    foods_avoided: Optional[str] = None
    medical_history: Optional[str] = None
    dietary_style: Optional[str] = None
    food_preferences: Optional[str] = None
    disliked_foods: Optional[str] = None
    meal_schedule: Optional[Any] = None
    water_intake_liters: Optional[float] = None
    activity_level: Optional[str] = None
    stress_level: Optional[int] = None
    sleep_quality: Optional[int] = None
    sleep_hours: Optional[float] = None
    budget_level: Optional[str] = None
    adherence_level: Optional[int] = None
    exercise_frequency_per_week: Optional[int] = None
    exercise_type: Optional[str] = None
    extra_notes: Optional[str] = None
    completed_by_patient: bool = False
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class PatientMetricsOut(BaseModel):
    id: int
    patient_id: int
    weight_kg: Optional[float] = None
    height_cm: Optional[float] = None
    neck_cm: Optional[float] = None
    chest_cm: Optional[float] = None
    waist_cm: Optional[float] = None
    hip_cm: Optional[float] = None
    leg_cm: Optional[float] = None
    calf_cm: Optional[float] = None
    recorded_at: datetime
    source: str
    notes: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedPatients(BaseModel):
    items: list[PatientOut]
    total: int
    page: int
    page_size: int


class PatientSummaryOut(BaseModel):
    class PatientMini(BaseModel):
        id: int
        full_name: str

    class LatestMetricsMini(BaseModel):
        weight_kg: Optional[float] = None
        height_cm: Optional[float] = None

    class ProfileFlags(BaseModel):
        has_allergies: bool
        has_diseases: bool
        is_profile_complete: bool

    class LatestDietMini(BaseModel):
        id: int
        created_at: datetime
        plan_duration_days: Optional[int] = None

    patient: PatientMini
    latest_metrics: Optional[LatestMetricsMini] = None
    profile_flags: ProfileFlags
    latest_diet: Optional[LatestDietMini] = None


class DoctorMeUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None


class DashboardSummary(BaseModel):
    total_patients: int
    new_patients_30d: int
    incomplete_profiles: int
    diets_generated: int
    latest_activity: list[dict] = Field(default_factory=list)


class PatientProfileUpsert(BaseModel):
    objective: Optional[str] = None
    diseases: Optional[str] = None
    medications: Optional[str] = None
    food_allergies: Optional[str] = None
    foods_avoided: Optional[str] = None
    medical_history: Optional[str] = None
    dietary_style: Optional[str] = None
    food_preferences: Optional[str] = None
    disliked_foods: Optional[str] = None
    meal_schedule: Optional[Any] = None
    water_intake_liters: Optional[float] = None
    activity_level: Optional[str] = None
    stress_level: Optional[int] = None
    sleep_quality: Optional[int] = None
    sleep_hours: Optional[float] = None
    budget_level: Optional[str] = None
    adherence_level: Optional[int] = None
    exercise_frequency_per_week: Optional[int] = None
    exercise_type: Optional[str] = None
    extra_notes: Optional[str] = None


class PatientMetricsCreate(BaseModel):
    weight_kg: Optional[float] = None
    height_cm: Optional[float] = None
    neck_cm: Optional[float] = None
    chest_cm: Optional[float] = None
    waist_cm: Optional[float] = None
    hip_cm: Optional[float] = None
    leg_cm: Optional[float] = None
    calf_cm: Optional[float] = None
    recorded_at: Optional[datetime] = None
    source: Optional[str] = "admin"
    notes: Optional[str] = None


class IntakeLinkCreate(BaseModel):
    patient_id: Optional[int] = None
    link_type: str = "register"
    expires_in_days: int = Field(default=7, ge=1, le=365)
    max_uses: int = Field(default=1, ge=1, le=50)


class IntakeLinkOut(BaseModel):
    id: int
    doctor_id: int
    patient_id: Optional[int] = None
    link_type: str = "register"
    token: str
    status: str
    expires_at: datetime
    max_uses: int
    use_count: int
    last_used_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IntakeLinkPublicMeta(BaseModel):
    valid: bool
    link_type: Optional[str] = None
    expires_at: Optional[datetime] = None
    patient_first_name: Optional[str] = None
    patient_last_name: Optional[str] = None
    message: Optional[str] = None


class IntakePublicSubmit(BaseModel):
    first_name: str
    last_name: str
    birth_date: date
    sex: str
    whatsapp: Optional[str] = None
    email: Optional[EmailStr] = None  # Not required
    country: str
    city: str
    objective: Optional[str] = None
    disliked_foods: Optional[str] = None
    weight_kg: Optional[float] = None
    height_cm: Optional[float] = None
    food_allergies: Optional[str] = None
    activity_level: Optional[str] = None


class IntakeUpdateSubmit(BaseModel):
    """Optional fields for updating an existing patient via link.
    No email (used for contact/notifications — not changed here).
    No height or clinical data (only the doctor modifies those)."""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    whatsapp: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    weight_kg: Optional[float] = None


class DietGenerateRequest(BaseModel):
    patient_id: int
    doctor_instruction: Optional[str] = None
    duration_days: int = 7
    meals_per_day: Literal[2, 3, 4, 5] = 4
    strategy_mode: Literal["auto", "guided", "manual"] = "auto"
    diet_style: Optional[
        Literal[
            "balanced",
            "low_carb",
            "high_carb",
            "high_protein",
            "mediterranean",
        ]
    ] = None
    macro_mode: Optional["MacroModeRequest"] = None
    manual_targets: Optional["ManualTargetsRequest"] = None

    @field_validator("duration_days")
    @classmethod
    def validate_duration_days(cls, v: int) -> int:
        from app.logic.diet_duration import validate_duration_days as vd

        return vd(v)


class DietRegenerateRequest(BaseModel):
    doctor_instruction: Optional[str] = None
    duration_days: Optional[int] = None
    meals_per_day: Optional[Literal[2, 3, 4, 5]] = None
    strategy_mode: Literal["auto", "guided", "manual"] = "auto"
    diet_style: Optional[
        Literal[
            "balanced",
            "low_carb",
            "high_carb",
            "high_protein",
            "mediterranean",
        ]
    ] = None
    macro_mode: Optional["MacroModeRequest"] = None
    manual_targets: Optional["ManualTargetsRequest"] = None

    @field_validator("duration_days")
    @classmethod
    def validate_duration_opt(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return None
        from app.logic.diet_duration import validate_duration_days as vd

        return vd(v)


class DietOut(BaseModel):
    id: int
    patient_id: int
    doctor_id: int
    status: str
    title: Optional[str] = None
    summary: Optional[str] = None
    structured_plan_json: Any
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PlanDurationPresetsOut(BaseModel):
    days: list[int]


class DietVersionSummary(BaseModel):
    id: int
    diet_id: int
    version_number: int
    doctor_instruction: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedDiets(BaseModel):
    items: list[DietOut]
    total: int
    page: int
    page_size: int


class MacroModeRequest(BaseModel):
    protein: Optional[Literal["low", "normal", "high"]] = None
    carbs: Optional[Literal["low", "normal", "high"]] = None
    fat: Optional[Literal["low", "normal", "high"]] = None


class ManualTargetsRequest(BaseModel):
    daily_calories: Optional[float] = Field(None, gt=0)
    protein_g: Optional[float] = Field(None, gt=0)
    carbs_g: Optional[float] = Field(None, gt=0)
    fat_g: Optional[float] = Field(None, gt=0)


# --- Diet approval / discard / quick-adjust / meal edit schemas ---

class DietQuickAdjustRequest(BaseModel):
    adjustment: str = Field(..., min_length=1, max_length=200)


class DietMealUpdate(BaseModel):
    day_index: int = Field(..., ge=0, le=55)
    slot_key: str = Field(..., min_length=1, max_length=40)
    meal_text: str = Field(..., min_length=1, max_length=3500)


class DietMealsUpdateRequest(BaseModel):
    meals: list[DietMealUpdate] = Field(..., min_length=1, max_length=56)
