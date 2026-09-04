from __future__ import annotations

import argparse
from pathlib import Path
import tempfile
import unittest

from tools.capture_roller_run import (
    build_capture_command,
    build_motor_command,
    validate_args,
)


def args(**overrides: object) -> argparse.Namespace:
    values: dict[str, object] = {
        "hci_port": "/dev/fake-hci",
        "motor_port": "/dev/fake-motor",
        "expected_device_id": "0123456789abcdef",
        "rpm": 120,
        "seconds": 3,
        "acceleration": 20,
        "deceleration": None,
        "pre_roll_seconds": 3.0,
        "tail_seconds": 3.0,
        "output": Path("run.jsonl"),
        "label": None,
        "notes": None,
        "confirm_clear": True,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


class CaptureRollerRunTests(unittest.TestCase):
    def test_capture_window_and_motor_command_are_synchronized_by_contract(self) -> None:
        values = args()
        capture = build_capture_command(values)
        motor = build_motor_command(values)

        self.assertEqual(capture[capture.index("--episode-seconds") + 1], "6.0")
        self.assertEqual(capture[capture.index("--label") + 1], "roller_120rpm")
        self.assertIn("--confirm-clear", motor)
        self.assertEqual(motor[motor.index("--rpm") + 1], "120")
        self.assertEqual(motor[motor.index("--acceleration") + 1], "20")
        self.assertNotIn("--deceleration", motor)

    def test_rejects_unconfirmed_or_unbounded_motion(self) -> None:
        invalid = (
            (args(confirm_clear=False), "confirm-clear"),
            (args(rpm=0), "rpm"),
            (args(rpm=301), "rpm"),
            (args(seconds=0), "seconds"),
            (args(acceleration=-1), "acceleration"),
            (args(acceleration=256), "acceleration"),
            (args(deceleration=-1), "deceleration"),
            (args(deceleration=256), "deceleration"),
            (args(seconds=12), "history"),
            (args(pre_roll_seconds=0), "positive"),
        )
        for values, message in invalid:
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                validate_args(values)

    def test_optional_deceleration_is_forwarded(self) -> None:
        motor = build_motor_command(args(deceleration=80))
        self.assertEqual(motor[motor.index("--deceleration") + 1], "80")

    def test_refuses_to_overwrite_an_existing_capture(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "existing.jsonl"
            output.touch()
            with self.assertRaisesRegex(ValueError, "already exists"):
                validate_args(args(output=output))


if __name__ == "__main__":
    unittest.main()
