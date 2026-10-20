import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_doctor
from app.core.database import get_db
from app.models import (
    AuditLog,
    Doctor,
    Patient,
    PatientIntakeLink,
    PatientMetrics,
    PatientProfile,
    utcnow,
)
from app.schemas import (
    IntakeLinkCreate,
    IntakeLinkOut,
    IntakeLinkPublicMeta,
    IntakePublicSubmit,
    IntakeUpdateSubmit,
)

router = APIRouter()


@router.get("", response_model=list[IntakeLinkOut])
async def list_links(
    db: AsyncSession = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    result = await db.execute(
        select(PatientIntakeLink)
        .where(PatientIntakeLink.doctor_id == doctor.id)
        .order_by(PatientIntakeLink.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("", response_model=IntakeLinkOut, status_code=status.HTTP_201_CREATED)
async def create_link(
    body: IntakeLinkCreate,
    db: AsyncSession = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    if body.link_type == "update":
        if body.patient_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="patient_id is required for update links",
            )
        patient = await db.get(Patient, body.patient_id)
        if patient is None or patient.doctor_id != doctor.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient not found",
            )

    token = secrets.token_urlsafe(32)
    expires_at = utcnow() + timedelta(days=body.expires_in_days)
    link = PatientIntakeLink(
        doctor_id=doctor.id,
        patient_id=body.patient_id,
        link_type=body.link_type,
        token=token,
        expires_at=expires_at,
        max_uses=body.max_uses,
    )
    db.add(link)
    await db.commit()
    await db.refresh(link)
    return link


@router.post("/{link_id}/revoke", response_model=IntakeLinkOut)
async def revoke_link(
    link_id: int,
    db: AsyncSession = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    result = await db.execute(
        select(PatientIntakeLink).where(
            PatientIntakeLink.id == link_id,
            PatientIntakeLink.doctor_id == doctor.id,
        )
    )
    link = result.scalar_one_or_none()
    if link is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link not found",
        )
    link.status = "revoked"
    link.updated_at = utcnow()
    await db.commit()
    await db.refresh(link)
    return link


@router.get("/public/{token}", response_model=IntakeLinkPublicMeta)
async def public_validate(token: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PatientIntakeLink).where(PatientIntakeLink.token == token)
    )
    link = result.scalar_one_or_none()
    if link is None:
        return IntakeLinkPublicMeta(valid=False, message="Enlace inválido")
    now = utcnow()
    if link.status == "revoked":
        return IntakeLinkPublicMeta(valid=False, message="Enlace revocado")
    if link.expires_at < now:
        return IntakeLinkPublicMeta(
            valid=False,
            expires_at=link.expires_at,
            message="Enlace expirado",
        )
    if link.use_count >= link.max_uses:
        return IntakeLinkPublicMeta(valid=False, message="Enlace ya utilizado")
    patient = await db.get(Patient, link.patient_id) if link.patient_id else None
    return IntakeLinkPublicMeta(
        valid=True,
        link_type=link.link_type,
        expires_at=link.expires_at,
        patient_first_name=patient.first_name if patient else None,
        patient_last_name=patient.last_name if patient else None,
    )


@router.post("/public/{token}/submit", status_code=status.HTTP_200_OK)
async def public_submit(
    token: str,
    body: IntakePublicSubmit,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PatientIntakeLink).where(PatientIntakeLink.token == token)
    )
    link = result.scalar_one_or_none()
    if link is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Enlace inválido",
        )
    now = utcnow()
    if link.status == "revoked":
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Enlace revocado")
    if link.expires_at < now:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Enlace expirado")
    if link.use_count >= link.max_uses:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Enlace ya utilizado")

    if link.link_type == "register" and link.patient_id is None:
        # Create new patient for registration flow
        patient = Patient(
            doctor_id=link.doctor_id,
            first_name=body.first_name,
            last_name=body.last_name,
            birth_date=body.birth_date,
            sex=body.sex,
            whatsapp=body.whatsapp,
            email=str(body.email) if body.email else None,
            country=body.country,
            city=body.city,
            source="intake_link",
        )
        db.add(patient)
        await db.flush()
        link.patient_id = patient.id
    else:
        patient = await db.get(Patient, link.patient_id)
        if patient is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient not found",
            )

    patient.first_name = body.first_name
    patient.last_name = body.last_name
    patient.birth_date = body.birth_date
    patient.sex = body.sex
    patient.whatsapp = body.whatsapp
    patient.email = str(body.email) if body.email else None
    patient.country = body.country
    patient.city = body.city
    patient.source = "intake_link"
    patient.updated_at = utcnow()

    # Partial profile — only what the patient can fill
    prof_result = await db.execute(
        select(PatientProfile).where(PatientProfile.patient_id == patient.id)
    )
    profile = prof_result.scalar_one_or_none()
    if profile is None:
        profile = PatientProfile(patient_id=patient.id)
        db.add(profile)

    if body.objective:
        profile.objective = body.objective
    if body.disliked_foods:
        profile.foods_avoided = body.disliked_foods
    if body.food_allergies:
        profile.food_allergies = body.food_allergies
    if body.activity_level:
        profile.activity_level = body.activity_level
    profile.completed_by_patient = True
    profile.updated_at = utcnow()

    # Crear PatientMetrics si el paciente proporcionó peso/altura
    if body.weight_kg is not None or body.height_cm is not None:
        metric = PatientMetrics(
            patient_id=patient.id,
            weight_kg=body.weight_kg,
            height_cm=body.height_cm,
            source="intake",
        )
        db.add(metric)

    link.use_count += 1
    link.last_used_at = utcnow()
    link.updated_at = utcnow()
    if link.use_count >= link.max_uses:
        link.status = "completed"

    db.add(
        AuditLog(
            doctor_id=link.doctor_id,
            action="intake_submit",
            entity_type="patient",
            entity_id=patient.id,
            payload_json={"intake_link_id": link.id},
        )
    )
    await db.commit()
    return {"ok": True}


