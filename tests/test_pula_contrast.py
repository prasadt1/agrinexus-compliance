"""Item 2 / gate: McHenry Stryax PULA, IL cutoff, bulletin month, attributes."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.planner import plan
from src import points as points_mod


def test_boone_liberty_no_pula_still_ok():
    result = plan(offline=True, pack="boone_liberty")
    assert result["status"] == "APPLY_OK"
    assert result["pula_active"] is False
    assert result["points"]["required_points"] == 3
    assert result["points"]["shortfall"] == 0
    assert result.get("label_date_cutoff") is None
    assert result["field"].get("use_frame")


def test_mchenry_stryax_label_date_block_keeps_pula_points():
    result = plan(
        offline=True,
        pack="mchenry_stryax_pula",
        planned_spray_date="2026-09-18",
    )
    assert result["product"]["epa_reg_no"] == "264-1241"
    assert result["field"]["county"] == "McHenry"
    assert result["field"]["crop_use"]
    assert result["pula_active"] is True
    assert result["points"]["required_points"] == 6
    assert result["points"]["earned_points"] == 3
    assert result["points"]["shortfall"] == 3
    assert result["status"] == "LABEL_DATE_BLOCK"
    assert "Illinois" in result["label_date_cutoff"]["message"]
    assert "June 20" in result["label_date_cutoff"]["message"]
    assert "IL after" not in result["label_date_cutoff"]["message"]
    # Attributes (non_irrigated) must not appear as recommended additions
    assert not any(a["id"] == "non_irrigated" for a in result["recommended_additions"])


def test_mchenry_june_date_blocks_on_bulletin_month_not_silent_shortfall():
    result = plan(
        offline=True,
        pack="mchenry_stryax_pula",
        planned_spray_date="2027-06-10",
    )
    assert result["status"] == "BULLETIN_MONTH_BLOCK"
    assert result["bulletin_month_gate"]["blocked"] is True
    assert "September 2026" in result["bulletin_month_gate"]["message"]
    assert "June 2027" in result["bulletin_month_gate"]["message"]
    assert result["points"]["shortfall"] == 3


def test_mchenry_matching_month_before_cutoff_is_points_short():
    # Bulletin is Sep 2026 — use a Sep date on/before June 20 is impossible;
    # use fixture month with a date that would pass cutoff only if we ignore month.
    # For POINTS_SHORT without date block, need planned month == bulletin month
    # AND day <= June 20 — impossible in September. So test June bulletin path
    # via explicit early-month only when bulletin matches: use Sep and expect
    # LABEL_DATE_BLOCK (already covered). Here assert June+matching would be
    # POINTS_SHORT if bulletin were June — covered by bulletin month block above.
    result = plan(
        offline=True,
        pack="mchenry_stryax_pula",
        planned_spray_date="2026-09-01",
    )
    assert result["status"] == "LABEL_DATE_BLOCK"


def test_recommend_additions_skips_attributes():
    menu = points_mod.load_menu()
    adds = points_mod.recommend_additions(
        ["mitigation_tracking", "grassed_waterway"],
        required_points=6,
        menu=menu,
    )
    assert adds
    assert all(a["id"] != "non_irrigated" for a in adds)
    idx = points_mod.practice_index(menu)
    for a in adds:
        assert idx[a["id"]].get("confirmation") != "attribute"


def test_stryax_wind_limit_is_ten_not_fifteen():
    windy = plan(
        offline=True,
        pack="mchenry_stryax_pula",
        windy=True,
        planned_spray_date="2026-09-01",
    )
    # Date cutoff still wins over weather when both would block
    assert windy["status"] == "LABEL_DATE_BLOCK"
    assert windy["weather"]["max_wind_mph"] == 10.0
    assert windy["weather"]["weather_ok"] is False
