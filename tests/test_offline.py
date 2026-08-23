"""Offline unit tests — no AWS required."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT))

from src import points, weather
from src.interpreter import interpret
from src.planner import plan


def test_points_boone_field_meets_three():
    menu = json.loads((ROOT / "fixtures/mitigation_menu.json").read_text())
    field = json.loads((ROOT / "fixtures/fields/field_boone.json").read_text())
    scored = points.score_field(field["practices"], required_points=3, menu=menu)
    assert scored.earned >= 3
    assert scored.shortfall == 0


def test_points_shortfall_recommends():
    menu = json.loads((ROOT / "fixtures/mitigation_menu.json").read_text())
    scored = points.score_field(["mitigation_tracking"], required_points=3, menu=menu)
    assert scored.shortfall > 0
    adds = points.recommend_additions(
        ["mitigation_tracking"], required_points=3, menu=menu
    )
    assert adds
    assert adds[-1]["shortfall_after"] == 0 or adds[0]["points"] >= 1


def test_weather_blocks_when_windy():
    gate = weather.evaluate_weather(weather.FIXTURE_WINDY, max_wind_mph=10)
    assert gate.ok is False
    assert gate.reasons


def test_weather_ok_when_calm():
    gate = weather.evaluate_weather(weather.FIXTURE_CALM, max_wind_mph=10)
    assert gate.ok is True


def test_plan_offline_calm_apply_ok():
    result = plan(offline=True, windy=False)
    assert result["points"]["layer"] == "deterministic"
    assert result["weather"]["weather_ok"] is True
    assert result["status"] == "APPLY_OK"
    assert "Educational" in result["disclaimer"]


def test_plan_offline_windy_blocks():
    result = plan(offline=True, windy=True)
    assert result["status"] == "WEATHER_BLOCK"
    assert result["weather"]["weather_ok"] is False


def test_interpret_offline_flags_human_when_thin():
    out = interpret("ok", offline=True)
    assert out["needs_human"] is True
    assert out["layer"] == "offline_stub"
