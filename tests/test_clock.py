"""Demo clock unit tests."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import clock
from src.cases import CaseStore
from src.planner import plan


def setup_function():
    clock.clear_override()


def teardown_function():
    clock.clear_override()


def test_clock_override_drives_case_timestamps(tmp_path):
    clock_file = tmp_path / "clock.json"
    fixed = datetime(2026, 6, 15, 18, 0, tzinfo=timezone.utc)
    clock.set_override(fixed)
    store = CaseStore(path=tmp_path / "cases.jsonl")
    case = store.create(plan(offline=True), planned_spray_date="2026-06-15")
    assert case.created_at.startswith("2026-06-15T18:00:00")
    clock.advance_hours(24, path=clock_file)
    # In-process override also advanced
    nudged = store.simulate_reminder(case.case_id, which="T+24")
    rem = next(e for e in nudged.events if e["type"] == "reminder_sent")
    assert rem["at"].startswith("2026-06-16T18:00:00")


def test_demo_reset_clears_cases(tmp_path, monkeypatch):
    from scripts import demo_reset

    monkeypatch.setattr(demo_reset, "ROOT", tmp_path)
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "cases.jsonl").write_text('{"case_id":"x"}\n', encoding="utf-8")
    (tmp_path / "receipts").mkdir()
    (tmp_path / "receipts" / "x.pdf").write_text("pdf", encoding="utf-8")
    result = demo_reset.reset_demo(seed=False)
    assert (tmp_path / "data" / "cases.jsonl").read_text(encoding="utf-8") == ""
    assert not (tmp_path / "receipts" / "x.pdf").exists()
    assert result["seeded"] == 0
    assert result["clock_cleared"] is True
    assert result["clock"]["override_active"] is False
