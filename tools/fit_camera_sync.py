#!/usr/bin/env python3
"""Fit camera-video time to PuttTrack Edge monotonic time from visible sync pulses."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from putttrack.vision import SyncPair, fit_camera_time_map, save_time_map  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="CSV: video_time_ns,edge_time_ns,label(optional)")
    parser.add_argument("output", type=Path)
    parser.add_argument("--max-rmse-ms", type=float, default=None)
    args = parser.parse_args()

    pairs: list[SyncPair] = []
    with args.input.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            pairs.append(
                SyncPair(
                    video_time_ns=int(row["video_time_ns"]),
                    edge_time_ns=int(row["edge_time_ns"]),
                    label=row.get("label") or "",
                )
            )
    mapping = fit_camera_time_map(pairs)
    save_time_map(args.output, mapping)
    summary = {**mapping.to_dict(), "output": str(args.output)}
    print(json.dumps(summary, indent=2, sort_keys=True))
    if args.max_rmse_ms is not None and mapping.rmse_ns > args.max_rmse_ms * 1_000_000.0:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
