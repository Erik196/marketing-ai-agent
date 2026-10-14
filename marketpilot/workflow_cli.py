"""Inspect CSV analytics and saved workflows without making model requests."""

import argparse
import json
import sqlite3
import sys

from marketpilot.analytics import analyze_csv
from marketpilot.storage import WorkflowStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="MarketPilot CSV analytics and saved workflows")
    commands = parser.add_subparsers(dest="command", required=True)
    analyze = commands.add_parser("analyze", help="Calculate CSV metrics without an LLM")
    analyze.add_argument("filename", help="CSV filename inside data/campaigns/")
    listing = commands.add_parser("list", help="List persisted agent runs")
    listing.add_argument("--limit", type=int, default=20)
    show = commands.add_parser("show", help="Inspect a saved run and its actual tool steps")
    show.add_argument("run_id")
    args = parser.parse_args(argv)
    try:
        if args.command == "analyze":
            result = analyze_csv(args.filename)
        elif args.command == "list":
            result = WorkflowStore().list_runs(args.limit)
        else:
            result = WorkflowStore().get_run(args.run_id)
    except (ValueError, OSError, sqlite3.Error) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
