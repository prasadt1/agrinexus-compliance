#!/usr/bin/env python3
"""Reset demo case store and receipts.

Clears data/cases.jsonl, receipts/, and the demo clock override.
Cohort seed cases across the full ladder land in a later commit;
this script is safe to run before screenshots once seeding exists.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.clock import clear_file_override, clear_override  # noqa: E402


def reset_demo(*, seed: bool = True) -> dict:
    cases = ROOT / "data" / "cases.jsonl"
    receipts = ROOT / "receipts"
    if cases.exists():
        cases.unlink()
    cases.parent.mkdir(parents=True, exist_ok=True)
    cases.touch()
    if receipts.exists():
        shutil.rmtree(receipts)
    receipts.mkdir(parents=True, exist_ok=True)
    clear_file_override()
    clear_override()

    seeded = 0
    if seed:
        from src.seed_cohort import seed_cohort

        seeded = seed_cohort()

    return {
        "cases_path": str(cases),
        "receipts_dir": str(receipts),
        "seeded": seeded,
        "clock_cleared": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset AgriNexus Compliance demo data")
    parser.add_argument(
        "--no-seed",
        action="store_true",
        help="Only clear cases/receipts/clock; do not seed cohort",
    )
    args = parser.parse_args()
    result = reset_demo(seed=not args.no_seed)
    print(json_dumps(result))


def json_dumps(obj: dict) -> str:
    import json

    return json.dumps(obj, indent=2)


if __name__ == "__main__":
    main()
