"""Reminder / expiry scheduler.

Local stand-in for EventBridge: evaluate open cases against the demo clock
and apply 24 h / 48 h reminders and 72 h expiry. Never surface that name in UI.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from .cases import CaseStore, ComplianceCase
from .clock import now
from .cohort import nudge_message_for_case

CHICAGO = ZoneInfo("America/Chicago")


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def compute_anchor(case: ComplianceCase) -> datetime:
    """Spray-date 18:00 America/Chicago when set; else created_at."""
    stored = getattr(case, "anchor_at", None)
    if stored:
        parsed = parse_iso(stored)
        if parsed:
            return parsed
    if case.planned_spray_date:
        # YYYY-MM-DD → 18:00 local
        local = datetime.fromisoformat(case.planned_spray_date + "T18:00:00").replace(
            tzinfo=CHICAGO
        )
        return local.astimezone(timezone.utc)
    created = parse_iso(case.created_at)
    if created:
        return created
    return now()


def reminder_count(case: ComplianceCase) -> int:
    if getattr(case, "nudge_count", None):
        return int(case.nudge_count or 0)
    return sum(
        1
        for e in case.events or []
        if e.get("type") in {"reminder_sent", "reminder_simulated"}
    )


def _append_reminder(case: ComplianceCase, which: str, at: datetime) -> None:
    outbound = nudge_message_for_case(case, which=which)
    count = reminder_count(case) + 1
    if hasattr(case, "nudge_count"):
        case.nudge_count = count
    case.status = "NUDGED"
    case.events.append(
        {
            "at": at.replace(microsecond=0).isoformat(),
            "type": "reminder_sent",
            "actor": "system",
            "detail": outbound,
            "data": {
                "nudge_count": count,
                "channel": "sms",
                "outbound_message": outbound,
                "sent_by": "schedule",
            },
            # Compat with current receipt / UI until rebuild
            "which": which,
            "channel": "sms",
            "outbound_message": outbound,
        }
    )


def _expire(case: ComplianceCase, at: datetime) -> None:
    case.status = "EXPIRED"
    case.events.append(
        {
            "at": at.replace(microsecond=0).isoformat(),
            "type": "expired",
            "actor": "system",
            "detail": "No reply by the 72-hour deadline.",
            "data": {},
        }
    )


def tick_case(case: ComplianceCase, clock: datetime | None = None) -> bool:
    """Apply due transitions for one case. Returns True if mutated."""
    clock = clock or now()
    if case.status in {"CONFIRMED", "EXPIRED", "BLOCKED", "VERIFIED", "NEEDS_REVIEW", "CLOSED"}:
        return False
    if case.status not in {"PLANNED", "NUDGED"}:
        return False

    # BLOCKED plans should not remind — create() will set BLOCKED later; defensive:
    plan_status = (case.plan or {}).get("status")
    if plan_status in {"WEATHER_BLOCK", "POINTS_SHORT"}:
        return False

    anchor = compute_anchor(case)
    elapsed = clock - anchor
    count = reminder_count(case)
    changed = False

    if elapsed >= timedelta(hours=72) and case.status in {"PLANNED", "NUDGED"}:
        _expire(case, clock)
        return True

    if elapsed >= timedelta(hours=48) and count < 2 and case.status in {"PLANNED", "NUDGED"}:
        # Catch up: if somehow only 0 reminders at 48h+, send second (and first if needed).
        if count < 1:
            _append_reminder(case, "T+24", anchor + timedelta(hours=24))
            changed = True
            count = reminder_count(case)
        if count < 2:
            _append_reminder(case, "T+48", anchor + timedelta(hours=48))
            changed = True
        return changed

    if elapsed >= timedelta(hours=24) and count < 1 and case.status == "PLANNED":
        _append_reminder(case, "T+24", anchor + timedelta(hours=24))
        return True

    return False


def tick(store: CaseStore, clock: datetime | None = None) -> dict[str, Any]:
    """Evaluate every open case. Idempotent at a fixed clock time."""
    clock = clock or now()
    changed_ids: list[str] = []
    for case in store.list_cases():
        if tick_case(case, clock):
            store._update(case)  # noqa: SLF001 — scheduler is a store collaborator
            changed_ids.append(case.case_id)
    return {
        "ticked": True,
        "clock": clock.replace(microsecond=0).isoformat(),
        "changed": changed_ids,
        "changed_count": len(changed_ids),
    }
