"""
Free-text / multimodal confirmation interpreter (Bedrock).

This is where loop-closure AI lives — not keyword lists.
Offline mode stores the reply without a verification verdict.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any


CONFIRM_SCHEMA_HELP = {
    "bulletin_saved": "bool|null",
    "applied": "bool|null — whether they sprayed / applied",
    "wind_mph_reported": "number|null",
    "weather_respected": "bool|null",
    "practices": (
        "[{id, status: confirmed | not_mentioned | contradicted, "
        "evidence: quoted words}]"
    ),
    "contradictions": "[string]",
    "needs_human": "bool",
    "confidence": "0-1",
    "summary": "one plain sentence for the applicator record",
}


def interpret_offline(text: str, plan: dict[str, Any] | None = None) -> dict[str, Any]:
    """Store-only offline stub — no plan verdict (checklist path verifies offline)."""
    return {
        "bulletin_saved": None,
        "applied": None,
        "wind_mph_reported": None,
        "weather_respected": None,
        "practices": [],
        "contradictions": [],
        "needs_human": True,
        "confidence": 0.0,
        "summary": (
            "Reply stored. Interpretation needs the model layer, "
            "which is off in this session."
        ),
        "layer": "offline_stub",
        "raw_text": text,
        "mode": "free_text",
    }


def interpret_bedrock(text: str, plan: dict[str, Any] | None = None) -> dict[str, Any]:
    model_id = os.environ.get(
        "COMPLIANCE_BEDROCK_MODEL",
        "anthropic.claude-3-haiku-20240307-v1:0",
    )
    region = os.environ.get("AWS_REGION") or os.environ.get(
        "COMPLIANCE_BEDROCK_REGION", "us-east-1"
    )
    import boto3

    plan = plan or {}
    points = plan.get("points") or {}
    credited = points.get("credited") or []
    client = boto3.client("bedrock-runtime", region_name=region)
    prompt = {
        "task": (
            "Map an applicator's free-text reply about ESA label mitigation "
            "follow-through into JSON. Schema: " + json.dumps(CONFIRM_SCHEMA_HELP)
        ),
        "plan_context": {
            "credited_practices": [
                {"id": c.get("id"), "name": c.get("name")} for c in credited
            ],
            "bulletin_actions": plan.get("bulletin_actions") or [],
            "max_wind_mph": (plan.get("weather") or {}).get("max_wind_mph")
            or (plan.get("product") or {}).get("max_wind_mph"),
            "planned_spray_date": plan.get("planned_spray_date"),
        },
        "reply": text,
        "rules": [
            "If unsure, set fields null and needs_human true",
            "Do not invent practices not implied by the text",
            "For each credited practice id, set status confirmed, not_mentioned, or contradicted",
        ],
    }
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 512,
        "temperature": 0,
        "messages": [{"role": "user", "content": json.dumps(prompt)}],
    }
    resp = client.invoke_model(
        modelId=model_id,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(body),
    )
    raw = json.loads(resp["body"].read())
    out_text = raw["content"][0]["text"].strip()
    if out_text.startswith("```"):
        out_text = re.sub(r"^```(?:json)?\s*", "", out_text)
        out_text = re.sub(r"\s*```$", "", out_text)
    data = json.loads(out_text)
    data["layer"] = "model"
    data["raw_text"] = text
    data["mode"] = "free_text"
    return data


def interpret(
    text: str,
    offline: bool = True,
    plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if offline:
        return interpret_offline(text, plan=plan)
    return interpret_bedrock(text, plan=plan)
