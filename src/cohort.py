"""Cohort view — merge seed pilot roster with live cases from the case store."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .cases import CaseStore, ComplianceCase

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_COHORT = ROOT / "fixtures" / "cohort_boone_pilot.json"


def load_cohort_fixture(path: Path | None = None) -> dict[str, Any]:
    p = path or DEFAULT_COHORT
    with p.open(encoding="utf-8") as f:
        return json.load(f)


def _case_row(case: ComplianceCase) -> dict[str, Any]:
    plan = case.plan or {}
    field = plan.get("field") or {}
    product = plan.get("product") or {}
    return {
        "applicator_id": case.case_id,
        "case_id": case.case_id,
        "name": case.applicator_name or "Live session applicator",
        "phone": case.phone or "—",
        "field_label": field.get("name") or f"{field.get('county', '')}, {field.get('state', '')}".strip(", "),
        "status": case.status,
        "plan_status": plan.get("status"),
        "epa_reg_no": case.epa_reg_no,
        "product_name": product.get("product_name"),
        "planned_spray_date": case.planned_spray_date,
        "updated_at": case.updated_at,
        "is_seed": False,
    }


def build_cohort_summary(store: CaseStore, fixture_path: Path | None = None) -> dict[str, Any]:
    fixture = load_cohort_fixture(fixture_path)
    live = [_case_row(c) for c in store.list_cases()]
    seed = [dict(s, case_id=None) for s in fixture.get("seed_applicators") or []]

    # Live cases first (newest activity), then seed examples
    members = live + seed

    def bucket(status: str) -> int:
        return sum(1 for m in members if m.get("status") == status)

    confirmed = bucket("CONFIRMED")
    nudged = bucket("NUDGED")
    planned = bucket("PLANNED")
    total = len(members)
    follow_through_pct = round(100 * confirmed / total) if total else 0

    return {
        "cohort_id": fixture.get("cohort_id"),
        "name": fixture.get("name"),
        "county": fixture.get("county"),
        "state": fixture.get("state"),
        "season": fixture.get("season"),
        "channel": fixture.get("channel"),
        "channel_note": fixture.get("channel_note"),
        "partner": fixture.get("partner"),
        "stats": {
            "total": total,
            "confirmed": confirmed,
            "nudged": nudged,
            "planned": planned,
            "follow_through_pct": follow_through_pct,
            "live_cases": len(live),
            "seed_examples": len(seed),
        },
        "members": members,
    }


def nudge_message_for_case(case: ComplianceCase, which: str = "T+24") -> str:
    """Outbound SMS-style copy (Twilio in production)."""
    plan = case.plan or {}
    product = plan.get("product") or {}
    field = plan.get("field") or {}
    product_name = product.get("product_name") or "your product"
    reg = case.epa_reg_no or product.get("epa_reg_no") or ""
    field_bit = field.get("county") or "your field"
    when = which.replace("T+", "day ")
    return (
        f"AgriNexus Compliance ({when} reminder): Your plan for {product_name} "
        f"(EPA {reg}) at {field_bit} is on file. "
        "Did you save the Bulletins Live! bulletin, meet mitigation points, "
        "and apply within weather limits? Reply in your own words or use your secure link."
    )
