"""Seed Boone cohort as real CaseStore rows across the ladder."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import clock
from .cases import CaseStore
from .planner import plan
from .scheduler import compute_anchor, tick
from .verify import checklist_to_interpretation, verify_against_plan

ROOT = Path(__file__).resolve().parents[1]


def bulletin_month() -> str:
    path = ROOT / "fixtures" / "bulletins" / "blt-boone-ia-7969-500-2026-09.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["application_month"]  # YYYY-MM


def spray_day(day: int = 15) -> str:
    return f"{bulletin_month()}-{day:02d}"


def _mark_example(store: CaseStore, case_id: str):
    case = store.get(case_id)
    assert case is not None
    case.is_example = True
    return store._update(case)


def seed_cohort(store: CaseStore | None = None) -> int:
    """Create six real cases. Order avoids shared-tick collisions."""
    store = store or CaseStore()
    start = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
    clock.set_override(start)
    clock.write_file_override(start)

    # A. Williams — spray date not reached (later day in bulletin month)
    w = store.create(
        plan(offline=True, windy=False),
        planned_spray_date=spray_day(28),
        applicator_name="A. Williams",
        phone="+1 (515) 555-0177",
    )
    _mark_example(store, w.case_id)

    # M. Larsen — blocked
    lar = store.create(
        plan(offline=True, windy=True),
        planned_spray_date=spray_day(15),
        applicator_name="M. Larsen",
        phone="+1 (515) 555-0166",
    )
    _mark_example(store, lar.case_id)

    # D. Okafor — expire then close (before other day-15 open cases exist)
    okafor = store.create(
        plan(offline=True, windy=False),
        planned_spray_date=spray_day(15),
        applicator_name="D. Okafor",
        phone="+1 (515) 555-0133",
    )
    _mark_example(store, okafor.case_id)
    o_anchor = compute_anchor(okafor)
    clock.set_override(o_anchor + timedelta(hours=72))
    clock.write_file_override(o_anchor + timedelta(hours=72))
    tick(store)
    store.close(okafor.case_id, outcome="expired")

    # R. Chen — two reminders, still open
    chen = store.create(
        plan(offline=True, windy=False),
        planned_spray_date=spray_day(15),
        applicator_name="R. Chen",
        phone="+1 (515) 555-0198",
    )
    _mark_example(store, chen.case_id)
    c_anchor = compute_anchor(chen)
    clock.set_override(c_anchor + timedelta(hours=48))
    clock.write_file_override(c_anchor + timedelta(hours=48))
    tick(store)

    # S. Nguyen — needs review (wind)
    nguyen = store.create(
        plan(offline=True, windy=False),
        planned_spray_date=spray_day(15),
        applicator_name="S. Nguyen",
        phone="+1 (515) 555-0111",
    )
    _mark_example(store, nguyen.case_id)
    n_anchor = compute_anchor(nguyen)
    clock.set_override(n_anchor + timedelta(hours=24))
    clock.write_file_override(n_anchor + timedelta(hours=24))
    tick(store)
    # Re-load plan from store
    nguyen = store.get(nguyen.case_id)
    assert nguyen is not None
    items_bad = {
        "bulletin_saved": True,
        "applied": True,
        "wind_mph": 20,
        "practices_done": ["grassed_waterway", "mitigation_tracking"],
    }
    conf_bad = checklist_to_interpretation(items_bad, nguyen.plan or {})
    store.confirm(nguyen.case_id, conf_bad, mode="checklist")
    verdict_bad = verify_against_plan(conf_bad, nguyen.plan or {})
    store.apply_verification(
        nguyen.case_id, verdict_bad, next_status=verdict_bad["next_status"]
    )

    # J. Martinez — verified + closed
    martinez = store.create(
        plan(offline=True, windy=False),
        planned_spray_date=spray_day(15),
        applicator_name="J. Martinez",
        phone="+1 (515) 555-0142",
    )
    _mark_example(store, martinez.case_id)
    m_anchor = compute_anchor(martinez)
    clock.set_override(m_anchor + timedelta(hours=24))
    clock.write_file_override(m_anchor + timedelta(hours=24))
    tick(store)
    martinez = store.get(martinez.case_id)
    assert martinez is not None
    items_ok = {
        "bulletin_saved": True,
        "applied": True,
        "wind_mph": 6,
        "practices_done": ["grassed_waterway", "mitigation_tracking"],
    }
    conf_ok = checklist_to_interpretation(items_ok, martinez.plan or {})
    conf_ok["summary"] = (
        "Saved the Boone bulletin, kept grassed waterway, sprayed at 7am under 6 mph"
    )
    conf_ok["raw_text"] = conf_ok["summary"]
    store.confirm(martinez.case_id, conf_ok, mode="checklist")
    verdict_ok = verify_against_plan(conf_ok, martinez.plan or {})
    store.apply_verification(
        martinez.case_id, verdict_ok, next_status=verdict_ok["next_status"]
    )
    store.close(martinez.case_id, outcome="verified")

    # Leave file clock for demo UI; clear in-process override
    clock.write_file_override(clock.now())
    clock.clear_override()
    return len(store.list_cases())
