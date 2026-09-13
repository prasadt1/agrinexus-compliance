"""Scheduler tick tests — 24 h / 48 h reminders and 72 h expiry."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import clock
from src.cases import CaseStore
from src.planner import plan
from src.scheduler import compute_anchor, tick


def setup_function():
    clock.clear_override()


def teardown_function():
    clock.clear_override()


def _store(tmp_path: Path) -> CaseStore:
    return CaseStore(path=tmp_path / "cases.jsonl")


def test_scheduler_24_48_and_expiry(tmp_path):
    store = _store(tmp_path)
    # Anchor = 2026-06-15 18:00 Chicago = 2026-06-15 23:00 UTC (CDT)
    clock.set_override(datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc))
    case = store.create(plan(offline=True), planned_spray_date="2026-06-15")
    anchor = compute_anchor(case)
    assert anchor == datetime(2026, 6, 15, 23, 0, tzinfo=timezone.utc)

    clock.set_override(anchor)
    assert tick(store)["changed_count"] == 0
    assert store.get(case.case_id).status == "PLANNED"

    clock.set_override(anchor + timedelta(hours=24))
    out = tick(store)
    assert case.case_id in out["changed"]
    c = store.get(case.case_id)
    assert c.status == "NUDGED"
    assert sum(1 for e in c.events if e["type"] in {"reminder_sent", "reminder_simulated"}) == 1

    assert tick(store)["changed_count"] == 0

    clock.set_override(anchor + timedelta(hours=48))
    tick(store)
    c = store.get(case.case_id)
    assert sum(1 for e in c.events if e["type"] in {"reminder_sent", "reminder_simulated"}) == 2

    clock.set_override(anchor + timedelta(hours=72))
    tick(store)
    c = store.get(case.case_id)
    assert c.status == "EXPIRED"


def test_tick_idempotent_same_clock_files(tmp_path):
    store = _store(tmp_path)
    clock.set_override(datetime(2026, 6, 16, 0, 0, tzinfo=timezone.utc))
    case = store.create(plan(offline=True), planned_spray_date="2026-06-15")
    tick(store)
    before = (tmp_path / "cases.jsonl").read_text(encoding="utf-8")
    tick(store)
    after = (tmp_path / "cases.jsonl").read_text(encoding="utf-8")
    assert before == after
    assert json.loads(before.strip().splitlines()[0])["case_id"] == case.case_id
