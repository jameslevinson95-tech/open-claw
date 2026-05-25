#!/usr/bin/env python3
"""
Run Archiver — Preserves each pipeline run's output files for historical analysis.

Problem: The pipeline overwrites output/*.json on every run. Without archiving,
the review system has no historical data to analyze.

Solution: After each pipeline run, archive all output files into a timestamped
directory under output/archive/YYYY-MM-DD_HHMM/.

Usage:
  python3 run_archiver.py                # Archive current output files
  python3 run_archiver.py --list         # List all archived runs
  python3 run_archiver.py --load 2026-05-22_0808  # Load a specific run's data
"""
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

OUTPUT_DIR = Path("output")
ARCHIVE_DIR = OUTPUT_DIR / "archive"

# Files to archive per run
ARCHIVE_FILES = [
    "agent1_directive.json",
    "agent2_candidates.json",
    "agent2_fundamentals.json",
    "agent3_verified.json",
    "agent4_orders.json",
    "agent4a_stops.json",
    "agent5_decisions.json",
    "agent5_snapshot.json",
    "broker_fills.json",
    "preflight_macro.json",
    "screener_universe.json",
    "smart_money_mentions.json",
    "x_mentions.json",
    "tear_sheet.txt",
    "assembly_data.json",
]


def archive_run(label: str = None) -> str:
    """
    Copy current output files into a timestamped archive folder.
    Returns the archive directory path.
    """
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    if label:
        run_dir = ARCHIVE_DIR / label
    else:
        run_dir = ARCHIVE_DIR / datetime.now().strftime("%Y-%m-%d_%H%M")

    if run_dir.exists():
        # Append seconds to avoid collision
        run_dir = ARCHIVE_DIR / datetime.now().strftime("%Y-%m-%d_%H%M%S")

    run_dir.mkdir(parents=True, exist_ok=True)

    archived = []
    for fname in ARCHIVE_FILES:
        src = OUTPUT_DIR / fname
        if src.exists():
            shutil.copy2(src, run_dir / fname)
            archived.append(fname)

    # Write manifest
    manifest = {
        "archived_at": datetime.now().isoformat(),
        "files": archived,
        "run_label": run_dir.name,
    }
    with open(run_dir / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"[Archiver] Archived {len(archived)} files to {run_dir}")
    return str(run_dir)


def list_runs() -> list:
    """List all archived runs, sorted by date."""
    if not ARCHIVE_DIR.exists():
        return []

    runs = []
    for d in sorted(ARCHIVE_DIR.iterdir()):
        if d.is_dir():
            manifest_path = d / "manifest.json"
            if manifest_path.exists():
                with open(manifest_path) as f:
                    manifest = json.load(f)
                runs.append({
                    "label": d.name,
                    "path": str(d),
                    "archived_at": manifest.get("archived_at"),
                    "file_count": len(manifest.get("files", [])),
                })
            else:
                runs.append({
                    "label": d.name,
                    "path": str(d),
                    "archived_at": None,
                    "file_count": len(list(d.glob("*.json"))),
                })
    return runs


def load_run(label: str) -> dict:
    """Load all JSON files from an archived run."""
    run_dir = ARCHIVE_DIR / label
    if not run_dir.exists():
        raise FileNotFoundError(f"No archived run found: {label}")

    data = {}
    for f in run_dir.glob("*.json"):
        if f.name == "manifest.json":
            continue
        with open(f) as fh:
            try:
                data[f.stem] = json.load(fh)
            except json.JSONDecodeError:
                data[f.stem] = {"error": "invalid JSON"}

    # Load tear sheet text if present
    tear_sheet = run_dir / "tear_sheet.txt"
    if tear_sheet.exists():
        data["tear_sheet"] = tear_sheet.read_text()

    return data


def load_all_runs() -> list:
    """Load all archived runs with their data. Returns list of (label, data) tuples."""
    runs = list_runs()
    result = []
    for run in runs:
        try:
            data = load_run(run["label"])
            data["_label"] = run["label"]
            data["_archived_at"] = run.get("archived_at")
            result.append(data)
        except Exception as e:
            print(f"[Archiver] Warning: Could not load {run['label']}: {e}")
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Archive pipeline output files")
    parser.add_argument("--list", action="store_true", help="List all archived runs")
    parser.add_argument("--load", type=str, help="Load a specific archived run")
    parser.add_argument("--label", type=str, help="Custom label for this archive")
    args = parser.parse_args()

    if args.list:
        runs = list_runs()
        if not runs:
            print("No archived runs found.")
        else:
            print(f"\n{'Label':<25} {'Files':<8} {'Archived At'}")
            print("-" * 60)
            for r in runs:
                print(f"{r['label']:<25} {r['file_count']:<8} {r.get('archived_at', 'unknown')}")
    elif args.load:
        data = load_run(args.load)
        print(f"Loaded {len(data)} files from {args.load}")
        for k in sorted(data.keys()):
            print(f"  - {k}")
    else:
        archive_run(label=args.label)
