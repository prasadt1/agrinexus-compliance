"""Copy and banned-string checks for the accountability loop UI."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.cases import CaseStore
from src.cohort import nudge_message_for_case
from src.planner import plan

BANNED = [
    "offline heuristic only",
    "replace with Bedrock",
    "demo stand-in for EventBridge",
    "day 24",
]


def test_reminder_copy_uses_hour_labels_not_day_24(tmp_path):
    store = CaseStore(path=tmp_path / "cases.jsonl")
    case = store.create(plan(offline=True), planned_spray_date="2026-08-15")
    msg24 = nudge_message_for_case(case, which="T+24")
    msg48 = nudge_message_for_case(case, which="T+48")
    assert "24-hour reminder" in msg24
    assert "48-hour reminder" in msg48
    assert "day 24" not in msg24
    assert "day 48" not in msg48

    nudged = store.simulate_reminder(case.case_id, which="T+24")
    rem = next(e for e in nudged.events if e["type"] == "reminder_sent")
    assert rem["detail"] == rem["outbound_message"]
    assert "24-hour reminder" in rem["detail"]
    assert "demo stand-in" not in rem["detail"]


def test_no_banned_developer_strings_in_src_or_web():
    roots = [ROOT / "src", ROOT / "web"]
    offenders: list[str] = []
    for root in roots:
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix not in {".py", ".js", ".html", ".css"}:
                continue
            text = path.read_text(encoding="utf-8")
            for banned in BANNED:
                if banned in text:
                    offenders.append(f"{path.relative_to(ROOT)}: {banned!r}")
    assert not offenders, "banned strings still present:\n" + "\n".join(offenders)
