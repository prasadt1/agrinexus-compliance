"""Demo / test clock — override UTC time via data/clock.json.

Production uses real time. EventBridge schedules reminders against wall clock;
this module is the local stand-in for demos and offline tests only.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CLOCK_PATH = ROOT / "data" / "clock.json"

# In-process override for unit tests (takes precedence over the file).
_override: datetime | None = None


def _parse_iso(value: str) -> datetime:
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def set_override(when: datetime | None) -> None:
    """Tests inject a fixed clock; pass None to clear."""
    global _override
    if when is None:
        _override = None
        return
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    _override = when.astimezone(timezone.utc)


def clear_override() -> None:
    set_override(None)


def clock_path(path: Path | None = None) -> Path:
    return path or DEFAULT_CLOCK_PATH


def read_file_override(path: Path | None = None) -> datetime | None:
    p = clock_path(path)
    if not p.exists():
        return None
    raw = json.loads(p.read_text(encoding="utf-8"))
    iso = raw.get("now") or raw.get("set")
    if not iso:
        return None
    return _parse_iso(str(iso))


def write_file_override(when: datetime, path: Path | None = None) -> datetime:
    p = clock_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    when = when.astimezone(timezone.utc).replace(microsecond=0)
    payload: dict[str, Any] = {"now": when.isoformat()}
    p.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return when


def clear_file_override(path: Path | None = None) -> None:
    p = clock_path(path)
    if p.exists():
        p.unlink()


def now(path: Path | None = None) -> datetime:
    if _override is not None:
        return _override
    file_now = read_file_override(path)
    if file_now is not None:
        return file_now
    return datetime.now(timezone.utc).replace(microsecond=0)


def now_iso(path: Path | None = None) -> str:
    return now(path).isoformat()


def advance_hours(hours: float, path: Path | None = None) -> datetime:
    current = now(path)
    nxt = (current + timedelta(hours=hours)).replace(microsecond=0)
    # Persist file override for demo sessions; keep in-process override in sync if set.
    write_file_override(nxt, path)
    if _override is not None:
        set_override(nxt)
    return nxt


def set_now(iso_or_dt: str | datetime, path: Path | None = None) -> datetime:
    when = iso_or_dt if isinstance(iso_or_dt, datetime) else _parse_iso(iso_or_dt)
    write_file_override(when, path)
    if _override is not None:
        set_override(when)
    return when.astimezone(timezone.utc).replace(microsecond=0)


def status(path: Path | None = None) -> dict[str, Any]:
    file_now = read_file_override(path)
    return {
        "now": now(path).isoformat(),
        "override_active": _override is not None or file_now is not None,
        "source": (
            "test_override"
            if _override is not None
            else ("file" if file_now is not None else "system")
        ),
    }
