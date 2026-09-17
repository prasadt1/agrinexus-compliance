"""Deterministic spray-window weather gate. No ML."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class WeatherSnapshot:
    wind_mph: float
    precip_inch_next_hour: float = 0.0
    source: str = "fixture"

    def as_dict(self) -> dict[str, Any]:
        return {
            "wind_mph": self.wind_mph,
            "precip_inch_next_hour": self.precip_inch_next_hour,
            "source": self.source,
            "layer": "deterministic",
        }


@dataclass
class WeatherGate:
    ok: bool
    reasons: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "weather_ok": self.ok,
            "weather_block_reasons": self.reasons,
            "layer": "deterministic",
        }


def evaluate_weather(
    snap: WeatherSnapshot,
    max_wind_mph: float,
    no_rain_hours_before: float | None = 1.0,
    min_wind_mph: float | None = None,
) -> WeatherGate:
    """
    Simple educational thresholds. Real labels may be stricter / more complex
    (inversions, droplet size, etc.) — do not treat this as legal clearance.
    """
    reasons: list[str] = []
    if min_wind_mph is not None and snap.wind_mph < float(min_wind_mph):
        reasons.append(
            f"Wind {snap.wind_mph} mph is below the label minimum "
            f"{float(min_wind_mph)} mph"
        )
    if snap.wind_mph > max_wind_mph:
        reasons.append(
            f"Wind {snap.wind_mph} mph exceeds the label limit "
            f"{max_wind_mph} mph"
        )
    # Only enforce a dry-window hours rule when the fixture states a number.
    if (
        no_rain_hours_before is not None
        and float(no_rain_hours_before) > 0
        and snap.precip_inch_next_hour > 0
    ):
        reasons.append(
            f"Precip {snap.precip_inch_next_hour} in next hour; "
            f"label asks {no_rain_hours_before}h dry window"
        )
    return WeatherGate(ok=len(reasons) == 0, reasons=reasons)


# Demo snapshots for offline CLI / tests
FIXTURE_CALM = WeatherSnapshot(wind_mph=6.0, precip_inch_next_hour=0.0, source="fixture_calm")
FIXTURE_WINDY = WeatherSnapshot(wind_mph=18.0, precip_inch_next_hour=0.0, source="fixture_windy")
