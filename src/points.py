"""Deterministic mitigation point arithmetic. No ML."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MENU = ROOT / "fixtures" / "mitigation_menu.json"


@dataclass
class PointsResult:
    required: int
    earned: int
    shortfall: int
    credited: list[dict[str, Any]]
    unknown_practice_ids: list[str]
    multi_category_bonus_applied: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "required_points": self.required,
            "earned_points": self.earned,
            "shortfall": self.shortfall,
            "credited": self.credited,
            "unknown_practice_ids": self.unknown_practice_ids,
            "multi_category_bonus_applied": self.multi_category_bonus_applied,
            "layer": "deterministic",
        }


def load_menu(path: Path | None = None) -> dict[str, Any]:
    p = path or DEFAULT_MENU
    with p.open(encoding="utf-8") as f:
        return json.load(f)


def practice_index(menu: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {p["id"]: p for p in menu["practices"]}


def score_field(
    practice_ids: list[str],
    required_points: int,
    menu: dict[str, Any] | None = None,
    auto_multi_category_bonus: bool = True,
) -> PointsResult:
    """
    Sum points for known practices. Optionally add multi_category_bonus
    if the grower already spans 2+ categories and hasn't listed the bonus id.
    """
    menu = menu or load_menu()
    idx = practice_index(menu)
    credited: list[dict[str, Any]] = []
    unknown: list[str] = []
    categories: set[str] = set()
    earned = 0
    ids = list(practice_ids)

    for pid in ids:
        if pid not in idx:
            unknown.append(pid)
            continue
        prac = idx[pid]
        credited.append(
            {
                "id": pid,
                "name": prac["name"],
                "points": prac["points"],
                "category": prac["category"],
            }
        )
        earned += int(prac["points"])
        categories.add(prac["category"])

    bonus_applied = False
    bonus_id = "multi_category_bonus"
    if (
        auto_multi_category_bonus
        and bonus_id not in ids
        and len(categories - {"bonus", "general"}) >= 2
        and bonus_id in idx
    ):
        prac = idx[bonus_id]
        credited.append(
            {
                "id": bonus_id,
                "name": prac["name"],
                "points": prac["points"],
                "category": prac["category"],
                "auto": True,
            }
        )
        earned += int(prac["points"])
        bonus_applied = True

    shortfall = max(0, required_points - earned)
    return PointsResult(
        required=required_points,
        earned=earned,
        shortfall=shortfall,
        credited=credited,
        unknown_practice_ids=unknown,
        multi_category_bonus_applied=bonus_applied,
    )


def recommend_additions(
    practice_ids: list[str],
    required_points: int,
    menu: dict[str, Any] | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Greedy: suggest unused practices by points descending until shortfall closed."""
    menu = menu or load_menu()
    current = score_field(practice_ids, required_points, menu=menu)
    if current.shortfall == 0:
        return []

    owned = set(practice_ids)
    candidates = [
        p
        for p in menu["practices"]
        if p["id"] not in owned and p["id"] != "multi_category_bonus"
    ]
    candidates.sort(key=lambda p: (-int(p["points"]), p["id"]))

    picks: list[dict[str, Any]] = []
    running = list(practice_ids)
    for prac in candidates:
        if len(picks) >= limit:
            break
        running.append(prac["id"])
        nxt = score_field(running, required_points, menu=menu)
        picks.append(
            {
                "id": prac["id"],
                "name": prac["name"],
                "points": prac["points"],
                "category": prac["category"],
                "earned_after": nxt.earned,
                "shortfall_after": nxt.shortfall,
            }
        )
        if nxt.shortfall == 0:
            break
    return picks