@router.put("/public/{token}/update", status_code=status.HTTP_200_OK)
async def public_update(
    token: str,
    body: IntakeUpdateSubmit,
    db: AsyncSession = Depends(get_db),
):
    """Update an existing patient's data via an update link."""
    result = await db.execute(
        select(PatientIntakeLink).where(PatientIntakeLink.token == token)
    )
    link = result.scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enlace inválido")
    now = utcnow()
    if link.status == "revoked":
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Enlace revocado")
    if link.expires_at < now:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Enlace expirado")
    if link.use_count >= link.max_uses:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Enlace ya utilizado")
    if link.patient_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este enlace es para registro de nuevos pacientes, usa POST /submit",
        )

    patient = await db.get(Patient, link.patient_id)
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

    # Update patient base fields only if provided (only personal info)
    patient_fields = [
        "first_name", "last_name", "whatsapp",
        "country", "city",
    ]
    for field_name in patient_fields:
        value = getattr(body, field_name, None)
        if value is not None:
            setattr(patient, field_name, value)
    patient.updated_at = utcnow()

    # NOTE: Profile fields (clinical data) are NOT updated here — only doctor can modify them

    # Add metric entry only if weight provided
    metric_fields = ["weight_kg"]
    has_metric = any(getattr(body, f, None) is not None for f in metric_fields)
    if has_metric:
        metric = PatientMetrics(
            patient_id=patient.id,
            recorded_at=utcnow(),
            source="intake_update",
        )
        for field_name in metric_fields:
            value = getattr(body, field_name, None)
            if value is not None:
                setattr(metric, field_name, value)
        db.add(metric)

    link.use_count += 1
    link.last_used_at = utcnow()
    link.updated_at = utcnow()
    if link.use_count >= link.max_uses:
        link.status = "completed"

    db.add(
        AuditLog(
            doctor_id=link.doctor_id,
            action="intake_update",
            entity_type="patient",
            entity_id=patient.id,
            payload_json={"intake_link_id": link.id},
        )
    )
    await db.commit()
    return {"ok": True}
