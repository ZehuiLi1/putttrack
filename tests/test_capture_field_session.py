from __future__ import annotations

import argparse
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.capture_field_session import (
    PROFILES,
    build_capture_command,
    build_power_command,
    output_path,
    run,
    validate_args,
)


def args(**overrides: object) -> argparse.Namespace:
    values: dict[str, object] = {
        "profile": "pickup_carry",
        "count": 10,
        "start_index": 1,
        "session_id": "s1",
        "output_dir": Path("runs"),
        "hci_port": "/dev/fake-hci",
        "expected_device_id": "f383571202836e6f",
        "device_name": "PuttTrack-",
        "ble_address": None,
        "address_type": None,
        "notes": None,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


class CaptureFieldSessionTests(unittest.TestCase):
    def test_capture_is_bounded_audible_and_identity_locked(self) -> None:
        command = build_capture_command(args(profile="putt_gentle"), 3)
        self.assertEqual(command[command.index("--episode-seconds") + 1], "12.0")
        self.assertEqual(command[command.index("--label") + 1], "putt_gentle")
        self.assertEqual(
            command[command.index("--expected-device-id") + 1],
            "f383571202836e6f",
        )
        self.assertIn("--audible-cue", command)
        self.assertEqual(
            command[command.index("--output") + 1],
            "runs/field-s1-putt_gentle-r03.jsonl",
        )
        self.assertNotIn("--wait-for-go-ack", command)

        web_command = build_capture_command(
            args(profile="putt_gentle"), 3, wait_for_go_ack=True
        )
        self.assertIn("--wait-for-go-ack", web_command)
        self.assertEqual(
            web_command[web_command.index("--go-ack-timeout") + 1], "20"
        )

    def test_power_commands_preserve_selector(self) -> None:
        values = args(ble_address="AA:BB:CC:DD:EE:FF", address_type="random")
        command = build_power_command(values, "research")
        self.assertIn("research", command)
        self.assertIn("--ble-address", command)
        self.assertIn("--address-type", command)
        self.assertNotIn("--device-name", command)

    def test_validation_rejects_unsafe_or_ambiguous_values(self) -> None:
        invalid = (
            (args(count=0), "count"),
            (args(start_index=0), "start-index"),
            (args(session_id="bad session"), "session-id"),
            (args(expected_device_id="1234"), "expected-device-id"),
            (args(address_type="random"), "requires"),
        )
        for values, message in invalid:
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                validate_args(values)

    def test_output_name_is_deterministic_and_existing_files_are_detectable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            values = args(output_dir=Path(directory), profile="handling")
            path = output_path(values, 2)
            self.assertEqual(path.name, "field-s1-handling-r02.jsonl")
            self.assertFalse(path.exists())
            path.touch()
            self.assertTrue(path.exists())

    def test_all_profiles_fit_retained_history(self) -> None:
        self.assertTrue(PROFILES)
        for profile in PROFILES.values():
            self.assertLessEqual(3.0 + profile.episode_seconds, 17.0)

    def test_stroke_profiles_keep_planned_counts_separate_from_truth(self) -> None:
        for name, expected in (("stroke_single_gentle", 1),
                               ("stroke_two_after_stop", 2),
                               ("stroke_second_while_rolling", 2),
                               ("stroke_one_multiple_rails", 1),
                               ("stroke_other_ball_contact", 0)):
            command = build_capture_command(args(profile=name), 1)
            notes = command[command.index("--notes") + 1]
            self.assertIn(f"planned_strokes={expected}", notes)
            self.assertIn("planned_only=true", notes)

    @patch("tools.capture_field_session.input", return_value="q")
    @patch("tools.capture_field_session.run_command", side_effect=(0, 0))
    def test_quit_without_capture_still_restores_auto(self, command, _input) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = run(args(output_dir=Path(directory)))

        self.assertEqual(result, 0)
        self.assertEqual(command.call_count, 2)
        self.assertIn("research", command.call_args_list[0].args[0])
        self.assertIn("auto", command.call_args_list[1].args[0])

    @patch("tools.capture_field_session.input", return_value="")
    @patch("tools.capture_field_session.run_command", side_effect=(0, 1, 0))
    def test_capture_failure_stops_and_restores_auto(self, command, _input) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = run(args(output_dir=Path(directory), count=2))

        self.assertEqual(result, 1)
        self.assertEqual(command.call_count, 3)
        self.assertIn("auto", command.call_args_list[-1].args[0])


if __name__ == "__main__":
    unittest.main()
