"""
Audit receipt builder — outcome, timeline, verification table, record hash.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.lib import colors

from .cases import ComplianceCase
from .clock import status as clock_status

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECEIPTS_DIR = ROOT / "receipts"

DISCLAIMER = (
    "Decision-support / education demo. Not legal advice. "
    "The product label controls. Verification compares the applicator reply to the "
    "plan this system issued — it is not legal clearance."
)


def _utc_now() -> str:
    from .clock import now_iso

    return now_iso()


def _parse_at(value: str | None) -> datetime | None:
    if not value:
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _elapsed_label(prev: datetime | None, cur: datetime | None) -> str:
    if not prev or not cur:
        return ""
    delta = cur - prev
    total_m = int(delta.total_seconds() // 60)
    h, m = divmod(abs(total_m), 60)
    sign = "+" if total_m >= 0 else "-"
    return f"{sign}{h} h {m} m"


def outcome_headline(case: ComplianceCase) -> tuple[str, str]:
    if case.status == "CLOSED":
        if case.outcome == "verified":
            return "Verified against plan", (case.verification or {}).get("summary") or ""
        if case.outcome == "unverified":
            return "Closed as unverified", (case.review or {}).get("note") or ""
        if case.outcome == "expired":
            return "Expired without reply", "No applicator reply by the deadline."
    if case.status == "VERIFIED":
        return "Verified against plan", (case.verification or {}).get("summary") or ""
    if case.status == "NEEDS_REVIEW":
        return "Needs partner review", (case.verification or {}).get("summary") or ""
    if case.status == "EXPIRED":
        return "Expired without reply", "No applicator reply by the deadline."
    return "Open", "Case still in progress."


def timeline_entries(case: ComplianceCase) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    prev: datetime | None = None
    for ev in case.events or []:
        at = _parse_at(ev.get("at"))
        outbound = ev.get("outbound_message") or (ev.get("data") or {}).get(
            "outbound_message"
        )
        data = ev.get("data") or {}
        label = ev.get("type")
        if ev.get("type") in {"reminder_sent", "reminder_simulated"}:
            by_partner = ev.get("actor") == "partner" or data.get("sent_by") == "partner"
            label = (
                "Reminder sent by partner"
                if by_partner
                else "Reminder sent on schedule"
            )
        rows.append(
            {
                "at": ev.get("at"),
                "type": ev.get("type"),
                "label": label,
                "actor": ev.get("actor"),
                "detail": ev.get("detail"),
                "elapsed_from_previous": _elapsed_label(prev, at),
                "outbound_message": outbound,
            }
        )
        if at:
            prev = at
    return rows


def build_receipt_payload(case: ComplianceCase) -> dict[str, Any]:
    plan = case.plan or {}
    points = plan.get("points") or {}
    weather = plan.get("weather") or {}
    layers = plan.get("layers") or {}
    headline, sub = outcome_headline(case)
    clk = clock_status()

    # Provenance from fixture JSON retrieval dates — load bulletin if cited
    provenance: list[dict[str, Any]] = []
    for cite in plan.get("citations") or []:
        entry: dict[str, Any] = {"path": cite}
        path = ROOT / cite if not Path(cite).is_absolute() else Path(cite)
        if path.suffix == ".json" and path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if "retrieved" in data:
                    entry["retrieved"] = data["retrieved"]
                if "date_printed" in data:
                    entry["date_printed"] = data["date_printed"]
                if "retrieved_approx" in data:
                    entry["retrieved"] = data["retrieved_approx"]
            except Exception:
                pass
        provenance.append(entry)

    payload: dict[str, Any] = {
        "receipt_generated_at": _utc_now(),
        "disclaimer": DISCLAIMER,
        "outcome_headline": headline,
        "outcome_summary": sub,
        "case_id": case.case_id,
        "status": case.status,
        "outcome": case.outcome,
        "applicator_name": case.applicator_name,
        "created_at": case.created_at,
        "updated_at": case.updated_at,
        "closed_at": case.closed_at,
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
        "weather": weather,
        "bulletin_actions": plan.get("bulletin_actions"),
        "bulletin_file": next(
            (c for c in (plan.get("citations") or []) if str(c).endswith(".pdf")),
            None,
        ),
        "confirmation": case.confirmation,
        "verification": case.verification,
        "review": case.review,
        "timeline": timeline_entries(case),
        "events": case.events,
        "reminder_events": [
            e
            for e in case.events
            if e.get("type") in {"reminder_simulated", "reminder_sent"}
        ],
        "honesty_split": {
            "deterministic": layers.get("deterministic", [])
            + ["verification rules", "scheduler"],
            "model": layers.get("model", [])
            + (
                ["confirmation interpretation"]
                if (case.confirmation or {}).get("layer") == "model"
                else []
            ),
        },
        "provenance": provenance,
        "citations": plan.get("citations"),
        "demo_clock": clk if clk.get("override_active") else None,
    }
    if case.receipt_sha256:
        payload["receipt_sha256"] = case.receipt_sha256
    return payload


def receipt_sha256_for_case(case: ComplianceCase) -> str:
    """Hash the immutable case record (identity, plan, events, outcomes).

    Live generation fields (`receipt_generated_at`, `demo_clock`) and
    `updated_at` (rewritten by store persistence after the hash is taken at
    close) are excluded so a printed SHA-256 still verifies after reload.
    """
    payload = build_receipt_payload(case)
    for key in ("receipt_sha256", "receipt_generated_at", "demo_clock", "updated_at"):
        payload.pop(key, None)
    blob = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def write_receipt_json(case: ComplianceCase, out_dir: Path | None = None) -> Path:
    out_dir = out_dir or DEFAULT_RECEIPTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = build_receipt_payload(case)
    if "receipt_sha256" not in payload:
        payload["receipt_sha256"] = receipt_sha256_for_case(case)
    path = out_dir / f"{case.case_id}.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def _esc(text: Any) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def write_receipt_pdf(case: ComplianceCase, out_dir: Path | None = None) -> Path:
    out_dir = out_dir or DEFAULT_RECEIPTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = build_receipt_payload(case)
    sha = payload.get("receipt_sha256") or receipt_sha256_for_case(case)
    path = out_dir / f"{case.case_id}.pdf"

    doc = SimpleDocTemplate(
        str(path),
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
        title=f"AgriNexus Compliance Receipt {case.case_id}",
        author="AgriNexus Compliance Demo",
        subject="ESA label mitigation educational audit receipt",
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle("ReceiptTitle", parent=styles["Heading1"], fontSize=14, spaceAfter=6)
    h2 = ParagraphStyle(
        "ReceiptH2", parent=styles["Heading2"], fontSize=11, spaceBefore=10, spaceAfter=4
    )
    body = ParagraphStyle("ReceiptBody", parent=styles["Normal"], fontSize=9, leading=12)
    small = ParagraphStyle(
        "ReceiptSmall", parent=styles["Normal"], fontSize=8, leading=10, textColor="#333333"
    )

    product = payload.get("product") or {}
    field = payload.get("field") or {}
    points = payload.get("points") or {}
    weather = payload.get("weather") or {}

    story: list[Any] = [
        Paragraph("AgriNexus Compliance — Audit Receipt", title),
        Paragraph(f"<b>{_esc(payload.get('outcome_headline'))}</b>", body),
        Paragraph(_esc(payload.get("outcome_summary") or ""), small),
        Spacer(1, 6),
        Paragraph(f"<b>Case ID:</b> {_esc(case.case_id)}", body),
        Paragraph(
            f"<b>Applicator:</b> {_esc(case.applicator_name or '—')} · "
            f"<b>Status:</b> {_esc(case.status)}"
            + (f" ({_esc(case.outcome)})" if case.outcome else ""),
            body,
        ),
        Paragraph(
            f"<b>Field:</b> {_esc(field.get('name') or field.get('field_id'))} — "
            f"{_esc(field.get('county'))}, {_esc(field.get('state'))}",
            body,
        ),
        Paragraph(
            f"<b>Product:</b> {_esc(product.get('product_name'))} "
            f"(EPA Reg. No. {_esc(product.get('epa_reg_no'))})",
            body,
        ),
        Paragraph(
            f"<b>Planned spray date:</b> {_esc(case.planned_spray_date or 'n/a')} · "
            f"<b>Generated:</b> {_esc(payload['receipt_generated_at'])}",
            body,
        ),
    ]
    if payload.get("demo_clock"):
        story.append(
            Paragraph(
                f"<b>Demo clock active:</b> {_esc(payload['demo_clock'].get('now'))}",
                small,
            )
        )

    story.append(Paragraph("Timeline", h2))
    for ev in payload.get("timeline") or []:
        elapsed = ev.get("elapsed_from_previous") or "start"
        label = ev.get("label") or ev.get("type")
        story.append(
            Paragraph(
                f"• [{_esc(ev.get('at'))}] <b>{_esc(label)}</b> "
                f"({_esc(elapsed)}) — {_esc(ev.get('detail'))}",
                body,
            )
        )
        if ev.get("outbound_message"):
            story.append(
                Paragraph(
                    f"&nbsp;&nbsp;&nbsp;<i>Outbound:</i> {_esc(ev['outbound_message'])}",
                    small,
                )
            )

    story.append(Paragraph("Verification", h2))
    vitems = (payload.get("verification") or {}).get("items") or []
    if vitems:
        table_data = [["Check", "Source", "Result", "Evidence"]]
        for row in vitems:
            table_data.append(
                [
                    Paragraph(_esc(row.get("check")), small),
                    Paragraph(_esc(row.get("source")), small),
                    Paragraph(_esc(row.get("result")), small),
                    Paragraph(_esc(row.get("evidence")), small),
                ]
            )
        t = Table(table_data, colWidths=[1.4 * inch, 0.9 * inch, 0.7 * inch, 3.2 * inch])
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e7f4ec")),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d9d2c6")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(t)
    else:
        story.append(Paragraph("No verification table on this case yet.", body))

    story.append(Paragraph("Plan", h2))
    story.append(
        Paragraph(
            f"Points required {points.get('required_points')} · "
            f"earned {points.get('earned_points')} · "
            f"shortfall {points.get('shortfall')}",
            body,
        )
    )
    for c in points.get("credited") or []:
        story.append(Paragraph(f"• {_esc(c.get('name') or c.get('id'))}", small))
    story.append(
        Paragraph(
            f"Weather gate: ok={weather.get('weather_ok')} · "
            f"wind={weather.get('wind_mph')} mph · limit={weather.get('max_wind_mph')}",
            body,
        )
    )
    story.append(
        Paragraph(
            f"Bulletin file: {_esc(payload.get('bulletin_file') or '—')}",
            small,
        )
    )
    for a in payload.get("bulletin_actions") or []:
        story.append(Paragraph(f"• {_esc(a)}", small))

    story.append(
        Paragraph(
            "Field-level documentation earns one mitigation point under EPA's "
            "runoff and erosion mitigation menu "
            "(EPA Herbicide Strategy / Insecticide Strategy mitigation measures).",
            small,
        )
    )

    story.append(Paragraph("Confirmation as received", h2))
    conf = payload.get("confirmation")
    if conf:
        if conf.get("checklist"):
            story.append(Paragraph(_esc(json.dumps(conf.get("checklist"))), small))
        elif conf.get("raw_text"):
            story.append(Paragraph(_esc(conf.get("raw_text")), body))
        else:
            story.append(Paragraph(_esc(conf.get("summary") or conf), body))
    else:
        story.append(Paragraph("No confirmation recorded.", body))

    story.append(Paragraph("Provenance", h2))
    for p in payload.get("provenance") or []:
        story.append(
            Paragraph(
                f"• {_esc(p.get('path'))}"
                + (f" · retrieved {_esc(p.get('retrieved'))}" if p.get("retrieved") else "")
                + (
                    f" · printed {_esc(p.get('date_printed'))}"
                    if p.get("date_printed")
                    else ""
                ),
                small,
            )
        )

    story.append(Paragraph("Honesty split", h2))
    hs = payload.get("honesty_split") or {}
    story.append(
        Paragraph(
            f"<b>Rules:</b> {_esc(', '.join(hs.get('deterministic') or []) or '—')}",
            body,
        )
    )
    story.append(
        Paragraph(
            f"<b>Model:</b> {_esc(', '.join(hs.get('model') or []) or '(none on this receipt)')}",
            body,
        )
    )

    story.append(Paragraph("Record integrity", h2))
    story.append(
        Paragraph(
            f"SHA-256: <font face='Courier'>{_esc(sha)}</font> · Kept for two years.",
            small,
        )
    )
    story.append(Spacer(1, 8))
    story.append(Paragraph(DISCLAIMER, small))

    doc.build(story)
    return path


def build_receipt_files(
    case: ComplianceCase, out_dir: Path | None = None
) -> dict[str, str]:
    json_path = write_receipt_json(case, out_dir=out_dir)
    pdf_path = write_receipt_pdf(case, out_dir=out_dir)
    return {"json": str(json_path), "pdf": str(pdf_path)}
