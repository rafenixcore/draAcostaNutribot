import base64
import logging
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import Diet, DietReminder, Patient, PatientIntakeLink
from app.services.email_service import send_email_sync

logger = logging.getLogger(__name__)

_LOGO_B64: str | None = None


def _get_logo_b64() -> str:
    global _LOGO_B64
    if _LOGO_B64 is None:
        logo_path = (
            Path(__file__).resolve().parent.parent.parent.parent
            / "frontend" / "public" / "logo-doctora.jpeg"
        )
        if logo_path.exists():
            _LOGO_B64 = base64.b64encode(logo_path.read_bytes()).decode()
        else:
            _LOGO_B64 = ""
    return _LOGO_B64


def utcnow():
    return datetime.now(timezone.utc)


def load_email_template(patient_name: str, link_url: str) -> str:
    logo_src = _get_logo_b64()
    logo_html = f"""<img src="data:image/jpeg;base64,{logo_src}" alt="Dra. Acosta"
           style="height:80px;width:auto;margin-bottom:12px;border-radius:12px;" />""" if logo_src else ""
    return f"""<!DOCTYPE html>
<html><body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;background:#f8fafc;">
  <div style="background:#fff;border-radius:16px;padding:32px;box-shadow:0 1px 3px rgba(0,0,0,0.08);">
    <div style="text-align:center;margin-bottom:24px;">
      {logo_html}
      <h1 style="color:#065f46;font-size:22px;margin:0 0 4px 0;">Dra. Acosta</h1>
      <p style="color:#64748b;font-size:14px;margin:0;">Plan Nutricional Personalizado</p>
    </div>
    <h2 style="color:#0f172a;font-size:18px;">¡Hola {patient_name}!</h2>
    <p style="color:#475569;font-size:14px;line-height:1.6;">
      Ha pasado un mes desde que recibiste tu plan nutricional. Cuéntanos cómo vas,
      ingresa tu peso actual y, si ya no resides donde antes, aprovecha para
      actualizar tu ubicación.
    </p>
    <div style="text-align:center;margin:28px 0;">
      <a href="{link_url}" style="background:#10b981;color:#fff;text-decoration:none;padding:14px 32px;border-radius:999px;font-size:15px;font-weight:600;display:inline-block;">
        Actualizar mis datos
      </a>
    </div>
    <p style="color:#94a3b8;font-size:12px;text-align:center;margin:0;">
      Este link expira en 7 días. Si ya actualizaste tus datos, ignora este mensaje.
    </p>
    <hr style="border:none;border-top:1px solid #e2e8f0;margin:24px 0;" />
    <p style="color:#94a3b8;font-size:11px;text-align:center;margin:0;">
      Dra. Acosta · Nutrición Personalizada · Este es un mensaje automático
    </p>
  </div>
</body></html>"""


async def check_and_send_reminders(db: AsyncSession) -> int:
    """Sends reminders for diets older than N days. Returns count sent."""
    threshold = utcnow() - timedelta(days=settings.REMINDER_DAYS)

    q = (
        select(Diet, Patient)
        .join(Patient, Diet.patient_id == Patient.id)
        .outerjoin(DietReminder, DietReminder.diet_id == Diet.id)
        .where(
            Diet.created_at <= threshold,
            Diet.status.in_(["generated", "approved"]),
            Diet.deleted_at.is_(None),
            Patient.email.isnot(None),
            DietReminder.id.is_(None),
        )
    )
    rows = (await db.execute(q)).all()

    sent = 0
    for diet, patient in rows:
        token = secrets.token_urlsafe(32)
        expires = utcnow() + timedelta(days=7)
        link = PatientIntakeLink(
            doctor_id=diet.doctor_id,
            patient_id=patient.id,
            link_type="update",
            token=token,
            expires_at=expires,
            max_uses=1,
        )
        db.add(link)
        await db.flush()

        link_url = f"{settings.APP_URL}/intake/{token}" if settings.APP_URL else f"/intake/{token}"
        html = load_email_template(patient.first_name, link_url)
        ok = send_email_sync(
            patient.email,
            "Actualiza tus datos — Dra. Acosta",
            html,
        )

        if ok:
            db.add(DietReminder(
                diet_id=diet.id,
                patient_id=patient.id,
                intake_link_id=link.id,
                sent_to_email=patient.email,
            ))
            sent += 1
            logger.info("Recordatorio enviado a %s (dieta %d)", patient.email, diet.id)
        else:
            logger.warning("Fallo envío a %s (dieta %d)", patient.email, diet.id)

    if sent > 0:
        await db.commit()
    else:
        await db.rollback()
    return sent
