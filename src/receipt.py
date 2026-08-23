"""
Audit receipt builder — timestamped JSON + one-page PDF (reportlab).

Deterministic layout; embeds case metadata for scrutiny.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from .cases import ComplianceCase

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECEIPTS_DIR = ROOT / "receipts"

DISCLAIMER = (
    "Decision-support / education demo. Not legal advice. "
    "The product label controls. Fixtures are educational stubs unless replaced "
    "with a real label excerpt and Bulletins Live! Two printable."
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def build_receipt_payload(case: ComplianceCase) -> dict[str, Any]:
    plan = case.plan or {}
    points = plan.get("points") or {}
    weather = plan.get("weather") or {}
    layers = plan.get("layers") or {}

    return {
        "receipt_generated_at": _utc_now(),
        "disclaimer": DISCLAIMER,
        "case_id": case.case_id,
        "status": case.status,
        "created_at": case.created_at,
        "updated_at": case.updated_at,
        "planned_spray_date": case.planned_spray_date,
        "product": plan.get("product"),
        "field": plan.get("field"),
        "points": {
            "required_points": points.get("required_points"),
            "earned_points": points.get("earned_points"),
            "shortfall": points.get("shortfall"),
            "credited": points.get("credited"),
            "layer": points.get("layer", "deterministic"),
        },
        "recommended_additions": plan.get("recommended_additions"),
        "weather": weather,
        "bulletin_actions": plan.get("bulletin_actions"),
        "citations": plan.get("citations"),
        "honesty_split": {
            "deterministic": layers.get("deterministic", []),
            "model": layers.get("model", []),
        },
        "model": plan.get("model"),
        "confirmation": case.confirmation,
        "events": case.events,
        "reminder_events": [
            e for e in case.events if e.get("type") == "reminder_simulated"
        ],
    }


def write_receipt_json(case: ComplianceCase, out_dir: Path | None = None) -> Path:
    out_dir = out_dir or DEFAULT_RECEIPTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = build_receipt_payload(case)
    path = out_dir / f"{case.case_id}.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def write_receipt_pdf(case: ComplianceCase, out_dir: Path | None = None) -> Path:
    out_dir = out_dir or DEFAULT_RECEIPTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = build_receipt_payload(case)
    path = out_dir / f"{case.case_id}.pdf"

    doc = SimpleDocTemplate(
        str(path),
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
        title=f"AgriNexus Compliance Receipt {case.case_id}",
        author="AgriNexus Compliance Demo",
        subject="ESA label mitigation educational audit receipt",
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "ReceiptTitle",
        parent=styles["Heading1"],
        fontSize=14,
        spaceAfter=8,
    )
    h2 = ParagraphStyle(
        "ReceiptH2",
        parent=styles["Heading2"],
        fontSize=11,
        spaceBefore=10,
        spaceAfter=4,
    )
    body = ParagraphStyle(
        "ReceiptBody",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
    )
    small = ParagraphStyle(
        "ReceiptSmall",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
        textColor="#333333",
    )

    product = payload.get("product") or {}
    field = payload.get("field") or {}
    points = payload.get("points") or {}
    weather = payload.get("weather") or {}

    story: list[Any] = [
        Paragraph("AgriNexus Compliance — Audit Receipt", title),
        Paragraph(DISCLAIMER, small),
        Spacer(1, 6),
        Paragraph(f"<b>Case ID:</b> {case.case_id}", body),
        Paragraph(f"<b>Status:</b> {case.status}", body),
        Paragraph(f"<b>Generated (UTC):</b> {payload['receipt_generated_at']}", body),
        Paragraph(
            f"<b>Product:</b> {product.get('product_name')} "
            f"(EPA Reg. No. {product.get('epa_reg_no')})",
            body,
        ),
        Paragraph(
            f"<b>Field:</b> {field.get('field_id')} — "
            f"{field.get('county')}, {field.get('state')}",
            body,
        ),
        Paragraph(
            f"<b>Planned spray date:</b> {case.planned_spray_date or 'n/a'}",
            body,
        ),
        Paragraph("Points (deterministic)", h2),
        Paragraph(
            f"Required {points.get('required_points')} · "
            f"Earned {points.get('earned_points')} · "
            f"Shortfall {points.get('shortfall')}",
            body,
        ),
        Paragraph("Weather gate (deterministic)", h2),
        Paragraph(
            f"weather_ok={weather.get('weather_ok')} · "
            f"wind={weather.get('wind_mph')} mph · "
            f"source={weather.get('source')}",
            body,
        ),
    ]
    reasons = weather.get("weather_block_reasons") or []
    if reasons:
        story.append(Paragraph("Block reasons: " + "; ".join(reasons), body))

    story.append(Paragraph("Honesty split", h2))
    hs = payload.get("honesty_split") or {}
    story.append(
        Paragraph(
            f"<b>Deterministic:</b> {', '.join(hs.get('deterministic') or []) or '—'}",
            body,
        )
    )
    story.append(
        Paragraph(
            f"<b>Model:</b> {', '.join(hs.get('model') or []) or '(offline / none)'}",
            body,
        )
    )

    story.append(Paragraph("Case events (includes simulated reminders)", h2))
    if not payload.get("events"):
        story.append(Paragraph("No events recorded.", body))
    else:
        for ev in payload["events"]:
            story.append(
                Paragraph(
                    f"• [{ev.get('at')}] <b>{ev.get('type')}</b> — {ev.get('detail')}",
                    body,
                )
            )

    conf = payload.get("confirmation")
    story.append(Paragraph("Confirmation", h2))
    if conf:
        story.append(
            Paragraph(
                f"summary={conf.get('summary')} · "
                f"applied={conf.get('applied')} · "
                f"bulletin_saved={conf.get('bulletin_saved')} · "
                f"needs_human={conf.get('needs_human')} · "
                f"layer={conf.get('layer')}",
                body,
            )
        )
        if conf.get("raw_text"):
            raw = str(conf["raw_text"]).replace("&", "&amp;").replace("<", "&lt;")
            story.append(Paragraph(f"Raw reply: {raw}", small))
    else:
        story.append(Paragraph("No free-text confirmation yet.", body))

    cites = payload.get("citations") or []
    story.append(Paragraph("Fixture citations", h2))
    story.append(Paragraph(", ".join(cites) if cites else "—", small))

    doc.build(story)
    return path


def build_receipt_files(
    case: ComplianceCase, out_dir: Path | None = None
) -> dict[str, str]:
    json_path = write_receipt_json(case, out_dir=out_dir)
    pdf_path = write_receipt_pdf(case, out_dir=out_dir)
    return {"json": str(json_path), "pdf": str(pdf_path)}
