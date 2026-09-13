"""Table-driven plan verification tests."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.cases import CaseStore
from src.planner import plan
from src.verify import checklist_to_interpretation, verify_against_plan


def _plan():
    return plan(offline=True, windy=False)


def _base_interp(**overrides):
    p = _plan()
    practices = []
    for c in (p.get("points") or {}).get("credited") or []:
        practices.append(
            {
                "id": c["id"],
                "status": "confirmed",
                "evidence": "ok",
            }
        )
    data = {
        "bulletin_saved": True,
        "applied": True,
        "wind_mph_reported": 6,
        "weather_respected": True,
        "practices": practices,
        "contradictions": [],
        "needs_human": False,
        "confidence": 0.9,
        "layer": "model",
        "summary": "all good",
    }
    data.update(overrides)
    return p, data


def test_all_confirmed_verified():
    p, interp = _base_interp()
    v = verify_against_plan(interp, p)
    assert v["next_status"] == "VERIFIED"


def test_wind_above_limit_needs_review():
    p, interp = _base_interp(
        wind_mph_reported=20, weather_respected=False, confidence=0.9
    )
    v = verify_against_plan(interp, p)
    assert v["next_status"] == "NEEDS_REVIEW"
    weather = next(i for i in v["items"] if i["check"] == "weather")
    assert weather["result"] == "fail"


def test_practice_not_mentioned_needs_review_attribute_ok():
    p, interp = _base_interp()
    # Drop grassed_waterway confirmation; keep attributes unmarked in practices list
    interp["practices"] = [
        x
        for x in interp["practices"]
        if x["id"]
        not in {"grassed_waterway", "runoff_vulnerability_relief", "non_irrigated"}
    ]
    # Attributes absent from practices list still pass via rule
    v = verify_against_plan(interp, p)
    assert v["next_status"] == "NEEDS_REVIEW"
    failing = [i for i in v["items"] if i["result"] == "fail"]
    assert any("grassed_waterway" in i["check"] for i in failing)
    assert not any("runoff_vulnerability_relief" in i["check"] and i["result"] == "fail" for i in failing)


def test_needs_human_or_low_confidence():
    p, interp = _base_interp(needs_human=True)
    assert verify_against_plan(interp, p)["next_status"] == "NEEDS_REVIEW"
    p, interp = _base_interp(confidence=0.4, needs_human=False)
    assert verify_against_plan(interp, p)["next_status"] == "NEEDS_REVIEW"


def test_checklist_path_verified_offline(tmp_path):
    store = CaseStore(path=tmp_path / "cases.jsonl")
    p = _plan()
    case = store.create(p, planned_spray_date="2026-09-15")
    items = {
        "bulletin_saved": True,
        "applied": True,
        "wind_mph": 6,
        "practices_done": ["grassed_waterway", "mitigation_tracking"],
    }
    conf = checklist_to_interpretation(items, p)
    case = store.confirm(case.case_id, conf, mode="checklist")
    assert case.status == "CONFIRMED"
    v = verify_against_plan(conf, p)
    assert v["next_status"] == "VERIFIED"
    case = store.apply_verification(case.case_id, v, next_status="VERIFIED")
    assert case.status == "VERIFIED"
