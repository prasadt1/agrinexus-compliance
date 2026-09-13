"""Seed Boone cohort as real CaseStore rows across the ladder.

Each case is seeded with the demo clock moving forward only on that case's
timeline. Between cases the clock may restart at the shared seed epoch; it
never moves backward while a case is accumulating events. After seeding,
real time is restored (file + in-process overrides cleared).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import clock
from .cases import CaseStore, ComplianceCase
from .planner import plan
from .scheduler import compute_anchor, tick
from .verify import checklist_to_interpretation, verify_against_plan

ROOT = Path(__file__).resolve().parents[1]
SEED_START = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)


def bulletin_month() -> str:
    path = ROOT / "fixtures" / "bulletins" / "blt-boone-ia-7969-500-2026-09.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["application_month"]  # YYYY-MM


def spray_day(day: int = 15) -> str:
    return f"{bulletin_month()}-{day:02d}"


def _set_clock(when: datetime) -> None:
    clock.set_override(when)
    clock.write_file_override(when)


def _advance_to(when: datetime, store: CaseStore) -> None:
    _set_clock(when)
    tick(store)


def _mark_example(store: CaseStore, case_id: str) -> ComplianceCase:
    case = store.get(case_id)
    assert case is not None
    case.is_example = True
    return store._update(case)


def assert_events_non_decreasing(case: ComplianceCase) -> None:
    """Every event timestamp must be >= the previous one on the same case."""
    prev: datetime | None = None
    for ev in case.events or []:
        raw = ev.get("at")
        if not raw:
            raise AssertionError(f"{case.case_id}: event missing 'at': {ev}")
        text = str(raw)
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        at = datetime.fromisoformat(text)
        if at.tzinfo is None:
            at = at.replace(tzinfo=timezone.utc)
        at = at.astimezone(timezone.utc)
        if prev is not None and at < prev:
            raise AssertionError(
                f"{case.applicator_name or case.case_id}: event times go backward "
                f"({prev.isoformat()} → {at.isoformat()}) type={ev.get('type')}"
            )
        prev = at


def seed_cohort(store: CaseStore | None = None) -> int:
    """Create six real cases. Per-case clock runs forward only; then real time."""
    store = store or CaseStore()

    # --- A. Williams: plan only, spray date not reached ---
    _set_clock(SEED_START)
    w = store.create(
        plan(offline=True, windy=False),
        planned_spray_date=spray_day(28),
        applicator_name="A. Williams",
        phone="+1 (515) 555-0177",
    )
    _mark_example(store, w.case_id)

    # --- M. Larsen: blocked ---
    _set_clock(SEED_START)
    lar = store.create(
        plan(offline=True, windy=True),
        planned_spray_date=spray_day(15),
        applicator_name="M. Larsen",
        phone="+1 (515) 555-0166",
    )
    _mark_example(store, lar.case_id)

    # --- D. Okafor: expire then close ---
    _set_clock(SEED_START)
    okafor = store.create(
        plan(offline=True, windy=False),
        planned_spray_date=spray_day(15),
        applicator_name="D. Okafor",
        phone="+1 (515) 555-0133",
    )
    _mark_example(store, okafor.case_id)
    o_anchor = compute_anchor(okafor)
    _advance_to(o_anchor + timedelta(hours=24), store)
    _advance_to(o_anchor + timedelta(hours=48), store)
    _advance_to(o_anchor + timedelta(hours=72), store)
    store.close(okafor.case_id, outcome="expired")

    # --- R. Chen: two reminders, still open ---
    _set_clock(SEED_START)
    chen = store.create(
        plan(offline=True, windy=False),
        planned_spray_date=spray_day(15),
        applicator_name="R. Chen",
        phone="+1 (515) 555-0198",
    )
    _mark_example(store, chen.case_id)
    c_anchor = compute_anchor(chen)
    _advance_to(c_anchor + timedelta(hours=24), store)
    _advance_to(c_anchor + timedelta(hours=48), store)

    # --- S. Nguyen: needs review (wind) ---
    _set_clock(SEED_START)
    nguyen = store.create(
        plan(offline=True, windy=False),
        planned_spray_date=spray_day(15),
        applicator_name="S. Nguyen",
        phone="+1 (515) 555-0111",
    )
    _mark_example(store, nguyen.case_id)
    n_anchor = compute_anchor(nguyen)
    _advance_to(n_anchor + timedelta(hours=24), store)
    nguyen = store.get(nguyen.case_id)
    assert nguyen is not None
    items_bad = {
        "bulletin_saved": True,
        "applied": True,
        "wind_mph": 20,
        "practices_done": ["grassed_waterway", "mitigation_tracking"],
    }
    conf_bad = checklist_to_interpretation(items_bad, nguyen.plan or {})
    _advance_to(n_anchor + timedelta(hours=25), store)
    store.confirm(nguyen.case_id, conf_bad, mode="checklist")
    verdict_bad = verify_against_plan(conf_bad, nguyen.plan or {})
    store.apply_verification(
        nguyen.case_id, verdict_bad, next_status=verdict_bad["next_status"]
    )

    # --- J. Martinez: full ladder with visible elapsed gaps ---
    _set_clock(SEED_START)
    martinez = store.create(
        plan(offline=True, windy=False),
        planned_spray_date=spray_day(15),
        applicator_name="J. Martinez",
        phone="+1 (515) 555-0142",
    )
    _mark_example(store, martinez.case_id)
    m_anchor = compute_anchor(martinez)
    _advance_to(m_anchor + timedelta(hours=24), store)
    _advance_to(m_anchor + timedelta(hours=48), store)
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
    _advance_to(m_anchor + timedelta(hours=49), store)
    store.confirm(martinez.case_id, conf_ok, mode="checklist")
    verdict_ok = verify_against_plan(conf_ok, martinez.plan or {})
    store.apply_verification(
        martinez.case_id, verdict_ok, next_status=verdict_ok["next_status"]
    )
    _advance_to(m_anchor + timedelta(hours=50), store)
    store.close(martinez.case_id, outcome="verified")

    for case in store.list_cases():
        assert_events_non_decreasing(case)

    # Restore real time — do not leave a frozen file override.
    clock.clear_file_override()
    clock.clear_override()
    return len(store.list_cases())
