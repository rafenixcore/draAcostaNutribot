from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_doctor
from app.core.database import get_db
from app.logic.diet_duration import QUICK_PLAN_DURATION_DAYS
from app.models import Diet, DietVersion, Doctor, Patient, PatientMetrics, PatientProfile, utcnow
from app.schemas import (
    DietGenerateRequest,
    DietMealsUpdateRequest,
    DietOut,
    DietQuickAdjustRequest,
    DietRegenerateRequest,
    DietVersionSummary,
    PaginatedDiets,
    PlanDurationPresetsOut,
)
from app.services.diet_export import (
    build_diet_export_json_bytes,
    build_diet_export_pdf_bytes,
    build_diet_export_text,
)
from app.services.diet_service import (
    DietGenerationError,
    approve_diet_preview,
    create_new_diet,
    discard_diet_preview,
    regenerate_diet,
    update_diet_meals,
)
from app.services.email_service import send_email_with_attachment

router = APIRouter()


@router.get("/duration-presets", response_model=PlanDurationPresetsOut)
async def plan_duration_presets(_doctor: Doctor = Depends(get_current_doctor)):
    """Atajos de duración (días) alineados con Telegram; requiere sesión de doctor."""
    return PlanDurationPresetsOut(days=list(QUICK_PLAN_DURATION_DAYS))


def _http_from_diet_error(e: DietGenerationError) -> HTTPException:
    if e.code == "not_found":
        st = status.HTTP_404_NOT_FOUND
    elif e.code == "openai_config":
        st = status.HTTP_503_SERVICE_UNAVAILABLE
    elif e.code == "openai_error":
        st = status.HTTP_502_BAD_GATEWAY
    else:
        st = status.HTTP_400_BAD_REQUEST
    return HTTPException(
        status_code=st,
        detail={
            "code": e.code,
            "message": e.message,
            "reasons": e.reasons,
        },
    )


