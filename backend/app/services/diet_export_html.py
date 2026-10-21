from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import date
from html import escape
from io import BytesIO
from pathlib import Path
from typing import Any, Optional

from pypdf import PdfReader

from app.models import Diet, Patient
from app.services.doctor_assistant_service import calc_age
from app.services.plan_meals import (
    extract_day_meals,
    normalize_plan_meal_metadata,
    resolve_plan_meal_slots,
)

ROOT = Path(__file__).resolve().parents[2]
LOGO_PATH = ROOT / "assets" / "logo_nitido.png"
PDF_TMP_ROOT = ROOT / ".tmp_pdf"


class HtmlPdfExportError(RuntimeError):
    """Raised when the official HTML PDF renderer cannot produce a PDF."""


@dataclass(frozen=True)
class LayoutProfile:
    content_scale: float
    cell_font: float
    cell_line_height: float
    cell_padding_y: float
    cell_padding_x: float
    header_font: float
    header_padding: float
    logo_width: float
    title_font: float
    energy_font: float
    note_font: float
    note_padding_y: float
    note_padding_x: float
    note_margin_top: float
    brand_gap: float
    brand_margin_bottom: float


LAYOUT_PROFILES: tuple[LayoutProfile, ...] = (
    # content_scale, cell_font, cell_line_h, cell_pad_y, cell_pad_x, header_font, header_pad, logo_w, title_font, energy_font, note_font, note_pad_y, note_pad_x, note_margin_top, brand_gap, brand_margin_bot
    # Profile 0: máximo — casi toda la hoja
    LayoutProfile(0.94, 17.0, 1.48, 18.0, 16.0, 21.0, 10.0, 150.0, 25.0, 17.0, 17.0, 14.0, 20.0, 8.0, 26.0, 5.0),
    # Profile 1
    LayoutProfile(0.90, 16.0, 1.45, 16.0, 15.0, 19.5, 9.0, 144.0, 23.5, 16.0, 16.0, 12.5, 18.0, 7.0, 22.0, 4.0),
    # Profile 2
    LayoutProfile(0.86, 15.0, 1.42, 14.0, 14.0, 18.0, 8.0, 136.0, 22.0, 15.0, 15.0, 11.0, 16.0, 6.0, 18.0, 3.0),
    # Profile 3
    LayoutProfile(0.81, 14.0, 1.38, 12.0, 13.0, 16.5, 7.0, 126.0, 20.5, 14.0, 14.0, 9.5, 14.0, 5.0, 14.0, 2.0),
    # Profile 4
    LayoutProfile(0.75, 13.0, 1.32, 9.0, 12.0, 15.0, 6.0, 114.0, 18.5, 12.5, 12.5, 7.5, 11.0, 4.0, 10.0, 0.0),
)


def _num(v: Any) -> Optional[str]:
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    return str(int(f)) if f == int(f) else str(round(f, 1))


def _patient_name(patient: Optional[Patient]) -> str:
    if not patient:
        return "Paciente"
    name = " ".join(
        part.strip()
        for part in [patient.first_name or "", patient.last_name or ""]
        if part and part.strip()
    )
    return name or "Paciente"


def _energy_line(patient: Optional[Patient], plan: dict[str, Any]) -> str:
    calories = _num(plan.get("daily_calories"))
    calories_text = f"{calories} kcal" if calories else "No disponible en este plan."
    parts = [f"Calorías diarias: {calories_text}"]

    macros = plan.get("macro_grams")
    if isinstance(macros, dict):
        protein = _num(macros.get("protein_g"))
        carbs = _num(macros.get("carbs_g"))
        fat = _num(macros.get("fat_g"))
        if protein and carbs and fat:
            parts.append(
                "Macronutrientes (referencia diaria): "
                f"proteínas {protein} g, carbohidratos {carbs} g, grasas {fat} g"
            )

    if patient and patient.birth_date is not None:
        age = calc_age(patient.birth_date)
        if age is not None:
            parts.append(f"Edad: {age} años")
    return " · ".join(parts)


def _recommendations(plan: dict[str, Any]) -> str:
    recs = plan.get("recommendations")
    if isinstance(recs, list):
        # Solo tomar las primeras 3 recomendaciones (agua, sueño, ejercicio)
        lines = [str(item).strip() for item in recs[:3] if str(item).strip()]
        if lines:
            text = " ".join(lines)
            # Truncar a 350 chars máximo
            if len(text) > 350:
                text = text[:350].rsplit(" ", 1)[0]
            return text
    if isinstance(recs, str) and recs.strip():
        text = recs.strip()[:350]
        return text
    return (
        "Hidratación: beber agua constante durante el día según peso y actividad. "
        "Actividad física: ejercicio regular adaptado a objetivo. "
        "Descanso: dormir 7-8 horas diarias."
    )


