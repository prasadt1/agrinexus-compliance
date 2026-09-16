"""Full ladder integration tests."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import clock
from src.cases import CaseStore, ConflictError
from src.planner import plan
from src.receipt import build_receipt_payload, receipt_sha256_for_case
from src.scheduler import compute_anchor, tick
from src.verify import checklist_to_interpretation, verify_against_plan


def setup_function():
    clock.clear_override()


def teardown_function():
    clock.clear_override()


def test_full_ladder_checklist_close(tmp_path):
    store = CaseStore(path=tmp_path / "cases.jsonl")
    clock.set_override(datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc))
    case = store.create(
        plan(offline=True),
        planned_spray_date="2026-09-15",
        applicator_name="Ladder Pilot",
    )
    anchor = compute_anchor(case)
    assert anchor == datetime(2026, 9, 15, 23, 0, tzinfo=timezone.utc)

    clock.set_override(anchor + timedelta(hours=24))
    tick(store)
    c = store.get(case.case_id)
    assert c.status == "NUDGED"
    assert c.nudge_count == 1 or sum(
        1 for e in c.events if e["type"] == "reminder_sent"
    ) == 1

    clock.set_override(anchor + timedelta(hours=48))
    tick(store)
    c = store.get(case.case_id)
    assert sum(1 for e in c.events if e["type"] == "reminder_sent") == 2

    items = {
        "bulletin_saved": True,
        "applied": True,
        "wind_mph": 6,
        "practices_done": ["grassed_waterway", "mitigation_tracking"],
    }
    conf = checklist_to_interpretation(items, c.plan or {})
    store.confirm(c.case_id, conf, mode="checklist")
    v = verify_against_plan(conf, c.plan or {})
    store.apply_verification(c.case_id, v, next_status="VERIFIED")
    closed = store.close(c.case_id)
    assert closed.status == "CLOSED"
    assert closed.outcome == "verified"
    assert closed.receipt_sha256
    payload = build_receipt_payload(closed)
    # At least planned, 2 reminders, reply, interpreted, verified, closed
    types = [e["type"] for e in closed.events]
    assert "planned" in types
    assert types.count("reminder_sent") == 2
    assert "reply_received" in types
    assert "verified" in types
    assert "closed" in types
    assert len(payload["timeline"]) >= 6
    # sha matches recomputation even after the clock advances
    assert closed.receipt_sha256 == receipt_sha256_for_case(closed)
    clock.set_override(anchor + timedelta(hours=100))
    assert closed.receipt_sha256 == receipt_sha256_for_case(closed)


def test_receipt_sha256_stable_after_clock_advance_and_reload(tmp_path):
    store = CaseStore(path=tmp_path / "cases.jsonl")
    clock.set_override(datetime(2026, 9, 1, tzinfo=timezone.utc))
    case = store.create(plan(offline=True), planned_spray_date="2026-09-15")
    anchor = compute_anchor(case)
    clock.set_override(anchor + timedelta(hours=72))
    tick(store)
    closed = store.close(case.case_id)
    assert closed.receipt_sha256
    clock.set_override(anchor + timedelta(hours=96))
    reloaded = store.get(closed.case_id)
    assert reloaded is not None
    assert receipt_sha256_for_case(reloaded) == reloaded.receipt_sha256


def test_expiry_close(tmp_path):
    store = CaseStore(path=tmp_path / "cases.jsonl")
    clock.set_override(datetime(2026, 9, 1, tzinfo=timezone.utc))
    case = store.create(plan(offline=True), planned_spray_date="2026-09-15")
    anchor = compute_anchor(case)
    clock.set_override(anchor + timedelta(hours=72))
    tick(store)
    closed = store.close(case.case_id)
    assert closed.outcome == "expired"


def test_409_mutations_on_closed(tmp_path):
    store = CaseStore(path=tmp_path / "cases.jsonl")
    clock.set_override(datetime(2026, 9, 1, tzinfo=timezone.utc))
    case = store.create(plan(offline=True), planned_spray_date="2026-09-15")
    anchor = compute_anchor(case)
    clock.set_override(anchor + timedelta(hours=72))
    tick(store)
    store.close(case.case_id)
    try:
        store.confirm(case.case_id, {"summary": "x", "raw_text": "x"})
        assert False
    except ConflictError:
        pass
    try:
        store.simulate_reminder(case.case_id)
        assert False
    except ConflictError:
        pass


def test_seed_cohort_ladder(tmp_path, monkeypatch):
    from src import seed_cohort as sc
    from src.clock import status as clock_status

    monkeypatch.setattr(sc, "ROOT", ROOT)
    store = CaseStore(path=tmp_path / "cases.jsonl")
    n = sc.seed_cohort(store)
    assert n == 6
    by_name = {c.applicator_name: c.status for c in store.list_cases()}
    assert by_name["J. Martinez"] == "CLOSED"
    assert by_name["R. Chen"] == "NUDGED"
    assert by_name["A. Williams"] == "PLANNED"
    assert by_name["D. Okafor"] == "CLOSED"
    assert by_name["S. Nguyen"] == "NEEDS_REVIEW"
    assert by_name["M. Larsen"] == "BLOCKED"
    for case in store.list_cases():
        sc.assert_events_non_decreasing(case)
    # Martinez must show real gaps between ladder rungs (not one collapsed timestamp)
    martinez = next(c for c in store.list_cases() if c.applicator_name == "J. Martinez")
    times = [e["at"] for e in martinez.events]
    assert len(set(times)) >= 4
    clk = clock_status()
    assert clk["override_active"] is False
    assert clk["source"] == "system"


def test_seeded_events_are_non_decreasing(tmp_path, monkeypatch):
    from src import seed_cohort as sc

    monkeypatch.setattr(sc, "ROOT", ROOT)
    store = CaseStore(path=tmp_path / "cases.jsonl")
    sc.seed_cohort(store)
    for case in store.list_cases():
        sc.assert_events_non_decreasing(case)
