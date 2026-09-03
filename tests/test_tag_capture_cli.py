from __future__ import annotations

import argparse
import unittest
from pathlib import Path

from putttrack.tag import MotionRecord
from tools.capture_tag_smp import (
    build_request_command,
    select_armed_window,
    validate_armed_options,
)


def args(**overrides) -> argparse.Namespace:
    values = {
        "hci_port": "/dev/fake-hci",
        "timeout": 30,
        "ble_address": None,
        "address_type": None,
        "device_name": "PuttTrack-",
        "scan_timeout": 15,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


class TagCaptureCliTests(unittest.TestCase):
    def test_name_selector_is_used_for_legacy_single_tag_capture(self) -> None:
        command = build_request_command(Path("/bin/nrfutil"), args(), 3)
        self.assertIn("--device-name", command)
        self.assertIn("PuttTrack-", command)
        self.assertIn("--scan-timeout", command)
        self.assertNotIn("--address", command)

    def test_address_selector_pins_every_request(self) -> None:
        command = build_request_command(
            Path("/bin/nrfutil"),
            args(ble_address="AA:BB:CC:DD:EE:FF", address_type="random"),
            4,
        )
        self.assertIn("--address", command)
        self.assertIn("AA:BB:CC:DD:EE:FF", command)
        self.assertIn("--address-type", command)
        self.assertIn("random", command)
        self.assertNotIn("--device-name", command)
        self.assertNotIn("--scan-timeout", command)

    def test_armed_capture_requires_a_bounded_frozen_pair(self) -> None:
        validate_armed_options(
            mode="frozen",
            armed_countdown=3.0,
            episode_seconds=10.0,
            until_enter=False,
        )
        invalid = [
            ("frozen", 3.0, None, False, "provided together"),
            ("window", 3.0, 10.0, False, "requires --mode frozen"),
            ("frozen", 3.0, 10.0, True, "cannot be combined"),
            ("frozen", 0.0, 10.0, False, "must be positive"),
            ("frozen", 8.0, 10.0, False, "must not exceed"),
        ]
        for mode, countdown, episode, until_enter, message in invalid:
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                validate_armed_options(
                    mode=mode,
                    armed_countdown=countdown,
                    episode_seconds=episode,
                    until_enter=until_enter,
                )

    def test_armed_window_excludes_setup_before_countdown(self) -> None:
        records = tuple(self._motion(index) for index in range(1_025))
        marker = records[750]
        selected = select_armed_window(
            records,
            action_marker=marker,
            pre_roll_seconds=3.0,
            episode_seconds=5.0,
        )

        self.assertEqual(selected[0].sequence, marker.sequence - 150)
        self.assertEqual(selected[-1].sequence, marker.sequence + 250)
        self.assertEqual(len(selected), 401)

    def test_armed_window_fails_if_marker_or_pre_roll_is_not_retained(self) -> None:
        records = tuple(self._motion(index) for index in range(100))
        with self.assertRaisesRegex(ValueError, "outside"):
            select_armed_window(
                records,
                action_marker=self._motion(200),
                pre_roll_seconds=1.0,
                episode_seconds=1.0,
            )
        with self.assertRaisesRegex(ValueError, "does not cover"):
            select_armed_window(
                records,
                action_marker=records[20],
                pre_roll_seconds=1.0,
                episode_seconds=1.0,
            )
        with self.assertRaisesRegex(ValueError, "post-GO"):
            select_armed_window(
                records,
                action_marker=records[80],
                pre_roll_seconds=1.0,
                episode_seconds=1.0,
            )

    @staticmethod
    def _motion(index: int) -> MotionRecord:
        return MotionRecord(
            protocol_version=1,
            sequence=1_000 + index,
            source_monotonic_us=5_000_000 + index * 20_000,
            adxl367_valid=True,
            bmi270_valid=True,
            adxl367_accel_micro_ms2=(0, 0, 9_806_650),
            bmi270_accel_micro_ms2=(0, 0, 9_806_650),
            bmi270_gyro_micro_rads=(0, 0, 0),
            sensor_error_bits=0,
        )


if __name__ == "__main__":
    unittest.main()
