from __future__ import annotations

import argparse
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tools.watch_ball_motion_demo import (
    QUALITY_FLAG_NAMES,
    append_jsonl,
    build_request_command,
    display_line,
    quality_names,
    validate_demo_payload,
)


class WatchBallMotionDemoTests(unittest.TestCase):
    @staticmethod
    def _args() -> argparse.Namespace:
        return argparse.Namespace(
            hci_port="/dev/test-hci",
            timeout=30,
            ble_address="AA:BB:CC:DD:EE:FF",
            address_type="random",
            device_name="PuttTrack-",
            scan_timeout=15,
        )

    @staticmethod
    def _payload() -> dict[str, object]:
        return {
            "demo_id": "mcu_motion_demo_v0",
            "authority": False,
            "candidate_only": True,
            "state": "CARRIED_CANDIDATE",
            "state_code": 4,
            "last_event": "PICKUP_FROM_REST",
            "event_code": 1,
            "quality_flags": 0,
            "transition_count": 3,
            "event_count": 1,
            "impulse_milli_mps": 850,
            "gyro_mean_milli_rads": 2200,
            "axis_milli": 450,
            "pickup_config_sha256": "test",
            "stream_hz": 50,
        }

    def test_request_is_encrypted_pairing_and_address_locked(self) -> None:
        command = build_request_command(
            Path("/opt/nrfutil"), self._args(), operation=0, command_id=24
        )
        self.assertIn("--pair", command)
        self.assertIn("--secure-connection", command)
        self.assertEqual(command[command.index("--group-id") + 1], "64")
        self.assertEqual(command[command.index("--command-id") + 1], "24")
        self.assertEqual(
            command[command.index("--address") + 1], "AA:BB:CC:DD:EE:FF"
        )

    def test_payload_stays_non_authoritative_and_converts_units(self) -> None:
        parsed = validate_demo_payload(self._payload())
        self.assertEqual(parsed["impulse_mps"], 0.85)
        self.assertEqual(parsed["gyro_mean_rads"], 2.2)
        self.assertEqual(parsed["axis_consistency"], 0.45)
        self.assertEqual(parsed["quality_names"], ())
        self.assertIn("CARRIED_CANDIDATE", display_line(parsed))

    def test_authority_or_schema_drift_is_rejected(self) -> None:
        payload = self._payload()
        payload["authority"] = True
        with self.assertRaisesRegex(ValueError, "authority=false"):
            validate_demo_payload(payload)
        payload = self._payload()
        del payload["state"]
        with self.assertRaisesRegex(ValueError, "missing fields"):
            validate_demo_payload(payload)

    def test_quality_bits_are_human_readable(self) -> None:
        flags = sum(QUALITY_FLAG_NAMES)
        self.assertEqual(set(quality_names(flags)), set(QUALITY_FLAG_NAMES.values()))
        self.assertEqual(quality_names(0), ())
        self.assertIn("unknown_bits_0x80", quality_names(0x80))

    @mock.patch("tools.watch_ball_motion_demo.time.time_ns", return_value=123)
    def test_optional_jsonl_log_is_append_only(self, _: mock.Mock) -> None:
        parsed = validate_demo_payload(self._payload())
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "demo.jsonl"
            append_jsonl(path, parsed)
            append_jsonl(path, parsed)
            lines = path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 2)
        self.assertIn('"host_time_ns": 123', lines[0])
        self.assertIn('"authority": false', lines[0])


if __name__ == "__main__":
    unittest.main()
