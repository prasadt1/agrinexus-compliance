"""Item 2: DuPage Stryax PULA contrast — bulletin adds points → POINTS_SHORT."""

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


def test_dupage_stryax_pula_points_short():
    result = plan(offline=True, pack="dupage_stryax_pula")
    assert result["product"]["epa_reg_no"] == "264-1241"
    assert result["field"]["county"] == "DuPage"
    assert result["pula_active"] is True
    assert result["pula_extra_points"] == 3
    # Label baseline 3 + bulletin DC125 +3 = 6 required; modest practices earn 3
    assert result["points"]["required_points"] == 6
    assert result["points"]["earned_points"] == 3
    assert result["points"]["shortfall"] == 3
    assert result["status"] == "POINTS_SHORT"
    assert result["recommended_additions"]
    assert any("PULA" in a or "ADDITIONAL" in a for a in result["bulletin_actions"])