def _column_widths(slots: list[str]) -> dict[str, str]:
    by_count = {
        2: {"breakfast": "48.1%", "dinner": "48.1%"},
        3: {"breakfast": "30.7%", "lunch": "32.5%", "dinner": "32.0%"},
        4: {
            "breakfast": "27.6%",
            "lunch": "27.8%",
            "snack": "14.4%",
            "dinner": "26.4%",
        },
        5: {
            "breakfast": "21.2%",
            "mid_morning_snack": "15.0%",
            "lunch": "24.0%",
            "snack": "14.0%",
            "dinner": "22.0%",
        },
    }
    return by_count.get(len(slots), {})


def render_official_diet_export_html(
    diet: Diet,
    *,
    patient: Optional[Patient] = None,
    layout: LayoutProfile = LAYOUT_PROFILES[0],
) -> str:
    plan_raw: Any = diet.structured_plan_json or {}
    plan: dict[str, Any] = plan_raw if isinstance(plan_raw, dict) else {}
    plan = normalize_plan_meal_metadata(plan)
    slots = resolve_plan_meal_slots(plan)
    days = [day for day in plan.get("days", []) if isinstance(day, dict)][:7]
    while len(days) < 7:
        days.append({"day": len(days) + 1, "meals": {}})

    widths = _column_widths(slots)
    name = _patient_name(patient)
    title = f"Plan Nutricional: {name}"
    fecha = (
        diet.created_at.strftime("%d/%m/%Y")
        if diet.created_at
        else date.today().strftime("%d/%m/%Y")
    )
    logo_src = LOGO_PATH.resolve().as_uri() if LOGO_PATH.exists() else ""

    colgroup = ['<col class="day">']
    for slot in slots:
        width = widths.get(slot)
        style = f' style="width: {width}"' if width else ""
        colgroup.append(f"<col{style}>")

    headers = ["<th>Día</th>"]
    for _, label, _ in extract_day_meals({"meals": {}}, slots):
        headers.append(f"<th>{escape(label)}</th>")

    rows: list[str] = []
    for idx, day in enumerate(days, start=1):
        cells = [f'<td class="day-cell">{escape(str(day.get("day") or idx))}</td>']
        for _, _, meal in extract_day_meals(day, slots):
            cells.append(f"<td>{escape(meal or '—')}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")

    logo = (
        f'<img class="brand-logo" src="{escape(logo_src)}" alt="Logo Dra. Acosta Fit">'
        if logo_src
        else ""
    )
    energy = escape(_energy_line(patient, plan))
    note = escape(_recommendations(plan))

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{escape(title)}</title>
  <style>
    :root {{
      --page-width: 1123px;
      --page-min-height: 794px;
      --content-scale: {layout.content_scale};
      --header-purple: #b09fcb;
      --row-purple: #d9d4e5;
      --border: #d1ccd8;
      --note-bg: #eef0fa;
      --note-accent: #7d91c1;
      --note-title: #50628e;
      --text: #181818;
    }}

    * {{ box-sizing: border-box; }}
    @page {{ size: A4 landscape; margin: 0; }}

    html, body {{
      margin: 0;
      padding: 0;
      background: #ffffff;
      color: var(--text);
      font-family: Arial, Helvetica, sans-serif;
      -webkit-print-color-adjust: exact;
      print-color-adjust: exact;
    }}

    body {{ display: flex; justify-content: center; }}

    .page {{
      width: 100%;
      max-width: var(--page-width);
      min-height: var(--page-min-height);
      padding: 8px 12px 5px;
      overflow: visible;
    }}

    .page-inner {{
      width: calc(100% / var(--content-scale));
      transform: scale(var(--content-scale));
      transform-origin: top left;
    }}

    .top-meta {{
      display: flex;
      justify-content: flex-end;
      align-items: center;
      margin-bottom: 3px;
      padding-right: 14px;
      font-size: 15px;
      font-weight: 700;
      color: #111111;
    }}

    .brand {{
      display: flex;
      justify-content: center;
      align-items: center;
      gap: {layout.brand_gap}px;
      margin: 2px 0 {layout.brand_margin_bottom}px;
    }}

    .brand-logo {{
      width: {layout.logo_width}px;
      height: auto;
      display: block;
      object-fit: contain;
      image-rendering: auto;
      filter: contrast(1.08) saturate(1.05);
    }}

    .brand-title {{
      margin: 0;
      font-size: {layout.title_font}px;
      font-weight: 700;
      color: #0b0b0b;
    }}

    .energy-line {{
      max-width: 920px;
      margin: 0 auto 10px;
      text-align: center;
      font-size: {layout.energy_font}px;
      line-height: 1.25;
      font-weight: 700;
      color: #111111;
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
    }}

    col.day {{ width: 3.8%; }}

    thead th {{
      padding: {layout.header_padding}px;
      border: 1px solid var(--border);
      background: var(--header-purple);
      color: #ffffff;
      font-size: {layout.header_font}px;
      font-weight: 700;
      text-align: center;
    }}

    tbody td {{
      padding: {layout.cell_padding_y}px {layout.cell_padding_x}px;
      border: 1px solid var(--border);
      font-size: {layout.cell_font}px;
      line-height: {layout.cell_line_height};
      vertical-align: top;
      text-align: justify;
      text-justify: inter-word;
      word-break: normal;
    }}

    tbody tr:nth-child(even) td {{ background: var(--row-purple); }}

    td.day-cell {{
      padding: 12px 8px;
      font-size: 13px;
      text-align: center;
      vertical-align: middle;
    }}

    .note {{
      margin-top: {layout.note_margin_top}px;
      border-left: 8px solid var(--note-accent);
      background: var(--note-bg);
      padding: {layout.note_padding_y}px {layout.note_padding_x}px;
      font-size: {layout.note_font}px;
      line-height: 1.28;
      color: #343434;
    }}

    .note strong {{ color: var(--note-title); }}
  </style>
