"""
Compliance case store — JSONL, status-enum compatible with Dynamo later.

Statuses match BUILD-MVP.md: PLANNED | NUDGED | CONFIRMED | EXPIRED | BLOCKED
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STORE = ROOT / "data" / "cases.jsonl"

STATUSES = frozenset({"PLANNED", "NUDGED", "CONFIRMED", "EXPIRED", "BLOCKED"})


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class ComplianceCase:
    case_id: str
    status: str
    created_at: str
    updated_at: str
    field_id: str
    epa_reg_no: str
    planned_spray_date: str | None = None
    plan: dict[str, Any] = field(default_factory=dict)
    confirmation: dict[str, Any] | None = None
    events: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class CaseStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or DEFAULT_STORE
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.touch()

    def _read_all(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        if not self.path.exists():
            return rows
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
        return rows

    def _write_all(self, rows: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        body = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows)
        if body:
            body += "\n"
        self.path.write_text(body, encoding="utf-8")

    def create(
        self,
        plan: dict[str, Any],
        planned_spray_date: str | None = None,
    ) -> ComplianceCase:
        now = _utc_now()
        # Demo keeps PLANNED even on weather/points short so the confirm loop stays visible.
        # BLOCKED / EXPIRED reserved for later Dynamo-compatible transitions.
        case = ComplianceCase(
            case_id=str(uuid.uuid4()),
            status="PLANNED",
            created_at=now,
            updated_at=now,
            field_id=(plan.get("field") or {}).get("field_id") or "unknown",
            epa_reg_no=(plan.get("product") or {}).get("epa_reg_no") or "unknown",
            planned_spray_date=planned_spray_date,
            plan=plan,
            confirmation=None,
            events=[
                {
                    "at": now,
                    "type": "planned",
                    "detail": f"Plan status={plan.get('status')}",
                }
            ],
        )
        rows = self._read_all()
        rows.append(case.as_dict())
        self._write_all(rows)
        return case

    def get(self, case_id: str) -> ComplianceCase | None:
        for row in self._read_all():
            if row.get("case_id") == case_id:
                return ComplianceCase(**row)
        return None

    def list_cases(self) -> list[ComplianceCase]:
        return [ComplianceCase(**row) for row in self._read_all()]

    def _update(self, case: ComplianceCase) -> ComplianceCase:
        case.updated_at = _utc_now()
        rows = self._read_all()
        found = False
        for i, row in enumerate(rows):
            if row.get("case_id") == case.case_id:
                rows[i] = case.as_dict()
                found = True
                break
        if not found:
            raise KeyError(f"case not found: {case.case_id}")
        self._write_all(rows)
        return case

    def simulate_reminder(self, case_id: str, which: str = "T+24") -> ComplianceCase:
        """
        Demo stand-in for EventBridge T+24 / T+48.
        Flips PLANNED → NUDGED and appends a visible event for the receipt.
        """
        case = self.get(case_id)
        if case is None:
            raise KeyError(f"case not found: {case_id}")
        if case.status in {"CONFIRMED", "EXPIRED"}:
            raise ValueError(f"cannot nudge case in status {case.status}")

        now = _utc_now()
        label = which if which in {"T+24", "T+48"} else "T+24"
        case.status = "NUDGED"
        case.events.append(
            {
                "at": now,
                "type": "reminder_simulated",
                "detail": f"Simulated {label} confirm-or-remind (demo stand-in for EventBridge)",
                "which": label,
            }
        )
        return self._update(case)

    def confirm(
        self,
        case_id: str,
        confirmation: dict[str, Any],
    ) -> ComplianceCase:
        case = self.get(case_id)
        if case is None:
            raise KeyError(f"case not found: {case_id}")

        now = _utc_now()
        case.confirmation = confirmation
        if confirmation.get("needs_human"):
            # Stay NUDGED or PLANNED but record; do not auto-confirm
            case.events.append(
                {
                    "at": now,
                    "type": "confirm_needs_human",
                    "detail": confirmation.get("summary") or "Interpreter flagged needs_human",
                }
            )
        else:
            case.status = "CONFIRMED"
            case.events.append(
                {
                    "at": now,
                    "type": "confirmed",
                    "detail": confirmation.get("summary") or "Free-text confirmation recorded",
                }
            )
        return self._update(case)
