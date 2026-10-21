from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_doctor
from app.core.database import get_db
from app.models import Diet, Doctor, Patient

router = APIRouter(prefix="/trash", tags=["trash"])


@router.get("/patients")
async def list_trashed_patients(
    search: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    doctor: Doctor = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    query = select(Patient).where(
        Patient.doctor_id == doctor.id,
        Patient.deleted_at.isnot(None),
    )
    if search:
        query = query.where(
            Patient.first_name.ilike(f"%{search}%")
            | Patient.last_name.ilike(f"%{search}%"),
        )
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0
    rows = (
        await db.execute(
            query.order_by(Patient.deleted_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size),
        )
    ).scalars().all()
    return {
        "items": [
            {
                "id": p.id,
                "first_name": p.first_name,
                "last_name": p.last_name,
                "email": p.email,
                "deleted_at": p.deleted_at.isoformat() if p.deleted_at else None,
            }
            for p in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/diets")
async def list_trashed_diets(
    search: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    doctor: Doctor = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Diet, Patient.first_name, Patient.last_name)
        .join(Patient, Diet.patient_id == Patient.id)
        .where(
            Patient.doctor_id == doctor.id,
            Diet.deleted_at.isnot(None),
        )
    )
    if search:
        query = query.where(
            Patient.first_name.ilike(f"%{search}%")
            | Patient.last_name.ilike(f"%{search}%"),
        )
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0
    rows = (
        await db.execute(
            query.order_by(Diet.deleted_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size),
        )
    ).all()
    return {
        "items": [
            {
                "diet_id": d.id,
                "patient_id": d.patient_id,
                "patient_name": f"{fn} {ln}",
                "title": d.title,
                "deleted_at": d.deleted_at.isoformat() if d.deleted_at else None,
            }
            for d, fn, ln in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
