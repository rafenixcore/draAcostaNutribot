import base64
import logging
from pathlib import Path

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


def _base_html(content_html: str) -> str:
    logo_src = _get_logo_b64()
    logo_tag = (
        f'<img src="data:image/jpeg;base64,{logo_src}" alt="Dra. Acosta" '
        f'style="height:80px;width:auto;margin-bottom:12px;border-radius:12px;" />'
    ) if logo_src else ""
    return f"""<!DOCTYPE html>
<html><body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;background:#f8fafc;">
  <div style="background:#fff;border-radius:16px;padding:32px;box-shadow:0 1px 3px rgba(0,0,0,0.08);">
    <div style="text-align:center;margin-bottom:24px;">
      {logo_tag}
      <h1 style="color:#065f46;font-size:22px;margin:0 0 4px 0;">Dra. Acosta</h1>
      <p style="color:#64748b;font-size:14px;margin:0;">Plan Nutricional Personalizado</p>
    </div>
    {content_html}
    <hr style="border:none;border-top:1px solid #e2e8f0;margin:24px 0;" />
    <p style="color:#94a3b8;font-size:11px;text-align:center;margin:0;">
      Dra. Acosta · Nutrición Personalizada · Este es un mensaje automático
    </p>
  </div>
</body></html>"""


def send_password_reset_email(to_email: str, full_name: str, reset_link: str) -> bool:
    content = f"""
    <h2 style="color:#0f172a;font-size:18px;">Hola {full_name},</h2>
    <p style="color:#475569;font-size:14px;line-height:1.6;">
      Recibimos una solicitud para restablecer la contraseña de tu cuenta en <b>Diet Agent</b>.
    </p>
    <div style="text-align:center;margin:28px 0;">
      <a href="{reset_link}" style="background:#10b981;color:#fff;text-decoration:none;padding:14px 32px;border-radius:999px;font-size:15px;font-weight:600;display:inline-block;">
        Restablecer Contraseña
      </a>
    </div>
    <p style="color:#94a3b8;font-size:12px;text-align:center;margin:0;">
      Este enlace expira en <b>30 minutos</b>. Si no solicitaste este cambio, ignora este mensaje.
    </p>
    <p style="color:#94a3b8;font-size:11px;text-align:center;margin-top:16px;">
      Si el botón no funciona, copia este enlace en tu navegador:<br>
      <span style="color:#3b82f6;">{reset_link}</span>
    </p>
    """
    html = _base_html(content)
    return send_email_sync(to_email, "Recuperación de Contraseña — Dra. Acosta", html)


def send_welcome_email(to_email: str, full_name: str, temp_password: str, login_link: str) -> bool:
    content = f"""
    <h2 style="color:#0f172a;font-size:18px;">¡Bienvenido(a) a Diet Agent, {full_name}!</h2>
    <p style="color:#475569;font-size:14px;line-height:1.6;">
      Se ha creado una cuenta para ti en el sistema de gestión nutricional.
    </p>
    <p style="color:#475569;font-size:14px;line-height:1.8;">
      <b>Email:</b> {to_email}<br>
      <b>Contraseña temporal:</b>
      <code style="background:#fefce8;padding:4px 8px;border-radius:4px;font-size:14px;">{temp_password}</code>
    </p>
    <p style="color:#ef4444;font-size:13px;">
      ⚠️ Al iniciar sesión por primera vez, deberás cambiar esta contraseña.
    </p>
    <div style="text-align:center;margin:28px 0;">
      <a href="{login_link}" style="background:#10b981;color:#fff;text-decoration:none;padding:14px 32px;border-radius:999px;font-size:15px;font-weight:600;display:inline-block;">
        Iniciar Sesión
      </a>
    </div>
    """
    html = _base_html(content)
    return send_email_sync(to_email, "Bienvenido a Nutrisoft — Dra. Acosta", html)