</head>
<body>
  <main class="page">
    <div class="page-inner">
      <div class="top-meta">Fecha: {escape(fecha)}</div>
      <section class="brand" aria-label="Encabezado del plan nutricional">
        {logo}
        <h1 class="brand-title">{escape(title)}</h1>
      </section>
      <div class="energy-line">{energy}</div>
      <table aria-label="Plan nutricional semanal">
        <colgroup>{"".join(colgroup)}</colgroup>
        <thead><tr>{"".join(headers)}</tr></thead>
        <tbody>{"".join(rows)}</tbody>
      </table>
      <section class="note"><strong>Recomendaciones:</strong> {note}</section>
    </div>
  </main>
</body>
</html>
"""


def _browser_bin() -> Optional[str]:
    for candidate in ("google-chrome", "google-chrome-stable", "chromium-browser", "chromium"):
        found = shutil.which(candidate)
        if found:
            return found
    return None


def html_to_pdf_bytes(html: str) -> bytes:
    browser = _browser_bin()
    if not browser:
        raise HtmlPdfExportError("No HTML-to-PDF browser binary was found.")

    PDF_TMP_ROOT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="diet_pdf_", dir=PDF_TMP_ROOT) as tmp:
        tmp_path = Path(tmp)
        html_path = tmp_path / "plan.html"
        pdf_path = tmp_path / "plan.pdf"
        html_path.write_text(html, encoding="utf-8")
        cmd = [
            browser,
            "--headless",
            "--disable-gpu",
            "--no-sandbox",
            "--print-to-pdf-no-header",
            f"--print-to-pdf={pdf_path}",
            html_path.resolve().as_uri(),
        ]
        completed = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            timeout=30,
        )
        if completed.returncode != 0 or not pdf_path.exists():
            stderr = completed.stderr.decode("utf-8", errors="replace")[:500]
            raise HtmlPdfExportError(f"HTML PDF rendering failed: {stderr}")
        return pdf_path.read_bytes()


def _pdf_page_count(pdf: bytes) -> int:
    return len(PdfReader(BytesIO(pdf)).pages)


def build_official_diet_export_pdf_bytes(
    diet: Diet,
    *,
    patient: Optional[Patient] = None,
) -> bytes:
    last_pdf: bytes | None = None
    for layout in LAYOUT_PROFILES:
        pdf = html_to_pdf_bytes(
            render_official_diet_export_html(diet, patient=patient, layout=layout)
        )
        last_pdf = pdf
        if _pdf_page_count(pdf) == 1:
            return pdf
    if last_pdf is None:
        raise HtmlPdfExportError("No PDF was generated.")
    return last_pdf
