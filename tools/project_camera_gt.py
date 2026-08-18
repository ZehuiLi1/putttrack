#!/usr/bin/env python3
"""Project annotated camera pixels onto the surveyed PuttTrack ground plane."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from putttrack.vision import (  # noqa: E402
    load_calibration,
    load_time_map,
    project_annotations,
    read_pixel_annotations,
    write_ground_truth,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("annotations", type=Path)
    parser.add_argument("calibration", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--time-map", type=Path, default=None)
    args = parser.parse_args()

    calibration = load_calibration(args.calibration)
    time_map = load_time_map(args.time_map) if args.time_map else None
    annotations = read_pixel_annotations(args.annotations)
    observations = project_annotations(annotations, calibration, time_map)
    write_ground_truth(args.output, observations)
    print(
        json.dumps(
            {
                "annotation_count": len(annotations),
                "ground_truth_count": len(observations),
                "camera_id": calibration.camera_id,
                "calibration_id": calibration.calibration_id,
                "time_mapped": time_map is not None,
                "output": str(args.output),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
