"""Plan-aware verification — compare applicator reply to the issued plan.

Decision-support / record keeping only. Not legal clearance.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def load_menu(path: Path | None = None) -> dict[str, Any]:
    p = path or ROOT / "fixtures" / "mitigation_menu.json"
    with p.open(encoding="utf-8") as f:
        return json.load(f)


def practice_confirmation_map(menu: dict[str, Any] | None = None) -> dict[str, str]:
    menu = menu or load_menu()
    out: dict[str, str] = {}
    for row in menu.get("practices") or []:
        out[str(row["id"])] = str(row.get("confirmation") or "practice")
    return out


def credited_practice_ids(plan: dict[str, Any]) -> list[dict[str, Any]]:
    points = plan.get("points") or {}
    credited = points.get("credited") or []
    return [
        {"id": c.get("id"), "name": c.get("name") or c.get("id")}
        for c in credited
        if c.get("id")
    ]


def checklist_to_interpretation(
    items: dict[str, Any],
    plan: dict[str, Any],
    *,
    menu: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Deterministic confirmation path (secure link / checklist)."""
    conf_map = practice_confirmation_map(menu)
    done = set(items.get("practices_done") or [])
    practices: list[dict[str, Any]] = []
    for row in credited_practice_ids(plan):
        pid = row["id"]
        kind = conf_map.get(pid, "practice")
        if kind == "attribute":
            practices.append(
                {
                    "id": pid,
                    "status": "confirmed",
                    "evidence": "field attribute — no applicator confirmation required",
                }
            )
        elif pid in done:
            practices.append(
                {"id": pid, "status": "confirmed", "evidence": "checklist checked"}
            )
        else:
            practices.append(
                {"id": pid, "status": "not_mentioned", "evidence": "not checked"}
            )

    wind = items.get("wind_mph")
    max_wind = float(((plan.get("weather") or {}).get("max_wind_mph")) or 15)
    # Prefer label max from plan weather gate if present
    weather_ok = None
    if wind is not None:
        weather_ok = float(wind) <= max_wind

    return {
        "bulletin_saved": bool(items.get("bulletin_saved")),
        "applied": bool(items.get("applied")),
        "wind_mph_reported": wind,
        "weather_respected": weather_ok,
        "practices": practices,
        "contradictions": [],
        "needs_human": False,
        "confidence": 1.0,
        "summary": "Checklist confirmation recorded.",
        "layer": "checklist",
        "checklist": items,
        "mode": "checklist",
    }


def verify_against_plan(
    interpretation: dict[str, Any],
    plan: dict[str, Any],
    *,
    menu: dict[str, Any] | None = None,
    require_confidence: bool = True,
) -> dict[str, Any]:
    """Return verification dict and next_status VERIFIED | NEEDS_REVIEW."""
    conf_map = practice_confirmation_map(menu)
    items: list[dict[str, Any]] = []
    failing = False
    source = interpretation.get("layer") or "model"
    if source == "checklist":
        source_label = "checklist"
    elif source == "offline_stub":
        source_label = "model"
    else:
        source_label = "model"

    def add(check: str, result: str, evidence: str = "", src: str | None = None) -> None:
        nonlocal failing
        if result != "pass":
            failing = True
        items.append(
            {
                "check": check,
                "source": src or source_label,
                "result": result,
                "evidence": evidence,
            }
        )

    applied = interpretation.get("applied")
    add(
        "applied",
        "pass" if applied is True else "fail",
        evidence=str(applied),
    )

    bulletin = interpretation.get("bulletin_saved")
    add(
        "bulletin_saved",
        "pass" if bulletin is True else "fail",
        evidence=str(bulletin),
    )

    # Weather
    max_wind = float(
        (plan.get("weather") or {}).get("max_wind_mph")
        or (plan.get("product") or {}).get("max_wind_mph")
        or 15
    )
    # Label often only on weather snapshot via evaluate — also read from credited plan
    wx_respected = interpretation.get("weather_respected")
    wind_reported = interpretation.get("wind_mph_reported")
    weather_pass = False
    evidence = ""
    if wx_respected is True:
        weather_pass = True
        evidence = "weather_respected=true"
    elif wind_reported is not None:
        weather_pass = float(wind_reported) <= max_wind
        evidence = f"wind_mph_reported={wind_reported} (limit {max_wind})"
    else:
        weather_pass = False
        evidence = "no weather confirmation"
    add("weather", "pass" if weather_pass else "fail", evidence=evidence, src="rule")

    # Practices
    by_id = {
        p.get("id"): p for p in (interpretation.get("practices") or []) if p.get("id")
    }
    for row in credited_practice_ids(plan):
        pid = row["id"]
        kind = conf_map.get(pid, "practice")
        if kind == "attribute":
            # Attributes need no confirmation — always pass for verification
            add(
                f"practice:{pid}",
                "pass",
                evidence="attribute — not required",
                src="rule",
            )
            continue
        entry = by_id.get(pid) or {}
        status = entry.get("status") or "not_mentioned"
        if status == "confirmed":
            add(
                f"practice:{pid}",
                "pass",
                evidence=str(entry.get("evidence") or ""),
            )
        else:
            add(
                f"practice:{pid}",
                "fail",
                evidence=f"{status}: {entry.get('evidence') or row.get('name')}",
            )

    contradictions = interpretation.get("contradictions") or []
    if contradictions:
        add("contradictions", "fail", evidence="; ".join(str(c) for c in contradictions))
    else:
        add("contradictions", "pass", evidence="none", src="rule")

    if interpretation.get("needs_human"):
        add("needs_human", "fail", evidence="true")
    else:
        add("needs_human", "pass", evidence="false", src="rule")

    conf = interpretation.get("confidence")
    if require_confidence and source_label == "model":
        ok_conf = conf is not None and float(conf) >= 0.6
        add(
            "confidence",
            "pass" if ok_conf else "fail",
            evidence=str(conf),
            src="rule",
        )
    elif source_label == "checklist":
        add("confidence", "pass", evidence="checklist path", src="rule")

    next_status = "NEEDS_REVIEW" if failing else "VERIFIED"
    summary = (
        "All required plan items confirmed."
        if next_status == "VERIFIED"
        else "One or more plan items need partner review."
    )
    return {
        "next_status": next_status,
        "summary": summary,
        "items": items,
        "source": source_label,
    }
