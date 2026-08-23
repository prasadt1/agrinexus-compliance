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
) -> dict[str, Any]:
    field_path = field_path or ROOT / "fixtures" / "fields" / "field_boone.json"
    label_path = label_path or ROOT / "fixtures" / "labels" / "DEMO-000001.json"
    bulletin_path = (
        bulletin_path
        or ROOT / "fixtures" / "bulletins" / "blt-boone-ia-demo-2026-04.json"
    )
    menu_path = menu_path or ROOT / "fixtures" / "mitigation_menu.json"

    label = _load_json(label_path)
    excerpt_rel = label.get("excerpt_markdown_path")
    excerpt = ""
    if excerpt_rel:
        excerpt_path = ROOT / excerpt_rel if not Path(excerpt_rel).is_absolute() else Path(excerpt_rel)
        if excerpt_path.exists():
            excerpt = _read_text(excerpt_path)

    return {
        "field": _load_json(field_path),
        "label": label,
        "label_excerpt": excerpt,
        "bulletin": _load_json(bulletin_path),
        "menu": _load_json(menu_path),
    }


def build_deterministic_plan(
    bundle: dict[str, Any],
    weather_snap: weather_mod.WeatherSnapshot,
) -> dict[str, Any]:
    label = bundle["label"]
    field = bundle["field"]
    bulletin = bundle["bulletin"]
    menu = bundle["menu"]

    required = int(label["required_runoff_points"])
    if bulletin.get("pula_active"):
        required += int(label.get("pula_extra_points") or 0)

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
    gate = weather_mod.evaluate_weather(
        weather_snap,
        max_wind_mph=float(label.get("max_wind_mph", 10)),
        no_rain_hours_before=float(label.get("no_rain_hours_before", 1)),
    )

    apply_allowed = gate.ok and scored.shortfall == 0
    status = "APPLY_OK" if apply_allowed else ("WEATHER_BLOCK" if not gate.ok else "POINTS_SHORT")

    return {
        "status": status,
        "disclaimer": (
            "Educational decision-support demo only. Not legal advice. "
            "The pesticide label and Bulletins Live! Two control. "
            "Strategies are frameworks applied at registration — labels bind."
        ),
        "product": {
            "epa_reg_no": label.get("epa_reg_no"),
            "product_name": label.get("product_name"),
            "requires_bulletins_live_two": label.get("requires_bulletins_live_two"),
        },
        "field": {
            "field_id": field.get("field_id"),
            "county": field.get("county"),
            "state": field.get("state"),
        },
        "bulletin_actions": bulletin.get("actions") or [],
        "points": scored.as_dict(),
        "recommended_additions": additions,
        "weather": {**weather_snap.as_dict(), **gate.as_dict()},
        "citations": [
            "fixtures/mitigation_menu.json",
            str(label.get("excerpt_markdown_path") or "fixtures/labels/"),
            "fixtures/bulletins/blt-boone-ia-demo-2026-04.json",
        ],
        "layers": {
            "deterministic": ["points", "weather", "status"],
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
) -> dict[str, Any]:
    bundle = load_bundle(field_path=field_path, label_path=label_path)
    snap = weather_mod.FIXTURE_WINDY if windy else weather_mod.FIXTURE_CALM
    result = build_deterministic_plan(bundle, snap)
    if not offline:
        result = enrich_with_bedrock(result, bundle)
    return result
