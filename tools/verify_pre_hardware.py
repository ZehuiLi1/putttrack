#!/usr/bin/env python3
"""Verify software/camera/runbook readiness without claiming physical-hardware results."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
PYTHON = sys.executable
ENV = {**os.environ, "PYTHONPATH": str(SRC)}


def run(name: str, command: list[str], checks: list[dict[str, Any]]) -> None:
    result = subprocess.run(command, cwd=ROOT, env=ENV, text=True, capture_output=True, check=False)
    checks.append(
        {
            "name": name,
            "command": command,
            "returncode": result.returncode,
            "passed": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    )
    if result.returncode != 0:
        raise RuntimeError(f"{name} failed with exit code {result.returncode}")


def main() -> int:
    checks: list[dict[str, Any]] = []
    try:
        run("canonical_verifier", [PYTHON, "tools/verify.py"], checks)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            calibration = root / "calibration.json"
            time_map = root / "time_map.json"
            gt = root / "ground_truth.csv"
            run(
                "oblique_camera_calibration",
                [
                    PYTHON,
                    "tools/calibrate_ground_plane.py",
                    "configs/ground_truth/camera_oblique.example.json",
                    str(calibration),
                ],
                checks,
            )
            run(
                "camera_time_sync",
                [
                    PYTHON,
                    "tools/fit_camera_sync.py",
                    "experiments/camera_gt/fixtures/sync_pairs.example.csv",
                    str(time_map),
                ],
                checks,
            )
            run(
                "camera_gt_projection",
                [
                    PYTHON,
                    "tools/project_camera_gt.py",
                    "experiments/camera_gt/fixtures/pixel_annotations.example.csv",
                    str(calibration),
                    str(gt),
                    "--time-map",
                    str(time_map),
                ],
                checks,
            )
            rows = gt.read_text(encoding="utf-8").strip().splitlines()
            camera_outputs_ok = calibration.exists() and time_map.exists() and gt.exists() and len(rows) == 4
            checks.append(
                {
                    "name": "camera_gt_outputs",
                    "passed": camera_outputs_ok,
                    "ground_truth_rows_including_header": len(rows),
                }
            )
            if not camera_outputs_ok:
                raise RuntimeError("camera ground-truth fixture outputs are incomplete")

        required = [
            Path("docs/research/CAMERA_GROUND_TRUTH.md"),
            Path("docs/research/PRE_HARDWARE_READINESS.md"),
            Path("experiments/phase0_cs/PHYSICAL_RIG_RUNBOOK.md"),
            Path("experiments/ux_dry_run/README.md"),
            Path("scripts/ncs/build_phase0_ras.sh"),
            Path("firmware/phase0_cs/telemetry_smoke_app/CMakeLists.txt"),
        ]
        missing = [str(path) for path in required if not (ROOT / path).exists()]
        checks.append({"name": "prehardware_artifact_set", "passed": not missing, "missing": missing})
        if missing:
            raise RuntimeError(f"missing pre-hardware artifacts: {missing}")
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "hardware_validated": False,
                    "error": f"{type(exc).__name__}: {exc}",
                    "checks": checks,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 1

    print(
        json.dumps(
            {
                "status": "PASS",
                "hardware_validated": False,
                "checks_passed": sum(1 for item in checks if item.get("passed")),
                "checks": checks,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
