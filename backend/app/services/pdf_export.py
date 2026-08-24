# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
"""Экспорт медицинской карты в PDF (кириллица через DejaVu Sans)."""
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

from fpdf import FPDF
from fpdf.fonts import FontFace

from app.services import i18n

FONT_PATH = Path(__file__).resolve().parents[2] / "fonts" / "DejaVuSans.ttf"
FONT_BOLD_PATH = Path(__file__).resolve().parents[2] / "fonts" / "DejaVuSans-Bold.ttf"


def _fmt_value(marker: dict[str, Any]) -> str:
    raw = marker.get("value_raw")
    if raw:
        return raw
    value = marker.get("value")
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def export_card_pdf(records: list[dict[str, Any]]) -> bytes:
    status_labels = {
        "normal": i18n.t("pdf.status.normal"),
        "elevated": i18n.t("pdf.status.elevated"),
        "low": i18n.t("pdf.status.low"),
        "unknown": "",
    }
    pdf = FPDF(format="A4")
    pdf.set_margins(14, 14, 14)
    pdf.add_page()
    pdf.add_font("DejaVu", "", FONT_PATH)
    pdf.add_font("DejaVu", "B", FONT_BOLD_PATH)

    pdf.set_font("DejaVu", "", 17)
    pdf.cell(0, 10, i18n.t("pdf.card_title"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("DejaVu", "", 9)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(
        0, 6,
        i18n.t("pdf.generated", dt=datetime.now().strftime("%d.%m.%Y %H:%M"), n=len(records)),
        new_x="LMARGIN", new_y="NEXT",
    )
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("DejaVu", "", 8)
    pdf.multi_cell(0, 4, i18n.t("pdf.disclaimer"))
    pdf.ln(3)

    for idx, rec in enumerate(records, start=1):
        pdf.set_font("DejaVu", "", 12)
        pdf.set_fill_color(235, 241, 250)
        title = i18n.t("pdf.record", idx=idx, source=rec["source_name"], date=rec["created_at"])
        pdf.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT", fill=True)
        pdf.ln(1)

        summary = (rec.get("summary") or "").strip()
        if summary:
            pdf.set_font("DejaVu", "", 9)
            pdf.multi_cell(0, 4.5, i18n.t("pdf.summary", summary=summary))
            pdf.ln(1)

        markers = rec.get("markers") or []
        if not markers:
            pdf.set_font("DejaVu", "", 9)
            pdf.set_text_color(120, 120, 120)
            pdf.cell(0, 5, i18n.t("pdf.no_markers"), new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(0, 0, 0)
            pdf.ln(3)
            continue

        with pdf.table(
            col_widths=(62, 24, 18, 50, 26),
            text_align="LEFT",
            padding=1,
            line_height=5,
        ) as table:
            header = table.row()
            for text in (
                i18n.t("pdf.h_col_name"),
                i18n.t("pdf.h_col_value"),
                i18n.t("pdf.h_col_unit"),
                i18n.t("pdf.h_col_ref"),
                i18n.t("pdf.h_col_status"),
            ):
                header.cell(text)

            for m in markers:
                row = table.row()
                row.cell(m.get("name") or "—")
                row.cell(_fmt_value(m))
                row.cell(m.get("unit") or "")
                row.cell(m.get("reference_range") or "—")
                status = m.get("status") or "unknown"
                status_text = status_labels.get(status, "")
                face = None
                if status == "normal":
                    face = FontFace(fill_color=(210, 235, 210))
                elif status in ("elevated", "low"):
                    face = FontFace(fill_color=(245, 220, 210))
                row.cell(status_text, style=face)
        pdf.ln(4)

    buf = BytesIO()
    pdf.output(buf)
    return buf.getvalue()


def export_notes_pdf(notes: list[dict[str, Any]]) -> bytes:
    pdf = FPDF(format="A4")
    pdf.set_margins(14, 14, 14)
    pdf.add_page()
    pdf.add_font("DejaVu", "", FONT_PATH)
    pdf.add_font("DejaVu", "B", FONT_BOLD_PATH)

    pdf.set_font("DejaVu", "", 17)
    pdf.cell(0, 10, i18n.t("pdf.notes_title"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("DejaVu", "", 9)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(
        0, 6,
        i18n.t("pdf.generated_notes", dt=datetime.now().strftime("%d.%m.%Y %H:%M"), n=len(notes)),
        new_x="LMARGIN", new_y="NEXT",
    )
    pdf.set_text_color(0, 0, 0)
    pdf.ln(3)

    for idx, note in enumerate(notes, start=1):
        pdf.set_font("DejaVu", "", 12)
        pdf.set_fill_color(250, 246, 230)
        title = i18n.t("pdf.note", idx=idx)
        if note.get("filename"):
            title += f" — {note['filename']}"
        title += f" — {note.get('created_at', '')}"
        pdf.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT", fill=True)
        pdf.ln(1)
        pdf.set_font("DejaVu", "", 9)
        pdf.multi_cell(0, 4.5, note.get("content") or "")
        pdf.ln(4)

    buf = BytesIO()
    pdf.output(buf)
    return buf.getvalue()
