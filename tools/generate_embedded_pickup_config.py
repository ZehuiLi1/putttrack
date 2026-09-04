#!/usr/bin/env python3
"""Generate the MCU frozen-pickup constants from the canonical research JSON.

The generated header is intentionally simple C so firmware and offline replay
share one threshold source. This tool never edits the JSON or changes authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def render(config_path: Path) -> str:
    raw = config_path.read_bytes()
    cfg = json.loads(raw)
    sha = hashlib.sha256(raw).hexdigest()
    stationary = cfg["stationary_baseline"]
    onset = cfg["onset"]
    impulse = cfg["vertical_impulse"]
    gyro = cfg["gyro_shape"]
    return f'''/* Auto-generated from configs/research/pickup_detector_v0.json.
 * Research-only; authority=false. Regenerate with
 * tools/generate_embedded_pickup_config.py.
 */
#pragma once

#define PT_PICKUP_V0_CONFIG_SHA256 "{sha}"
#define PT_PICKUP_V0_CONFIG_HASH32 0x{sha[:8]}U
#define PT_PICKUP_V0_EXPECTED_RATE_HZ {int(cfg["expected_source_rate_hz"])}U
#define PT_PICKUP_V0_GRAVITY_MPS2 {float(cfg["gravity_mps2"]):.8g}f
#define PT_PICKUP_V0_BASELINE_SECONDS {float(cfg["required_pre_go_stationary_s"]):.8g}f
#define PT_PICKUP_V0_BASELINE_ACCEL_STDEV_MAX {float(stationary["maximum_accel_norm_stdev_mps2"]):.8g}f
#define PT_PICKUP_V0_BASELINE_GYRO_RMS_MAX {float(stationary["maximum_gyro_norm_rms_rads"]):.8g}f
#define PT_PICKUP_V0_ONSET_ACCEL_DEVIATION {float(onset["accel_norm_deviation_mps2"]):.8g}f
#define PT_PICKUP_V0_ONSET_GYRO_NORM {float(onset["gyro_norm_rads"]):.8g}f
#define PT_PICKUP_V0_ONSET_LOOKAHEAD_SAMPLES {int(onset["lookahead_samples"])}U
#define PT_PICKUP_V0_ONSET_MIN_ACTIVE_SAMPLES {int(onset["minimum_active_samples"])}U
#define PT_PICKUP_V0_IMPULSE_START_S ({float(impulse["window_start_relative_to_onset_s"]):.8g}f)
#define PT_PICKUP_V0_IMPULSE_END_S {float(impulse["window_end_relative_to_onset_s"]):.8g}f
#define PT_PICKUP_V0_IMPULSE_MIN_MPS {float(impulse["minimum_mps"]):.8g}f
#define PT_PICKUP_V0_GYRO_WINDOW_START_S {float(gyro["window_start_relative_to_onset_s"]):.8g}f
#define PT_PICKUP_V0_GYRO_WINDOW_END_S {float(gyro["window_end_relative_to_onset_s"]):.8g}f
#define PT_PICKUP_V0_GYRO_MEAN_MAX_RADS {float(gyro["maximum_mean_norm_rads"]):.8g}f
#define PT_PICKUP_V0_AXIS_CONSISTENCY_MAX {float(gyro["maximum_axis_consistency"]):.8g}f
'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/research/pickup_detector_v0.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "firmware/nrf54l15_tag_motion_demo/src/pickup_v0_generated.h"
        ),
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = render(args.config)
    if args.check:
        actual = args.output.read_text(encoding="utf-8")
        if actual != expected:
            raise SystemExit(
                "embedded pickup header is stale; run tools/generate_embedded_pickup_config.py"
            )
        print("PASS: embedded pickup header matches frozen research config")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(expected, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
