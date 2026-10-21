from typing import Optional

from app.logic.profile import norm
from app.models import Patient, PatientMetrics, PatientProfile


def diet_generation_blockers(
    patient: Patient,
    profile: Optional[PatientProfile],
    latest: Optional[PatientMetrics],
) -> list[str]:
    reasons: list[str] = []
    if patient.deleted_at:
        reasons.append("El paciente ha sido eliminado")
    if not patient.birth_date:
        reasons.append("Falta la fecha de nacimiento del paciente")
    if not patient.sex:
        reasons.append("Falta el sexo del paciente")
    if not patient.country or not patient.city:
        reasons.append("Falta el país o ciudad del paciente")
    if not profile:
        reasons.append("Falta completar el perfil clínico del paciente")
    else:
        if not profile.objective:
            reasons.append("Falta el objetivo del paciente en el perfil clínico")
        if not norm(profile.food_allergies):
            reasons.append("Faltan alergias alimentarias (escribe 'ninguna' si no aplica)")
        if not norm(profile.foods_avoided):
            reasons.append("Faltan alimentos a evitar (escribe 'ninguno' si no aplica)")
    if not latest or latest.weight_kg is None:
        reasons.append("Falta registrar el peso del paciente en métricas")
    if not latest or latest.height_cm is None:
        reasons.append("Falta registrar la altura del paciente en métricas")
    return reasons
