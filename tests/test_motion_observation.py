from __future__ import annotations

import unittest

from putttrack.motion import build_provisional_motion_observation
from putttrack.tag import MotionRecord, StatusRecord


class MotionObservationTests(unittest.TestCase):
    def test_builds_uncalibrated_canonical_stationary_observation(self) -> None:
        status = StatusRecord(
            protocol_version=1,
            sequence=100,
            uptime_ms=2000,
            reset_cause=2,
            sensor_error_count=0,
            notify_drop_count=0,
            adxl367_ready=True,
            bmi270_ready=True,
            notify_active=False,
            device_id="f383571202836e6f",
            boot_id="0011223344556677",
            firmware_version="0.1.5",
        )
        records = [
            MotionRecord(
                protocol_version=1,
                sequence=sequence,
                source_monotonic_us=sequence * 20_000,
                adxl367_valid=True,
                bmi270_valid=True,
                adxl367_accel_micro_ms2=(0, 0, 9_806_650),
                bmi270_accel_micro_ms2=(0, 0, 9_806_650),
                bmi270_gyro_micro_rads=(1000, 0, 0),
                sensor_error_bits=0,
            )
            for sequence in range(1, 65)
        ]

        observation = build_provisional_motion_observation(
            records,
            status,
            ball_id="ball-01",
            hole_id="H01",
            raw_window_ref="runs/stationary.jsonl",
            edge_received_ns=2_000_000_000,
        )

        self.assertEqual(observation.motion_state, "STATIONARY_CANDIDATE")
        self.assertEqual(observation.confidence, 0.0)
        self.assertFalse(observation.extensions["confidence_calibrated"])
        self.assertTrue(observation.extensions["diagnostic_only"])
        self.assertEqual(observation.source_device_id, status.device_id)
        self.assertEqual(observation.sequence, 64)
        self.assertAlmostEqual(observation.accel_mps2[2], 9.80665)

    def test_builds_generic_active_observation_without_action_claim(self) -> None:
        status = StatusRecord(
            protocol_version=1,
            sequence=100,
            uptime_ms=2000,
            reset_cause=2,
            sensor_error_count=0,
            notify_drop_count=0,
            adxl367_ready=True,
            bmi270_ready=True,
            notify_active=False,
            device_id="f383571202836e6f",
            boot_id="0011223344556677",
            firmware_version="0.1.6",
        )
        records = [
            MotionRecord(
                protocol_version=1,
                sequence=sequence,
                source_monotonic_us=sequence * 20_000,
                adxl367_valid=True,
                bmi270_valid=True,
                adxl367_accel_micro_ms2=(0, 0, 9_806_650),
                bmi270_accel_micro_ms2=(
                    0,
                    0,
                    8_000_000 + (sequence % 2) * 4_000_000,
                ),
                bmi270_gyro_micro_rads=(1_000_000, 0, 0),
                sensor_error_bits=0,
            )
            for sequence in range(1, 65)
        ]

        observation = build_provisional_motion_observation(
            records,
            status,
            ball_id="ball-01",
            hole_id="H01",
            raw_window_ref="runs/active.jsonl",
            edge_received_ns=2_000_000_000,
        )

        self.assertEqual(observation.motion_state, "ACTIVE_MOTION_CANDIDATE")
        self.assertEqual(observation.confidence, 0.0)
        self.assertEqual(
            observation.model_version,
            "provisional-generic-motion-smoke-v0",
        )
        self.assertTrue(observation.extensions["diagnostic_only"])


if __name__ == "__main__":
    unittest.main()
