"""
Compliance case store — JSONL, status-enum compatible with Dynamo later.

Statuses (BUILD-MVP base + ladder extension):
  PLANNED | BLOCKED | NUDGED | CONFIRMED | VERIFIED | NEEDS_REVIEW | EXPIRED | CLOSED
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STORE = ROOT / "data" / "cases.jsonl"

STATUSES = frozenset(
    {
        "PLANNED",
        "BLOCKED",
        "NUDGED",
        "CONFIRMED",
        "VERIFIED",
        "NEEDS_REVIEW",
        "EXPIRED",
        "CLOSED",
    }
)

TERMINAL = frozenset({"CLOSED"})
CONFIRMABLE = frozenset({"PLANNED", "NUDGED"})


class ConflictError(ValueError):
    """Illegal transition — maps to HTTP 409."""


def _utc_now() -> str:
    from .clock import now_iso

    return now_iso()


def _anchor_iso(planned_spray_date: str | None, created_at: str) -> str:
    from types import SimpleNamespace

    from .scheduler import compute_anchor

    tmp = SimpleNamespace(
        anchor_at=None,
        planned_spray_date=planned_spray_date,
        created_at=created_at,
    )
    return compute_anchor(tmp).replace(microsecond=0).isoformat()


@dataclass
class ComplianceCase:
    case_id: str
    status: str
    created_at: str
    updated_at: str
    field_id: str
    epa_reg_no: str
    planned_spray_date: str | None = None
    applicator_name: str | None = None
    phone: str | None = None
    plan: dict[str, Any] = field(default_factory=dict)
    confirmation: dict[str, Any] | None = None
    events: list[dict[str, Any]] = field(default_factory=list)
    anchor_at: str | None = None
    nudge_count: int = 0
    verification: dict[str, Any] | None = None
    review: dict[str, Any] | None = None
    outcome: str | None = None
    closed_at: str | None = None
    receipt_sha256: str | None = None
    is_example: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _row_to_case(row: dict[str, Any]) -> ComplianceCase:
    """Backward-compatible load for rows written before applicator fields existed."""
    allowed = {f.name for f in fields(ComplianceCase)}
    filtered = {k: v for k, v in row.items() if k in allowed}
    return ComplianceCase(**filtered)


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

    def _require(self, case_id: str) -> ComplianceCase:
        case = self.get(case_id)
        if case is None:
            raise KeyError(f"case not found: {case_id}")
        return case

    def _reject_if_closed(self, case: ComplianceCase) -> None:
        if case.status == "CLOSED":
            raise ConflictError("This case is closed and cannot be changed.")

    def create(
        self,
        plan: dict[str, Any],
        planned_spray_date: str | None = None,
        applicator_name: str | None = None,
        phone: str | None = None,
        is_example: bool = False,
    ) -> ComplianceCase:
        now = _utc_now()
        plan_status = plan.get("status")
        blocked = plan_status in {
            "WEATHER_BLOCK",
            "POINTS_SHORT",
            "LABEL_DATE_BLOCK",
        }
        status = "BLOCKED" if blocked else "PLANNED"
        event_type = "blocked" if blocked else "planned"
        anchor_at = _anchor_iso(planned_spray_date, now)
        case = ComplianceCase(
            case_id=str(uuid.uuid4()),
            status=status,
            created_at=now,
            updated_at=now,
            field_id=(plan.get("field") or {}).get("field_id") or "unknown",
            epa_reg_no=(plan.get("product") or {}).get("epa_reg_no") or "unknown",
            planned_spray_date=planned_spray_date,
            applicator_name=applicator_name,
            phone=phone,
            plan=plan,
            confirmation=None,
            anchor_at=anchor_at,
            nudge_count=0,
            is_example=bool(is_example),
            events=[
                {
                    "at": now,
                    "type": event_type,
                    "actor": "system",
                    "detail": f"Plan status={plan_status}",
                    "data": {"plan_status": plan_status},
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
                return _row_to_case(row)
        return None

    def list_cases(self) -> list[ComplianceCase]:
        return [_row_to_case(row) for row in self._read_all()]

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
        """Manual nudge — prefer scheduler.tick in demos.

        Code comment only: temporary path until all callers use the clock + tick.
        """
        from .cohort import nudge_message_for_case

        case = self._require(case_id)
        self._reject_if_closed(case)
        if case.status not in CONFIRMABLE:
            raise ConflictError(f"cannot nudge case in status {case.status}")

        now = _utc_now()
        label = which if which in {"T+24", "T+48"} else "T+24"
        case.status = "NUDGED"
        case.nudge_count = int(case.nudge_count or 0) + 1
        outbound = nudge_message_for_case(case, which=label)
        case.events.append(
            {
                "at": now,
                "type": "reminder_sent",
                "actor": "partner",
                "detail": outbound,
                "data": {
                    "nudge_count": case.nudge_count,
                    "channel": "sms",
                    "outbound_message": outbound,
                    "sent_by": "partner",
                },
                "which": label,
                "channel": "sms",
                "outbound_message": outbound,
            }
        )
        return self._update(case)

    def confirm(
        self,
        case_id: str,
        confirmation: dict[str, Any],
        *,
        mode: str = "free_text",
    ) -> ComplianceCase:
        case = self._require(case_id)
        self._reject_if_closed(case)
        if case.status not in CONFIRMABLE:
            raise ConflictError(
                f"Cannot confirm from status {case.status}. "
                "Only planned or reminded cases accept a reply."
            )

        now = _utc_now()
        raw = confirmation.get("raw_text") or confirmation.get("checklist") or confirmation
        case.confirmation = confirmation
        case.status = "CONFIRMED"
        case.events.append(
            {
                "at": now,
                "type": "reply_received",
                "actor": "applicator",
                "detail": confirmation.get("summary") or "Reply recorded",
                "data": {
                    "channel": "sms" if mode == "free_text" else "secure_link",
                    "mode": mode,
                    "raw": raw,
                },
            }
        )
        case.events.append(
            {
                "at": now,
                "type": "interpreted",
                "actor": "system",
                "detail": confirmation.get("summary") or "Interpretation recorded",
                "data": {
                    "layer": confirmation.get("layer"),
                    "interpreter": {
                        k: confirmation.get(k)
                        for k in (
                            "bulletin_saved",
                            "applied",
                            "weather_respected",
                            "wind_mph_reported",
                            "practices",
                            "contradictions",
                            "needs_human",
                            "confidence",
                            "summary",
                        )
                        if k in confirmation
                    },
                },
            }
        )
        return self._update(case)

    def apply_verification(
        self,
        case_id: str,
        verification: dict[str, Any],
        next_status: str,
    ) -> ComplianceCase:
        case = self._require(case_id)
        self._reject_if_closed(case)
        if case.status != "CONFIRMED":
            raise ConflictError(
                f"Verification runs after confirm; status is {case.status}."
            )
        if next_status not in {"VERIFIED", "NEEDS_REVIEW"}:
            raise ValueError(f"invalid verification status {next_status}")
        now = _utc_now()
        case.verification = verification
        case.status = next_status
        case.events.append(
            {
                "at": now,
                "type": "verified" if next_status == "VERIFIED" else "needs_review",
                "actor": "system",
                "detail": verification.get("summary")
                or (
                    "Verified against plan"
                    if next_status == "VERIFIED"
                    else "Needs partner review"
                ),
                "data": {"items": verification.get("items") or []},
            }
        )
        return self._update(case)

    def review(
        self,
        case_id: str,
        *,
        decision: str,
        note: str,
        actor: str = "partner",
    ) -> ComplianceCase:
        case = self._require(case_id)
        self._reject_if_closed(case)
        if case.status != "NEEDS_REVIEW":
            raise ConflictError("Only cases that need review can be reviewed.")
        note = (note or "").strip()
        if not note:
            raise ValueError("A partner note is required.")
        if decision not in {"accept", "unverified"}:
            raise ValueError("decision must be accept or unverified")

        now = _utc_now()
        case.review = {
            "decision": decision,
            "note": note,
            "at": now,
            "actor": actor,
        }
        case.events.append(
            {
                "at": now,
                "type": "reviewed",
                "actor": actor,
                "detail": note,
                "data": {"decision": decision, "note": note},
            }
        )
        if decision == "accept":
            case.status = "VERIFIED"
            return self._update(case)
        self._update(case)
        return self.close(case_id, outcome="unverified")

    def replan(
        self,
        case_id: str,
        plan: dict[str, Any],
        planned_spray_date: str | None = None,
    ) -> ComplianceCase:
        case = self._require(case_id)
        self._reject_if_closed(case)
        if case.status != "BLOCKED":
            raise ConflictError("Only blocked cases can be replanned.")
        now = _utc_now()
        case.plan = plan
        if planned_spray_date is not None:
            case.planned_spray_date = planned_spray_date
            case.anchor_at = _anchor_iso(planned_spray_date, case.created_at)
        plan_status = plan.get("status")
        case.events.append(
            {
                "at": now,
                "type": "replanned",
                "actor": "applicator",
                "detail": f"Replanned; plan status={plan_status}",
                "data": {"plan_status": plan_status},
            }
        )
        if plan_status == "APPLY_OK":
            case.status = "PLANNED"
        else:
            case.status = "BLOCKED"
        return self._update(case)

    def close(self, case_id: str, *, outcome: str | None = None) -> ComplianceCase:
        case = self._require(case_id)
        self._reject_if_closed(case)

        if outcome is None:
            if case.status == "VERIFIED":
                outcome = "verified"
            elif case.status == "EXPIRED":
                outcome = "expired"
            else:
                raise ConflictError(
                    f"Cannot close from status {case.status} without an outcome."
                )
        if outcome not in {"verified", "unverified", "expired"}:
            raise ValueError(f"invalid outcome {outcome}")
        if outcome == "verified" and case.status not in {"VERIFIED", "NEEDS_REVIEW"}:
            # accept path already moved to VERIFIED; allow close from VERIFIED only
            if case.status != "VERIFIED":
                raise ConflictError("Verified close requires a verified case.")
        if outcome == "expired" and case.status != "EXPIRED":
            raise ConflictError("Expired close requires an expired case.")

        now = _utc_now()
        from .receipt import build_receipt_files, receipt_sha256_for_case

        case.outcome = outcome
        case.closed_at = now
        case.status = "CLOSED"
        case.events.append(
            {
                "at": now,
                "type": "closed",
                "actor": "partner",
                "detail": f"Closed ({outcome})",
                "data": {"outcome": outcome},
            }
        )
        sha = receipt_sha256_for_case(case)
        case.receipt_sha256 = sha
        build_receipt_files(case)
        return self._update(case)
