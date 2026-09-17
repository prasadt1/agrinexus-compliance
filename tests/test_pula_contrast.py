"""Item 2: McHenry Stryax PULA + Illinois June 20 label cutoff."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.planner import plan


def test_boone_liberty_no_pula_still_ok():
    result = plan(offline=True, pack="boone_liberty")
    assert result["status"] == "APPLY_OK"
    assert result["pula_active"] is False
    assert result["points"]["required_points"] == 3
    assert result["points"]["shortfall"] == 0
    assert result.get("label_date_cutoff") is None


def test_mchenry_stryax_label_date_block_keeps_pula_points():
    result = plan(
        offline=True,
        pack="mchenry_stryax_pula",
        planned_spray_date="2026-09-18",
    )
    assert result["product"]["epa_reg_no"] == "264-1241"
    assert result["field"]["county"] == "McHenry"
    assert result["field"]["state"] == "IL"
    assert result["pula_active"] is True
    assert result["pula_extra_points"] == 3
    # Label baseline 3 + bulletin DC125 +3 = 6; irrigated field with tracking+waterway = 3
    assert result["points"]["required_points"] == 6
    assert result["points"]["earned_points"] == 3
    assert result["points"]["shortfall"] == 3
    assert result["status"] == "LABEL_DATE_BLOCK"
    assert result["label_date_cutoff"]["blocked"] is True
    assert "June 20" in result["label_date_cutoff"]["message"] or "6/20" in result[
        "label_date_cutoff"
    ]["message"]
    assert result["recommended_additions"]
    assert result["product"]["max_wind_mph"] == 10
    assert result["product"]["min_wind_mph"] == 3
    assert result["weather"]["max_wind_mph"] == 10.0


def test_mchenry_before_cutoff_is_points_short_not_date_block():
    result = plan(
        offline=True,
        pack="mchenry_stryax_pula",
        planned_spray_date="2026-06-15",
    )
    assert result["status"] == "POINTS_SHORT"
    assert result.get("label_date_cutoff") is None
    assert result["points"]["shortfall"] == 3


def test_stryax_wind_limit_is_ten_not_fifteen():
    calm = plan(offline=True, pack="mchenry_stryax_pula", planned_spray_date="2026-06-01")
    assert calm["weather"]["weather_ok"] is True
    assert calm["weather"]["max_wind_mph"] == 10.0
    windy = plan(
        offline=True,
        pack="mchenry_stryax_pula",
        windy=True,
        planned_spray_date="2026-06-01",
    )
    assert windy["status"] == "WEATHER_BLOCK"
    assert windy["weather"]["weather_ok"] is False
    assert any("label limit" in r for r in windy["weather"]["weather_block_reasons"])
