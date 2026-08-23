"""CLI: plan (deterministic / Bedrock) and interpret reply."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow `python -m src.cli` from repo root
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.interpreter import interpret
from src.planner import plan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AgriNexus compliance MVP CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_plan = sub.add_parser("plan", help="Build a compliance plan from fixtures")
    p_plan.add_argument(
        "--bedrock",
        action="store_true",
        help="Also call Bedrock to enrich the plan (default: offline deterministic)",
    )
    p_plan.add_argument(
        "--windy",
        action="store_true",
        help="Use windy weather fixture (should WEATHER_BLOCK)",
    )
    p_plan.add_argument("-o", "--out", type=Path, help="Write JSON to path")

    p_int = sub.add_parser("interpret", help="Interpret free-text confirmation")
    p_int.add_argument("text", help="Applicator reply")
    p_int.add_argument("--bedrock", action="store_true")
    p_int.add_argument("-o", "--out", type=Path)

    args = parser.parse_args(argv)

    if args.cmd == "plan":
        result = plan(offline=not args.bedrock, windy=args.windy)
    else:
        result = interpret(args.text, offline=not args.bedrock)

    text = json.dumps(result, indent=2)
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
