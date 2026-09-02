#!/usr/bin/env python3
"""Analyze a manifest of research-ball Tag captures without connected hardware."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from putttrack.motion.dataset import (  # noqa: E402
    analyze_dataset,
    build_quality_report,
    read_capture,
)
from putttrack.motion.reporting import write_episode_svg  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--no-svg",
        action="store_true",
        help="skip per-episode SVG plots",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    dataset_id, analyses = analyze_dataset(args.manifest)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    summary_json = args.output_dir / "dataset_summary.json"
    summary_json.write_text(
        json.dumps(
            {
                "dataset_id": dataset_id,
                "episodes": [item.to_dict() for item in analyses],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    rows = [item.to_flat_dict() for item in analyses]
    summary_csv = args.output_dir / "dataset_summary.csv"
    with summary_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    quality = build_quality_report(dataset_id, analyses)
    quality_json = args.output_dir / "quality_report.json"
    quality_json.write_text(
        json.dumps(quality, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    if not args.no_svg:
        plot_dir = args.output_dir / "plots"
        for analysis in analyses:
            capture = read_capture(Path(analysis.capture_path))
            subtitle_parts = [analysis.metadata.label, analysis.quality_status]
            if analysis.metadata.core_revision:
                subtitle_parts.append(f"core={analysis.metadata.core_revision}")
            if analysis.metadata.surface:
                subtitle_parts.append(f"surface={analysis.metadata.surface}")
            write_episode_svg(
                plot_dir / f"{analysis.metadata.episode_id}.svg",
                capture.records,
                title=analysis.metadata.episode_id,
                subtitle=" | ".join(subtitle_parts),
            )

    print(
        json.dumps(
            {
                "status": "PASS" if quality["quality_status_counts"]["FAIL"] == 0 else "FAIL",
                "dataset_id": dataset_id,
                "episodes": len(analyses),
                "output_dir": str(args.output_dir),
                "quality_status_counts": quality["quality_status_counts"],
                "note": "offline analysis only; no motion-class semantic thresholds are inferred",
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if quality["quality_status_counts"]["FAIL"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
