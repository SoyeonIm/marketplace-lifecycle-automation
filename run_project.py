from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.analyze_experiment import analyze_experiment
from src.build_dashboard import build_dashboard
from src.build_readme_assets import build_readme_assets
from src.generate_data import generate_data
from src.pipeline import build_warehouse
from src.quality_checks import run_quality_checks


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the marketplace lifecycle campaign analytics project."
    )
    parser.add_argument("--members", type=int, default=12_000, help="Synthetic member count")
    parser.add_argument("--seed", type=int, default=42, help="Deterministic random seed")
    parser.add_argument(
        "--skip-generate",
        action="store_true",
        help="Reuse existing CSV data and rebuild only analytics outputs",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    print("1/5 Generating privacy-safe synthetic marketplace data...")
    if not args.skip_generate:
        generation = generate_data(member_count=args.members, seed=args.seed)
        print(json.dumps(generation, indent=2))
    else:
        print("Reusing existing raw CSV files.")

    print("2/5 Building the local SQL warehouse and marts...")
    build_warehouse()

    print("3/5 Running data quality and campaign safety checks...")
    quality = run_quality_checks(write_report=True)
    failed = [check for check in quality if check["status"] != "PASS"]
    print(f"{len(quality) - len(failed)}/{len(quality)} checks passed.")
    if failed:
        for check in failed:
            print(f"FAILED: {check['name']} - {check['detail']}")
        return 1

    print("4/5 Analysing experiment incrementality and guardrails...")
    metrics = analyze_experiment()
    print(
        f"Best observed variant: {metrics['decision']['best_observed_variant']} | "
        f"recommendation: {metrics['decision']['recommendation']}"
    )

    print("5/5 Building the campaign dashboard and visual assets...")
    dashboard_path = build_dashboard()
    asset_paths = build_readme_assets()
    print(f"Done. Open {dashboard_path}")
    print(f"Generated {len(asset_paths)} README visual assets.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
