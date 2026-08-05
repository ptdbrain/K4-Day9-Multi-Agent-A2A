"""
main.py — entry point for the multi-agent E-commerce dispute resolution pipeline.

Usage:
    python main.py                    # process all cases in input/
    python main.py --case EC_001      # process a single case
    python main.py --dry-run          # validate setup without API calls
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from tqdm import tqdm

# Load .env (API key must be set here, model name is in source code)
load_dotenv()

INPUT_DIR = Path("input")
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)


def get_input_files(case_filter: str | None = None) -> list[Path]:
    files = sorted(INPUT_DIR.glob("EC_*.json"))
    if not files:
        print("[ERROR] No input files found in input/ directory.")
        print("        Waiting for organizers to provide EC_001.json … EC_050.json")
        sys.exit(1)
    if case_filter:
        files = [f for f in files if f.stem == case_filter]
        if not files:
            print(f"[ERROR] Case '{case_filter}' not found in input/")
            sys.exit(1)
    return files


def process_all(case_filter: str | None = None, dry_run: bool = False) -> None:
    from src.data_loader import DataLoader
    from src.logger import TraceLogger
    from src.agents.coordinator_agent import CoordinatorAgent

    # Load data (singleton — done once)
    db = DataLoader()
    db.load_all()

    # Open trace log (fresh run — truncate previous)
    trace = TraceLogger()
    trace.open()

    coordinator = CoordinatorAgent()
    input_files = get_input_files(case_filter)

    print(f"\n{'='*60}")
    print(f"  Multi-Agent Dispute Resolution — {len(input_files)} case(s)")
    print(f"{'='*60}\n")

    errors: list[str] = []

    for input_path in tqdm(input_files, desc="Processing cases"):
        case_id = input_path.stem
        output_path = OUTPUT_DIR / input_path.name

        try:
            with open(input_path, "r", encoding="utf-8") as f:
                case = json.load(f)

            if dry_run:
                print(f"  [DRY-RUN] Would process {case_id}")
                continue

            result = coordinator.process_case(case)

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2, default=str)

        except Exception as e:
            err_msg = f"{case_id}: {type(e).__name__}: {e}"
            errors.append(err_msg)
            print(f"\n[ERROR] {err_msg}")

    trace.close()

    print(f"\n{'='*60}")
    print(f"  Done. {len(input_files) - len(errors)} succeeded, {len(errors)} failed.")
    if errors:
        print("  Errors:")
        for e in errors:
            print(f"    - {e}")
    print(f"  Outputs >> {OUTPUT_DIR.resolve()}")
    print(f"  Trace   >> trace.jsonl")
    print(f"{'='*60}\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Multi-Agent E-commerce Dispute Resolution"
    )
    parser.add_argument(
        "--case", type=str, default=None,
        help="Process a single case (e.g. EC_001). Default: all cases."
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Validate setup without making API calls or writing outputs."
    )
    args = parser.parse_args()

    process_all(case_filter=args.case, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