@router.get("", response_model=PaginatedDiets)
async def list_diets(
    db: AsyncSession = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
    patient_id: Optional[int] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    conditions = [Diet.doctor_id == doctor.id, Diet.deleted_at.is_(None)]
    if patient_id is not None:
        conditions.append(Diet.patient_id == patient_id)
    if status_filter:
        conditions.append(Diet.status == status_filter)

    count_stmt = select(func.count()).select_from(Diet).where(*conditions)
    total = (await db.execute(count_stmt)).scalar_one()
    stmt = (
        select(Diet)
        .where(*conditions)
        .order_by(Diet.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    items = result.scalars().all()
    return PaginatedDiets(
        items=[DietOut.model_validate(d) for d in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/generate", response_model=DietOut, status_code=status.HTTP_201_CREATED)
async def generate_diet(
    body: DietGenerateRequest,
    db: AsyncSession = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
    pending: bool = Query(False, description="Create as pending_approval instead of generated"),
):
    try:
        diet = await create_new_diet(
            db,
            doctor,
            body.patient_id,
            body.doctor_instruction,
            diet_status="pending_approval" if pending else "generated",
            duration_days=body.duration_days,
            meals_per_day=body.meals_per_day,
            strategy_mode=body.strategy_mode,
            diet_style=body.diet_style,
            macro_mode=body.macro_mode.model_dump(exclude_none=True)
            if body.macro_mode
            else None,
            manual_targets=body.manual_targets.model_dump(exclude_none=True)
            if body.manual_targets
            else None,
        )
        await db.commit()
        await db.refresh(diet)
        return diet
    except DietGenerationError as e:
        await db.rollback()
        raise _http_from_diet_error(e) from e


@router.get("/{diet_id}", response_model=DietOut)
async def get_diet(
    diet_id: int,
    db: AsyncSession = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    diet = await db.get(Diet, diet_id)
    if diet is None or diet.doctor_id != doctor.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dieta no encontrada")
    return diet


@router.get("/{diet_id}/versions", response_model=list[DietVersionSummary])
async def list_versions(
    diet_id: int,
    db: AsyncSession = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    diet = await db.get(Diet, diet_id)
    if diet is None or diet.doctor_id != doctor.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dieta no encontrada")
    result = await db.execute(
        select(DietVersion)
        .where(DietVersion.diet_id == diet_id)
        .order_by(DietVersion.version_number.asc())
    )
    rows = result.scalars().all()
    return [DietVersionSummary.model_validate(v) for v in rows]


@router.post("/{diet_id}/regenerate", response_model=DietOut)
async def regenerate_diet_route(
    diet_id: int,
    body: DietRegenerateRequest,
    db: AsyncSession = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    try:
        diet = await regenerate_diet(
            db,
            doctor,
            diet_id,
            body.doctor_instruction,
            duration_days=body.duration_days,
            meals_per_day=body.meals_per_day,
            strategy_mode=body.strategy_mode,
            diet_style=body.diet_style,
            macro_mode=body.macro_mode.model_dump(exclude_none=True)
            if body.macro_mode
            else None,
            manual_targets=body.manual_targets.model_dump(exclude_none=True)
            if body.manual_targets
            else None,
        )
        await db.commit()
        await db.refresh(diet)
        return diet
    except DietGenerationError as e:
        await db.rollback()
        raise _http_from_diet_error(e) from e


@router.post("/{diet_id}/approve", response_model=DietOut)
async def approve_diet(
    diet_id: int,
    db: AsyncSession = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    """Approve a pending diet, changing status from pending_approval to generated."""
    try:
        diet = await approve_diet_preview(db, doctor, diet_id)
        await db.commit()
        await db.refresh(diet)
        return diet
    except DietGenerationError as e:
        await db.rollback()
        raise _http_from_diet_error(e) from e


@router.post("/{diet_id}/discard", response_model=DietOut)
async def discard_diet(
    diet_id: int,
    db: AsyncSession = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    """Discard a pending diet, changing status from pending_approval to discarded."""
    try:
        diet = await discard_diet_preview(db, doctor, diet_id)
        await db.commit()
        await db.refresh(diet)
        return diet
    except DietGenerationError as e:
        await db.rollback()
        raise _http_from_diet_error(e) from e


@router.post("/{diet_id}/quick-adjust", response_model=DietOut)
async def quick_adjust_diet(
    diet_id: int,
    body: DietQuickAdjustRequest,
    db: AsyncSession = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    """Regenerate diet with a quick-adjust instruction, keeping it as pending_approval."""
    try:
        diet = await regenerate_diet(
            db,
            doctor,
            diet_id,
            body.adjustment,
            diet_status="pending_approval",
        )
        await db.commit()
        await db.refresh(diet)
        return diet
    except DietGenerationError as e:
        await db.rollback()
        raise _http_from_diet_error(e) from e


@router.patch("/{diet_id}/meals", response_model=DietOut)
async def edit_diet_meals(
    diet_id: int,
    body: DietMealsUpdateRequest,
    db: AsyncSession = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    """Edit specific meals in a pending-approval diet."""
    try:
        meals_dicts = [
            {"day_index": m.day_index, "slot_key": m.slot_key, "meal_text": m.meal_text}
            for m in body.meals
        ]
        diet = await update_diet_meals(db, doctor, diet_id, meals_dicts)
        await db.commit()
        await db.refresh(diet)
        return diet
    except DietGenerationError as e:
        await db.rollback()
        raise _http_from_diet_error(e) from e


@router.get("/{diet_id}/export")
async def export_diet(
    diet_id: int,
    db: AsyncSession = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
    export_format: Literal["txt", "json"] = Query("txt", alias="format"),
):
    diet = await db.get(Diet, diet_id)
    if diet is None or diet.doctor_id != doctor.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dieta no encontrada")
    if export_format == "json":
        body = build_diet_export_json_bytes(diet)
        return Response(
            content=body,
            media_type="application/json; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="diet_{diet_id}.json"'
            },
        )
    patient = await db.get(Patient, diet.patient_id)
    if patient is not None and patient.doctor_id != doctor.id:
        patient = None
    text = build_diet_export_text(diet, patient=patient)
    return Response(
        content=text.encode("utf-8"),
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="diet_{diet_id}.txt"'
        },
    )


@router.get("/{diet_id}/pdf")
async def get_diet_pdf(
    diet_id: int,
    db: AsyncSession = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    diet = await db.get(Diet, diet_id)
    if diet is None or diet.doctor_id != doctor.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dieta no encontrada")
    patient = await db.get(Patient, diet.patient_id)
    profile = None
    metrics = None
    if patient is not None and patient.doctor_id == doctor.id:
        pr = await db.execute(
            select(PatientProfile).where(PatientProfile.patient_id == patient.id)
        )
        profile = pr.scalar_one_or_none()
        mr = await db.execute(
            select(PatientMetrics)
            .where(PatientMetrics.patient_id == patient.id)
            .order_by(PatientMetrics.recorded_at.desc())
            .limit(1)
        )
        metrics = mr.scalar_one_or_none()
    pdf_bytes = build_diet_export_pdf_bytes(
        diet,
        patient=patient if patient and patient.doctor_id == doctor.id else None,
        profile=profile,
        metrics=metrics,
        doctor=doctor,
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="diet_{diet_id}.pdf"'
        },
    )


@router.post("/{diet_id}/email")
async def email_diet_pdf(
    diet_id: int,
    db: AsyncSession = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    """Send the diet PDF to the patient's registered email."""
    diet = await db.get(Diet, diet_id)
    if diet is None or diet.doctor_id != doctor.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dieta no encontrada",
        )

    patient = await db.get(Patient, diet.patient_id)
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PATIENT_NOT_FOUND",
        )
    if not patient.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PATIENT_NO_EMAIL",
        )

    # Fetch profile and latest metrics for PDF generation
    profile = None
    metrics = None
    if patient.doctor_id == doctor.id:
        pr = await db.execute(
            select(PatientProfile).where(PatientProfile.patient_id == patient.id)
        )
        profile = pr.scalar_one_or_none()
        mr = await db.execute(
            select(PatientMetrics)
            .where(PatientMetrics.patient_id == patient.id)
            .order_by(PatientMetrics.recorded_at.desc())
            .limit(1)
        )
        metrics = mr.scalar_one_or_none()

    # Generate PDF
    pdf_bytes = build_diet_export_pdf_bytes(
        diet,
        patient=patient,
        profile=profile,
        metrics=metrics,
        doctor=doctor,
    )

    # Build email
    patient_name = (patient.first_name or "Paciente").strip()
    subject = "Tu Plan Nutricional - Dra. Acosta"
    html_body = f"""<html><body style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:20px">
<h2 style="color:#1e3a5f">Hola {patient_name},</h2>
<p>La <strong>Dra. Acosta</strong> te comparte tu plan nutricional personalizado.</p>
<p>Adjunto encontrarás el PDF con tu dieta y recomendaciones.</p>
<p style="color:#666;font-size:13px;margin-top:30px;border-top:1px solid #eee;padding-top:15px">
Este correo fue enviado por el consultorio de la Dra. Acosta.<br/>
Si tienes dudas, responde a este correo o contacta por WhatsApp.
</p></body></html>"""

    success = send_email_with_attachment(
        to_email=patient.email,
        subject=subject,
        html_body=html_body,
        attachment_bytes=pdf_bytes,
        attachment_filename=f"Plan_Nutricional_{patient_name}.pdf",
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="EMAIL_SEND_FAILED",
        )

    return {"ok": True, "sent_to": patient.email}


@router.post("/{diet_id}/soft-delete")
async def soft_delete_diet(
    diet_id: int,
    db: AsyncSession = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    diet = await db.get(Diet, diet_id)
    if diet is None or diet.doctor_id != doctor.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dieta no encontrada")
    diet.deleted_at = utcnow()
    await db.commit()
    return {"ok": True}


@router.post("/{diet_id}/restore")
async def restore_diet(
    diet_id: int,
    db: AsyncSession = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    diet = await db.get(Diet, diet_id)
    if diet is None or diet.doctor_id != doctor.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dieta no encontrada")
    # Check if the associated patient is in the trash
    patient = await db.get(Patient, diet.patient_id)
    if patient and patient.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se puede restaurar la dieta porque el paciente está en la papelera. Restaure al paciente primero."
        )
    diet.deleted_at = None
    await db.commit()
    return {"ok": True}


@router.delete("/{diet_id}/hard-delete")
async def hard_delete_diet(
    diet_id: int,
    db: AsyncSession = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    diet = await db.get(Diet, diet_id)
    if diet is None or diet.doctor_id != doctor.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dieta no encontrada")
    await db.delete(diet)
    await db.commit()
    return {"ok": True}
