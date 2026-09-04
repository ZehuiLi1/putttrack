from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from putttrack.motion.pickup_v0 import (  # noqa: E402
    PickupDecision,
    evaluate_capture_path,
)


G = 9.80665


class PickupV0Tests(unittest.TestCase):
    def _write_capture(
        self,
        path: Path,
        *,
        mode: str,
        label: str = "pickup_carry",
        sequence_gap: bool = False,
    ) -> None:
        go_us = 2_000_000
        rows = [
            {
                "record_type": "tag_status",
                "episode_label": label,
                "device_id": "fixture-ball",
                "boot_id": "fixture-boot",
                "firmware_version": "fixture",
                "stream_rate_hz": 50,
            },
            {
                "record_type": "tag_episode_marker",
                "marker_kind": "action_start",
                "source_monotonic_us": go_us,
                "episode_label": label,
            },
            {
                "record_type": "tag_episode_window",
                "action_start_source_monotonic_us": go_us,
                "episode_label": label,
            },
        ]
        sequence = 1000
        for index in range(200):
            time_us = 500_000 + index * 20_000
            if sequence_gap and index == 100:
                sequence += 1
            accel = [0.0, 0.0, G]
            gyro = [0.0, 0.0, 0.0]
            action_time = (time_us - go_us) / 1_000_000.0
            if 0.70 <= action_time < 1.10:
                if mode == "pickup":
                    accel = [0.0, 0.0, G + 4.5]
                    phase = index % 4
                    gyro = (
                        [1.4, -1.0, 0.5]
                        if phase < 2
                        else [-1.0, 1.4, -0.5]
                    )
                elif mode == "rolling":
                    accel = [0.0, 0.0, G + 4.5]
                    gyro = [0.0, 15.0, 0.0]
                elif mode == "handling":
                    accel = [0.0, 0.0, G + 0.7]
                    gyro = [1.0 if index % 2 else -1.0, 0.4, 0.0]
                elif mode == "clipped":
                    accel = [0.0, 0.0, G + 4.5]
                    gyro = [35.0, 0.0, 0.0]
            rows.append(
                {
                    "record_type": "tag_motion",
                    "episode_label": label,
                    "protocol_version": 1,
                    "sequence": sequence,
                    "source_monotonic_us": time_us,
                    "adxl367_valid": True,
                    "bmi270_valid": True,
                    "adxl367_accel_micro_ms2": [0, 0, round(G * 1_000_000)],
                    "bmi270_accel_micro_ms2": [
                        round(value * 1_000_000) for value in accel
                    ],
                    "bmi270_gyro_micro_rads": [
                        round(value * 1_000_000) for value in gyro
                    ],
                    "sensor_error_bits": 0,
                }
            )
            sequence += 1
        rows.append(
            {"record_type": "tag_capture_result", "status": "PASS", "issues": []}
        )
        path.write_text(
            "".join(
                json.dumps(row, separators=(",", ":")) + "\n" for row in rows
            ),
            encoding="utf-8",
        )

    def _evaluate(
        self, mode: str, *, label: str = "pickup_carry", gap: bool = False
    ):
        with tempfile.TemporaryDirectory() as temp:
            capture = Path(temp) / "episode.jsonl"
            self._write_capture(
                capture, mode=mode, label=label, sequence_gap=gap
            )
            return evaluate_capture_path(
                capture,
                ROOT / "configs" / "research" / "pickup_detector_v0.json",
                ROOT
                / "configs"
                / "research"
                / "pickup_detector_v0_eval_profile.json",
                manifest_label=label,
            )

    def test_stationary_start_pickup_passes_frozen_rule(self) -> None:
        result = self._evaluate("pickup")
        self.assertEqual(result.decision, PickupDecision.PICKUP_SUSPECTED)
        self.assertFalse(result.authority)
        self.assertTrue(all(result.rule_passes.values()))
        self.assertIsNotNone(result.features)
        assert result.features is not None
        self.assertGreater(
            result.features.positive_vertical_impulse_mps or 0.0, 0.5
        )

    def test_single_axis_fast_roll_is_not_pickup(self) -> None:
        result = self._evaluate("rolling", label="putt_gentle")
        self.assertEqual(result.decision, PickupDecision.NOT_PICKUP)
        self.assertFalse(result.rule_passes["axis_consistency"])
        self.assertFalse(all(result.rule_passes.values()))

    def test_no_lift_handling_is_not_pickup(self) -> None:
        result = self._evaluate("handling", label="handling")
        self.assertEqual(result.decision, PickupDecision.NOT_PICKUP)
        self.assertFalse(result.rule_passes["positive_vertical_impulse"])

    def test_clipped_feature_window_fails_closed(self) -> None:
        result = self._evaluate("clipped")
        self.assertEqual(result.decision, PickupDecision.UNKNOWN)
        self.assertIn(
            "bmi270_gyro_clipping_inside_feature_window", result.reason_codes
        )

    def test_sequence_gap_fails_closed(self) -> None:
        result = self._evaluate("pickup", gap=True)
        self.assertEqual(result.decision, PickupDecision.UNKNOWN)
        self.assertIn("sequence_gap_or_reordering", result.reason_codes)

    def test_rolling_pickup_is_explicitly_unsupported(self) -> None:
        result = self._evaluate("pickup", label="rolling_pickup")
        self.assertEqual(result.decision, PickupDecision.UNKNOWN)
        self.assertEqual(
            result.reason_codes, ("unsupported_rolling_start_path",)
        )


if __name__ == "__main__":
    unittest.main()
