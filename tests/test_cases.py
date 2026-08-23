"""Case store + reminder simulation tests."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.cases import CaseStore
from src.planner import plan
from src.receipt import build_receipt_payload, build_receipt_files


def test_create_nudge_confirm_and_receipt(tmp_path):
    store = CaseStore(path=tmp_path / "cases.jsonl")
    result = plan(offline=True, windy=False)
    case = store.create(result, planned_spray_date="2026-04-15")
    assert case.status == "PLANNED"
    assert case.events[0]["type"] == "planned"

    nudged = store.simulate_reminder(case.case_id, which="T+24")
    assert nudged.status == "NUDGED"
    assert any(e["type"] == "reminder_simulated" for e in nudged.events)
    assert any(e.get("which") == "T+24" for e in nudged.events)

    confirmed = store.confirm(
        case.case_id,
        {
            "bulletin_saved": True,
            "applied": True,
            "needs_human": False,
            "confidence": 0.8,
            "summary": "printed bulletin and sprayed",
            "layer": "offline_stub",
            "raw_text": "Printed bulletin and sprayed at 7am",
        },
    )
    assert confirmed.status == "CONFIRMED"

    payload = build_receipt_payload(confirmed)
    assert payload["reminder_events"]
    assert payload["reminder_events"][0]["which"] == "T+24"
    assert payload["status"] == "CONFIRMED"

    paths = build_receipt_files(confirmed, out_dir=tmp_path / "receipts")
    assert Path(paths["pdf"]).exists()
    assert Path(paths["json"]).exists()
    assert Path(paths["pdf"]).stat().st_size > 500


def test_cohort_summary_includes_seed_and_live(tmp_path):
    from src.cases import CaseStore
    from src.cohort import build_cohort_summary
    from src.planner import plan

    store = CaseStore(path=tmp_path / "cases.jsonl")
    case = store.create(
        plan(offline=True),
        planned_spray_date="2026-08-15",
        applicator_name="Test Pilot",
        phone="+1 (515) 555-0199",
    )
    summary = build_cohort_summary(store)
    assert summary["stats"]["seed_examples"] >= 3
    assert summary["stats"]["live_cases"] >= 1
    assert summary["stats"]["total"] == summary["stats"]["seed_examples"] + summary["stats"]["live_cases"]
    assert any(m.get("case_id") == case.case_id for m in summary["members"])


def test_cannot_nudge_confirmed(tmp_path):
    store = CaseStore(path=tmp_path / "cases.jsonl")
    case = store.create(plan(offline=True), planned_spray_date=None)
    store.confirm(
        case.case_id,
        {
            "needs_human": False,
            "summary": "done",
            "bulletin_saved": True,
            "applied": True,
            "layer": "offline_stub",
            "raw_text": "Printed bulletin and sprayed carefully today",
        },
    )
    try:
        store.simulate_reminder(case.case_id)
        assert False, "expected ValueError"
    except ValueError:
        pass
