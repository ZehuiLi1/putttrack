from __future__ import annotations

import unittest

from putttrack.motion import (
    extract_window_features,
    provisional_generic_motion_check,
    provisional_stationary_check,
)
from putttrack.tag import MotionRecord


def sample(sequence: int, *, gyro: int = 5_000, accel_z: int = 9_806_650) -> MotionRecord:
    return MotionRecord(
        protocol_version=1,
        sequence=sequence,
        source_monotonic_us=sequence * 20_000,
        adxl367_valid=True,
        bmi270_valid=True,
        adxl367_accel_micro_ms2=(0, 0, accel_z),
        bmi270_accel_micro_ms2=(0, 0, accel_z),
        bmi270_gyro_micro_rads=(gyro, 0, 0),
        sensor_error_bits=0,
    )


class MotionFeatureTests(unittest.TestCase):
    def test_stationary_window_passes_provisional_smoke_gate(self) -> None:
        records = [sample(sequence) for sequence in range(100, 161)]

        features = extract_window_features(records)
        result = provisional_stationary_check(features)

        self.assertAlmostEqual(features.observed_rate_hz, 50.0)
        self.assertEqual(features.sequence_gaps, 0)
        self.assertEqual(features.valid_fraction, 1.0)
        self.assertEqual(features.active_sample_fraction, 0.0)
        self.assertIsNone(features.first_active_offset_s)
        self.assertTrue(result.passed)
        self.assertEqual(result.state, "STATIONARY_CANDIDATE")

    def test_motion_is_not_called_stationary(self) -> None:
        records = [
            sample(sequence, gyro=400_000, accel_z=9_000_000 + (sequence % 2) * 2_000_000)
            for sequence in range(100, 161)
        ]

        result = provisional_stationary_check(extract_window_features(records))

        self.assertFalse(result.passed)
        self.assertIn("gyro_activity", result.reasons)
        self.assertIn("accel_variability", result.reasons)

    def test_clear_motion_is_generic_active_without_claiming_action_type(self) -> None:
        records = [
            sample(sequence, gyro=400_000, accel_z=9_000_000 + (sequence % 2) * 2_000_000)
            for sequence in range(100, 161)
        ]

        result = provisional_generic_motion_check(extract_window_features(records))

        self.assertTrue(result.passed)
        self.assertEqual(result.state, "ACTIVE_MOTION_CANDIDATE")
        self.assertGreater(extract_window_features(records).active_sample_fraction, 0.0)

    def test_intermediate_motion_fails_closed_in_dead_band(self) -> None:
        records = [
            sample(
                sequence,
                gyro=200_000,
                accel_z=9_000_000 + (sequence % 2) * 400_000,
            )
            for sequence in range(100, 161)
        ]

        result = provisional_generic_motion_check(extract_window_features(records))

        self.assertFalse(result.passed)
        self.assertEqual(result.state, "UNCLASSIFIED")
        self.assertEqual(result.reasons, ("motion_dead_band",))

    def test_rejects_out_of_order_source_data(self) -> None:
        with self.assertRaises(ValueError):
            extract_window_features([sample(2), sample(1)])


if __name__ == "__main__":
    unittest.main()
