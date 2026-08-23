"""
Free-text / multimodal confirmation interpreter (Bedrock).

This is where loop-closure AI lives — not keyword lists.
Offline mode uses a tiny heuristic only for local tests; do not claim that
heuristic as the product.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any


CONFIRM_SCHEMA_HELP = {
    "bulletin_saved": "bool|null",
    "points_practices_done": "list[str] practice ids mentioned or null",
    "applied": "bool|null — whether they sprayed / applied",
    "weather_respected": "bool|null",
    "needs_human": "bool — escalate if unclear or high stakes",
    "confidence": "0-1",
    "summary": "short string",
}


def interpret_offline(text: str) -> dict[str, Any]:
    """Crude local stub for tests. Not the endeavor claim."""
    t = text.lower()
    applied = any(w in t for w in ("sprayed", "applied", "finished application"))
    bulletin = any(w in t for w in ("bulletin", "printed blt", "bulletins live"))
    unclear = len(t.split()) < 4
    return {
        "bulletin_saved": bulletin if bulletin else None,
        "points_practices_done": None,
        "applied": applied if applied else None,
        "weather_respected": None,
        "needs_human": unclear or (applied and not bulletin),
        "confidence": 0.35,
        "summary": "offline heuristic only — replace with Bedrock for demos",
        "layer": "offline_stub",
        "raw_text": text,
    }


def interpret_bedrock(text: str) -> dict[str, Any]:
    model_id = os.environ.get(
        "COMPLIANCE_BEDROCK_MODEL", "anthropic.claude-3-haiku-20240307-v1:0"
    )
    region = os.environ.get("AWS_REGION", "us-east-1")
    import boto3

    client = boto3.client("bedrock-runtime", region_name=region)
    prompt = {
        "task": (
            "Map an applicator's free-text reply about ESA label mitigation "
            "follow-through into JSON. Schema: " + json.dumps(CONFIRM_SCHEMA_HELP)
        ),
        "reply": text,
        "rules": [
            "If unsure, set fields null and needs_human true",
            "Do not invent practices not implied by the text",
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
    return data


def interpret(text: str, offline: bool = True) -> dict[str, Any]:
    if offline:
        return interpret_offline(text)
    return interpret_bedrock(text)
