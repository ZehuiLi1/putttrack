from __future__ import annotations

import argparse
from dataclasses import replace
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
    validate_continuity,
    main,
)
from tests.test_tag_capture_session import status


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
            "pickup_config_sha256": "62c82c1a313f70912a5bb6c2f53c635fe179c537cdb3738dbc5d2a347050c8ad",
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

    def test_wrong_demo_and_detector_hash_fail_closed(self) -> None:
        for field, value in (("demo_id", "pickup_shadow_v0"), ("pickup_config_sha256", "test")):
            payload = self._payload()
            payload[field] = value
            with self.assertRaises(ValueError):
                validate_demo_payload(payload)

    def test_reboot_recovery_and_unhealthy_status_fail_closed(self) -> None:
        initial = status(capture_safe=True, sensor_health="healthy")
        validate_continuity(initial, initial)
        for changes in ({"boot_id": "1122334455667788"},
                        {"sensor_recovery_generation": 1},
                        {"capture_safe": False},
                        {"device_id": "1122334455667788"}):
            with self.assertRaises(RuntimeError):
                validate_continuity(initial, replace(initial, **changes))

    def run_mock_watcher(self, policy="auto", wait_error=False, cleanup_error=False):
        initial = status(capture_safe=True, power_policy=policy, sensor_health="healthy")
        calls = []
        def request(_nrfutil, _args, *, operation, command_id):
            calls.append((operation, command_id))
            if command_id == 24:
                # Stop the watcher after the read-only preflight probe.
                if calls.count((0, 24)) > 1:
                    raise KeyboardInterrupt()
                return self._payload()
            return {}
        def wait(_nrfutil, _args, expected):
            if expected == "research" and wait_error:
                raise RuntimeError("research transition timeout")
            if expected == "auto" and cleanup_error:
                raise RuntimeError("cleanup timeout")
            return replace(initial, power_policy=expected)
        argv = ["watch", "--ble-address", "AA:BB:CC:DD:EE:FF",
                "--expected-device-id", initial.device_id]
        with mock.patch("sys.argv", argv), \
             mock.patch("tools.watch_ball_motion_demo.Path.exists", return_value=True), \
             mock.patch("tools.watch_ball_motion_demo.find_nrfutil", return_value=Path("nrfutil")), \
             mock.patch("tools.watch_ball_motion_demo.status_from_smp", return_value=initial), \
             mock.patch("tools.watch_ball_motion_demo.request", side_effect=request), \
             mock.patch("tools.watch_ball_motion_demo.wait_for_policy", side_effect=wait):
            try:
                main()
            finally:
                self.assertIn((2, 20), calls)

    def test_cleanup_after_research_transition_timeout(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "research transition timeout"):
            self.run_mock_watcher(wait_error=True)

    def test_healthy_idle_can_pass_preflight_but_quarantine_cannot(self) -> None:
        idle = status(sensor_health="healthy", capture_safe=False, runtime_state="idle")
        validate_continuity(idle, idle, require_active=False)
        with self.assertRaises(RuntimeError):
            validate_continuity(idle, idle)
        with self.assertRaises(RuntimeError):
            validate_continuity(idle, replace(idle, sensor_health="quarantined"), require_active=False)

    def test_already_research_still_restores_auto(self) -> None:
        self.run_mock_watcher(policy="research")

    def test_cleanup_failure_is_not_successful_exit(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "failed to restore auto"):
            self.run_mock_watcher(cleanup_error=True)

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
