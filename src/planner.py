"""
Compliance planner: deterministic core + optional Bedrock narrative layer.

Offline mode never calls AWS. Bedrock mode may refine recommendations / cite
label language but must not override weather_ok or point arithmetic.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from . import points as points_mod
from . import weather as weather_mod

ROOT = Path(__file__).resolve().parents[1]

# Named fixture packs: Boone (no PULA) vs McHenry Stryax (PULA + IL cutoff).
PACKS: dict[str, dict[str, Path]] = {
    "boone_liberty": {
        "field": ROOT / "fixtures" / "fields" / "field_boone.json",
        "label": ROOT / "fixtures" / "labels" / "7969-500.json",
        "bulletin": ROOT
        / "fixtures"
        / "bulletins"
        / "blt-boone-ia-7969-500-2026-09.json",
    },
    "mchenry_stryax_pula": {
        "field": ROOT / "fixtures" / "fields" / "field_mchenry_twin_creeks.json",
        "label": ROOT / "fixtures" / "labels" / "264-1241.json",
        "bulletin": ROOT
        / "fixtures"
        / "bulletins"
        / "blt-mchenry-il-264-1241-2026-09.json",
    },
}


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_bundle(
    field_path: Path | None = None,
    label_path: Path | None = None,
    bulletin_path: Path | None = None,
    menu_path: Path | None = None,
    pack: str | None = None,
) -> dict[str, Any]:
    if pack:
        if pack not in PACKS:
            raise ValueError(f"unknown fixture pack: {pack}")
        paths = PACKS[pack]
        field_path = field_path or paths["field"]
        label_path = label_path or paths["label"]
        bulletin_path = bulletin_path or paths["bulletin"]
    field_path = field_path or ROOT / "fixtures" / "fields" / "field_boone.json"
    label_path = label_path or ROOT / "fixtures" / "labels" / "7969-500.json"
    bulletin_path = (
        bulletin_path
        or ROOT / "fixtures" / "bulletins" / "blt-boone-ia-7969-500-2026-09.json"
    )
    menu_path = menu_path or ROOT / "fixtures" / "mitigation_menu.json"

    label = _load_json(label_path)
    excerpt_rel = label.get("excerpt_markdown_path")
    excerpt = ""
    if excerpt_rel:
        excerpt_path = ROOT / excerpt_rel if not Path(excerpt_rel).is_absolute() else Path(excerpt_rel)
        if excerpt_path.exists():
            excerpt = _read_text(excerpt_path)

    bulletin = _load_json(bulletin_path)

    def _rel(p: Path) -> str:
        try:
            return str(p.relative_to(ROOT))
        except ValueError:
            return str(p)

    return {
        "field": _load_json(field_path),
        "label": label,
        "label_excerpt": excerpt,
        "bulletin": bulletin,
        "menu": _load_json(menu_path),
        "paths": {
            "field": _rel(field_path),
            "label": _rel(label_path),
            "bulletin": _rel(bulletin_path),
            "bulletin_pdf": bulletin.get("bulletin_pdf") or "",
        },
    }


def _parse_mmdd(mmdd: str) -> tuple[int, int]:
    month_s, day_s = mmdd.split("-", 1)
    return int(month_s), int(day_s)


def _application_ymd(
    planned_spray_date: str | None,
    bulletin: dict[str, Any],
) -> tuple[int, int, int] | None:
    """Return (year, month, day) for cutoff checks, or None if unknown."""
    if planned_spray_date:
        parts = planned_spray_date.strip()[:10].split("-")
        if len(parts) == 3:
            return int(parts[0]), int(parts[1]), int(parts[2])
    app_month = (bulletin.get("application_month") or "").strip()
    if len(app_month) >= 7 and app_month[4] == "-":
        # Bulletin months are YYYY-MM; treat as the first day of that month
        # for "after June 20" comparisons (September ⇒ after cutoff).
        return int(app_month[0:4]), int(app_month[5:7]), 1
    return None


def evaluate_state_cutoff(
    label: dict[str, Any],
    field: dict[str, Any],
    bulletin: dict[str, Any],
    planned_spray_date: str | None = None,
) -> dict[str, Any] | None:
    """
    Label state-specific calendar cutoffs (e.g. Illinois dicamba on soybean).
    Returns a block dict when the planned/bulletin date is past the cutoff.
    """
    state = (field.get("state") or "").upper()
    cutoffs = (label.get("state_cutoffs") or {}).get(state) or {}
    crop_use = (field.get("crop_use") or "").lower()
    rule = None
    crop_key = None
    if "soybean" in crop_use and "soybean" in cutoffs:
        crop_key = "soybean"
        rule = cutoffs["soybean"]
    if not rule:
        return None
    mmdd = rule.get("cutoff_mmdd") if isinstance(rule, dict) else rule
    if not mmdd:
        return None
    ymd = _application_ymd(planned_spray_date, bulletin)
    if not ymd:
        return None
    year, month, day = ymd
    cut_m, cut_d = _parse_mmdd(str(mmdd))
    if (month, day) <= (cut_m, cut_d):
        return None
    quote = ""
    message = ""
    if isinstance(rule, dict):
        quote = rule.get("source_quote") or ""
        tmpl = rule.get("message_template") or (
            "This label does not allow {product_class} on {crop_noun} in "
            "{state_name} after {cutoff_display}. Do not apply."
        )
        message = tmpl.format(
            product_class=rule.get("product_class") or "this product",
            crop_noun=rule.get("crop_noun") or crop_key or "this crop",
            state_name=rule.get("state_name") or state,
            cutoff_display=rule.get("cutoff_display")
            or f"{cut_m}/{cut_d}",
        )
    else:
        message = (
            f"This label does not allow application in {state} after "
            f"{cut_m}/{cut_d}. Do not apply."
        )
    return {
        "blocked": True,
        "state": state,
        "crop": crop_key,
        "cutoff_mmdd": str(mmdd),
        "cutoff_display": (
            rule.get("cutoff_display") if isinstance(rule, dict) else None
        )
        or f"{cut_m}/{cut_d}",
        "state_name": (
            rule.get("state_name") if isinstance(rule, dict) else None
        )
        or state,
        "application_date": f"{year:04d}-{month:02d}-{day:02d}",
        "message": message,
        "source_quote": quote,
        "layer": "deterministic",
    }


def _format_bulletin_month(app_month: str) -> str:
    """Turn YYYY-MM into 'September 2026' when possible."""
    try:
        year = int(app_month[0:4])
        month = int(app_month[5:7])
        import calendar

        return f"{calendar.month_name[month]} {year}"
    except (ValueError, IndexError):
        return app_month


def evaluate_bulletin_month(
    bulletin: dict[str, Any],
    planned_spray_date: str | None = None,
) -> dict[str, Any] | None:
    """
    Bulletin prints are month-specific. Planning a different month than the
    on-file bulletin is a block (print the matching month first).
    """
    app_month = (bulletin.get("application_month") or "").strip()
    if len(app_month) < 7 or not planned_spray_date:
        return None
    parts = planned_spray_date.strip()[:10].split("-")
    if len(parts) < 2:
        return None
    planned_ym = f"{parts[0]}-{parts[1]}"
    if planned_ym == app_month[:7]:
        return None
    printed = _format_bulletin_month(app_month[:7])
    needed = _format_bulletin_month(planned_ym)
    return {
        "blocked": True,
        "bulletin_month": app_month[:7],
        "planned_month": planned_ym,
        "message": (
            f"The bulletin on file is for {printed}. Print the bulletin for "
            f"{needed} before planning this date."
        ),
        "layer": "deterministic",
    }


def build_deterministic_plan(
    bundle: dict[str, Any],
    weather_snap: weather_mod.WeatherSnapshot,
    planned_spray_date: str | None = None,
) -> dict[str, Any]:
    label = bundle["label"]
    field = bundle["field"]
    bulletin = bundle["bulletin"]
    menu = bundle["menu"]

    required = int(label["required_runoff_points"])
    if bulletin.get("pula_active"):
        extra = bulletin.get("pula_extra_points")
        if extra is None:
            extra = label.get("pula_extra_points") or 0
        required += int(extra)

    scored = points_mod.score_field(
        field.get("practices") or [],
        required_points=required,
        menu=menu,
    )
    additions = points_mod.recommend_additions(
        field.get("practices") or [],
        required_points=required,
        menu=menu,
    )

    rain_hours = label.get("no_rain_hours_before")
    gate = weather_mod.evaluate_weather(
        weather_snap,
        max_wind_mph=float(label.get("max_wind_mph", 10)),
        no_rain_hours_before=(
            None if rain_hours is None else float(rain_hours)
        ),
        min_wind_mph=(
            float(label["min_wind_mph"])
            if label.get("min_wind_mph") is not None
            else None
        ),
    )

    cutoff = evaluate_state_cutoff(
        label, field, bulletin, planned_spray_date=planned_spray_date
    )
    bulletin_month = evaluate_bulletin_month(
        bulletin, planned_spray_date=planned_spray_date
    )

    # Precedence: label date → bulletin month → weather → points.
    # Points still render under date/month blocks so the PULA lesson remains.
    if cutoff:
        status = "LABEL_DATE_BLOCK"
    elif bulletin_month:
        status = "BULLETIN_MONTH_BLOCK"
    elif not gate.ok:
        status = "WEATHER_BLOCK"
    elif scored.shortfall == 0:
        status = "APPLY_OK"
    else:
        status = "POINTS_SHORT"

    paths = bundle.get("paths") or {}
    citations = [
        "fixtures/mitigation_menu.json",
        paths.get("label") or str(label.get("excerpt_markdown_path") or "fixtures/labels/"),
        paths.get("bulletin") or "",
    ]
    if paths.get("bulletin_pdf"):
        citations.append(paths["bulletin_pdf"])
    citations = [c for c in citations if c]

    product = {
        "epa_reg_no": label.get("epa_reg_no"),
        "product_name": label.get("product_name"),
        "requires_bulletins_live_two": label.get("requires_bulletins_live_two"),
        "max_wind_mph": label.get("max_wind_mph"),
        "min_wind_mph": label.get("min_wind_mph"),
        "restricted_use_pesticide": label.get("restricted_use_pesticide"),
        "documentation_mitigation_point": label.get("documentation_mitigation_point"),
        "record_retention_years": label.get("record_retention_years"),
        "record_retention": label.get("record_retention"),
    }

    return {
        "status": status,
        "disclaimer": (
            "Educational decision-support demo only. Not legal advice. "
            "The pesticide label and Bulletins Live! Two control. "
            "Strategies are frameworks applied at registration — labels bind."
        ),
        "product": product,
        "field": {
            "field_id": field.get("field_id"),
            "county": field.get("county"),
            "state": field.get("state"),
            "name": field.get("name"),
            "township": field.get("township"),
            "lat": field.get("lat"),
            "lon": field.get("lon"),
            "use_frame": field.get("use_frame"),
            "crop_use": field.get("crop_use"),
        },
        "bulletin_actions": bulletin.get("actions") or [],
        "bulletin_meta": {
            "application_month": bulletin.get("application_month"),
            "date_printed": bulletin.get("date_printed"),
            "pdf_md5": bulletin.get("pdf_md5"),
            "pdf_creation": bulletin.get("pdf_creation"),
            "bulletin_pdf": bulletin.get("bulletin_pdf"),
            "coordinate_note": bulletin.get("coordinate_note"),
        },
        "pula_active": bool(bulletin.get("pula_active")),
        "pula_extra_points": int(bulletin.get("pula_extra_points") or 0)
        if bulletin.get("pula_active")
        else 0,
        "label_date_cutoff": cutoff,
        "bulletin_month_gate": bulletin_month,
        "points": scored.as_dict(),
        "recommended_additions": additions,
        "weather": {
            **weather_snap.as_dict(),
            **gate.as_dict(),
            "max_wind_mph": float(label.get("max_wind_mph", 10)),
            "min_wind_mph": label.get("min_wind_mph"),
        },
        "citations": citations,
        "layers": {
            "deterministic": [
                "label_date_cutoff",
                "bulletin_month_gate",
                "points",
                "weather",
                "status",
            ],
            "model": [],
        },
    }


def _extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def enrich_with_bedrock(plan: dict[str, Any], bundle: dict[str, Any]) -> dict[str, Any]:
    """
    Optional narrative + practice ranking. Never flips weather_ok or recomputes
    earned points — those stay from the deterministic plan.
    """
    model_id = os.environ.get(
        "COMPLIANCE_BEDROCK_MODEL", "anthropic.claude-3-haiku-20240307-v1:0"
    )
    region = os.environ.get("AWS_REGION", "us-east-1")

    import boto3

    client = boto3.client("bedrock-runtime", region_name=region)

    user_payload = {
        "task": (
            "You help US applicators understand ESA pesticide-LABEL mitigation "
            "(educational). Propose which mitigation_menu practices to add to close "
            "a points shortfall. Extract any bulletin/label actions worth emphasizing. "
            "Return ONLY JSON with keys: "
            "summary (string), "
            "recommended_additions (array of {id, reason}), "
            "label_bulletin_highlights (array of strings), "
            "confidence (0-1)."
        ),
        "constraints": [
            "Only recommend practice ids from mitigation_menu",
            "Do not invent point values",
            "Do not claim weather is safe if weather_ok is false",
            "Remind that the label controls, not this tool",
        ],
        "deterministic_plan": {
            "status": plan["status"],
            "points": plan["points"],
            "recommended_additions": plan["recommended_additions"],
            "weather": plan["weather"],
            "bulletin_actions": plan["bulletin_actions"],
        },
        "label_excerpt": bundle.get("label_excerpt", "")[:6000],
        "bulletin": bundle.get("bulletin"),
        "mitigation_menu_ids": [p["id"] for p in bundle["menu"]["practices"]],
    }

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1024,
        "temperature": 0,
        "messages": [
            {
                "role": "user",
                "content": json.dumps(user_payload),
            }
        ],
    }

    resp = client.invoke_model(
        modelId=model_id,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(body),
    )
    raw = json.loads(resp["body"].read())
    text = raw["content"][0]["text"]
    model_out = _extract_json_object(text)

    plan = dict(plan)
    plan["model"] = model_out
    plan["layers"] = {
        "deterministic": plan["layers"]["deterministic"],
        "model": ["summary", "recommended_additions_reasons", "label_bulletin_highlights"],
    }
    # Merge reasons onto deterministic greedy picks when ids match
    reason_by_id = {
        r["id"]: r.get("reason")
        for r in (model_out.get("recommended_additions") or [])
        if isinstance(r, dict) and r.get("id")
    }
    merged = []
    for row in plan["recommended_additions"]:
        item = dict(row)
        if row["id"] in reason_by_id:
            item["model_reason"] = reason_by_id[row["id"]]
        merged.append(item)
    plan["recommended_additions"] = merged
    return plan


def plan(
    offline: bool = True,
    windy: bool = False,
    field_path: Path | None = None,
    label_path: Path | None = None,
    bulletin_path: Path | None = None,
    pack: str | None = None,
    planned_spray_date: str | None = None,
) -> dict[str, Any]:
    bundle = load_bundle(
        field_path=field_path,
        label_path=label_path,
        bulletin_path=bulletin_path,
        pack=pack,
    )
    snap = weather_mod.FIXTURE_WINDY if windy else weather_mod.FIXTURE_CALM
    result = build_deterministic_plan(
        bundle, snap, planned_spray_date=planned_spray_date
    )
    if not offline:
        result = enrich_with_bedrock(result, bundle)
    return result
