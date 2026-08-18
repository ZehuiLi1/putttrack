#!/usr/bin/env python3
"""Fit a planar image->venue XY mapping from surveyed ground-control points."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from putttrack.vision import GroundControlPoint, calibrate_ground_plane, save_calibration  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="JSON with camera_id, world_frame and points[]")
    parser.add_argument("output", type=Path, help="output calibration JSON")
    parser.add_argument("--max-rmse-m", type=float, default=None)
    parser.add_argument("--max-error-m", type=float, default=None)
    args = parser.parse_args()

    raw = json.loads(args.input.read_text(encoding="utf-8"))
    points = [GroundControlPoint.from_dict(item) for item in raw["points"]]
    calibration = calibrate_ground_plane(
        camera_id=str(raw["camera_id"]),
        world_frame=str(raw.get("world_frame", "venue_xy")),
        points=points,
        notes=str(raw.get("notes", "")),
    )
    save_calibration(args.output, calibration)

    summary = {
        "camera_id": calibration.camera_id,
        "calibration_id": calibration.calibration_id,
        "control_point_count": len(calibration.control_points),
        "rmse_m": calibration.rmse_m,
        "max_error_m": calibration.max_error_m,
        "output": str(args.output),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    if args.max_rmse_m is not None and calibration.rmse_m > args.max_rmse_m:
        return 2
    if args.max_error_m is not None and calibration.max_error_m > args.max_error_m:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
