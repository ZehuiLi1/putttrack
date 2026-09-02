from __future__ import annotations

import unittest
from dataclasses import replace

from putttrack.tag import (
    MotionRecord,
    StatusRecord,
    TagCaptureSession,
    TagIdentityError,
    TelemetryProtocolError,
)


def status(**overrides) -> StatusRecord:
    values = {
        "protocol_version": 1,
        "sequence": 9,
        "uptime_ms": 1_000,
        "reset_cause": 0,
        "sensor_error_count": 0,
        "notify_drop_count": 0,
        "adxl367_ready": True,
        "bmi270_ready": True,
        "notify_active": False,
        "device_id": "0011223344556677",
        "boot_id": "8899aabbccddeeff",
        "firmware_version": "0.1.13",
    }
    values.update(overrides)
    return StatusRecord(**values)


def motion(
    sequence: int,
    source_monotonic_us: int,
    **overrides,
) -> MotionRecord:
    values = {
        "protocol_version": 1,
        "sequence": sequence,
        "source_monotonic_us": source_monotonic_us,
        "adxl367_valid": True,
        "bmi270_valid": True,
        "adxl367_accel_micro_ms2": (1, 2, 3),
        "bmi270_accel_micro_ms2": (4, 5, 6),
        "bmi270_gyro_micro_rads": (7, 8, 9),
        "sensor_error_bits": 0,
    }
    values.update(overrides)
    return MotionRecord(**values)


class TagCaptureSessionTests(unittest.TestCase):
    def test_locked_identity_contiguous_capture_passes(self) -> None:
        capture = TagCaptureSession(expected_device_id="0011223344556677")
        capture.start(status())
        capture.observe_motion(motion(10, 1_100_000))
        capture.observe_motion(motion(11, 1_120_000))

        report = capture.finalize(status(sequence=11, uptime_ms=1_130))

        self.assertTrue(report.passed)
        self.assertEqual(report.motion_records, 2)
        self.assertEqual(report.sequence_gaps, 0)
        self.assertEqual(report.device_id, "0011223344556677")

    def test_wrong_expected_device_aborts_before_capture(self) -> None:
        capture = TagCaptureSession(expected_device_id="ffeeddccbbaa9988")
        with self.assertRaisesRegex(TagIdentityError, "connected Tag is"):
            capture.start(status())

    def test_gap_invalid_sample_and_clock_regression_fail_report(self) -> None:
        capture = TagCaptureSession()
        capture.start(status())
        capture.observe_motion(motion(10, 1_100_000))
        capture.observe_motion(
            motion(
                12,
                1_090_000,
                bmi270_valid=False,
                sensor_error_bits=2,
            )
        )
        report = capture.finalize(status(sequence=12, uptime_ms=1_200))

        self.assertFalse(report.passed)
        self.assertEqual(report.sequence_gaps, 1)
        self.assertIn("motion_sequence_gap", report.issues)
        self.assertIn("motion_clock_not_increasing", report.issues)
        self.assertIn("motion_bmi270_invalid", report.issues)
        self.assertIn("motion_sensor_error_bits_nonzero", report.issues)

    def test_reboot_identity_change_and_error_counter_increase_fail(self) -> None:
        initial = status()
        capture = TagCaptureSession()
        capture.start(initial)
        capture.observe_motion(motion(10, 1_100_000))
        final = replace(
            initial,
            sequence=1,
            uptime_ms=20,
            boot_id="0123456789abcdef",
            sensor_error_count=1,
            notify_drop_count=2,
        )
        report = capture.finalize(final)

        self.assertFalse(report.passed)
        self.assertIn("boot_id_changed", report.issues)
        self.assertIn("status_uptime_regression", report.issues)
        self.assertIn("sensor_error_count_increased", report.issues)
        self.assertIn("notify_drop_count_increased", report.issues)
        self.assertEqual(report.sensor_error_delta, 1)
        self.assertEqual(report.notify_drop_delta, 2)

    def test_lifecycle_misuse_is_rejected(self) -> None:
        capture = TagCaptureSession()
        with self.assertRaises(TelemetryProtocolError):
            capture.observe_motion(motion(1, 1))
        capture.start(status())
        capture.finalize(status())
        with self.assertRaises(TelemetryProtocolError):
            capture.finalize(status())

    def test_malformed_notification_marks_capture_failed(self) -> None:
        capture = TagCaptureSession()
        capture.start(status())
        capture.record_malformed_motion()
        report = capture.finalize(status(sequence=10, uptime_ms=1_100))
        self.assertFalse(report.passed)
        self.assertIn("malformed_motion_packet", report.issues)

    def test_clipping_delta_is_reported_without_hiding_valid_transport(self) -> None:
        capture = TagCaptureSession()
        capture.start(status(adxl367_clip_count=2))
        capture.observe_motion(motion(10, 1_100_000))
        report = capture.finalize(
            status(sequence=10, uptime_ms=1_100, adxl367_clip_count=5)
        )

        self.assertTrue(report.passed)
        self.assertEqual(report.adxl367_clip_delta, 3)

    def test_uint32_motion_sequence_wrap_is_contiguous(self) -> None:
        capture = TagCaptureSession()
        capture.start(status(sequence=0xFFFFFFFE))
        capture.observe_motion(motion(0xFFFFFFFF, 1_100_000))
        capture.observe_motion(motion(0, 1_120_000))
        report = capture.finalize(status(sequence=0, uptime_ms=1_130))

        self.assertTrue(report.passed)
        self.assertEqual(report.sequence_gaps, 0)

    def test_new_health_contract_allows_recovered_past_error_history(self) -> None:
        initial = status(
            sensor_error_count=9,
            sensor_health="healthy",
            capture_safe=True,
            sensor_recovery_generation=2,
        )
        capture = TagCaptureSession()
        capture.start(initial)
        capture.observe_motion(motion(10, 1_100_000))

        report = capture.finalize(replace(initial, sequence=10, uptime_ms=1_100))

        self.assertTrue(report.passed)
        self.assertEqual(report.sensor_recovery_generation_delta, 0)

    def test_health_transition_or_recovery_during_capture_fails(self) -> None:
        initial = status(
            sensor_health="healthy",
            capture_safe=True,
            sensor_recovery_generation=2,
        )
        capture = TagCaptureSession()
        capture.start(initial)
        capture.observe_motion(motion(10, 1_100_000))

        report = capture.finalize(
            replace(
                initial,
                sequence=10,
                uptime_ms=1_100,
                sensor_health="recovering",
                capture_safe=False,
                sensor_recovery_generation=3,
            )
        )

        self.assertFalse(report.passed)
        self.assertIn("final_sensor_health_not_healthy", report.issues)
        self.assertIn("final_capture_not_safe", report.issues)
        self.assertIn("sensor_recovery_generation_increased", report.issues)
        self.assertEqual(report.sensor_recovery_generation_delta, 1)


if __name__ == "__main__":
    unittest.main()
