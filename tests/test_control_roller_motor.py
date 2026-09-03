from __future__ import annotations

import argparse
import json
import unittest

from tools.control_roller_motor import execute, send_line, validate_args, wait_event


class FakeSerial:
    def __init__(self, replies: list[dict[str, object] | str] | None = None) -> None:
        self.writes: list[bytes] = []
        self.replies = list(replies or [])

    def write(self, data: bytes) -> int:
        self.writes.append(data)
        return len(data)

    def flush(self) -> None:
        return None

    def readline(self) -> bytes:
        if not self.replies:
            return b""
        reply = self.replies.pop(0)
        if isinstance(reply, str):
            return (reply + "\n").encode()
        return (json.dumps(reply) + "\n").encode()


def run_args(**overrides: object) -> argparse.Namespace:
    values: dict[str, object] = {
        "command": "run",
        "rpm": 30,
        "seconds": 3,
        "confirm_clear": True,
        "timeout": 0.01,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


class RollerMotorControlTests(unittest.TestCase):
    def test_run_requires_explicit_confirmation_and_bounded_values(self) -> None:
        invalid = (
            (run_args(confirm_clear=False), "confirm-clear"),
            (run_args(rpm=0), "rpm"),
            (run_args(rpm=301), "rpm"),
            (run_args(seconds=0), "seconds"),
            (run_args(seconds=31), "seconds"),
            (run_args(timeout=0), "timeout"),
        )
        for args, message in invalid:
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                validate_args(args)

    def test_probe_command_is_exact_and_requires_ok(self) -> None:
        port = FakeSerial([{"event": "motor_probe", "ok": True}])
        execute(port, argparse.Namespace(command="probe", timeout=0.01))
        self.assertEqual(port.writes, [b"motor probe\n"])

    def test_scan_command_is_read_only_and_exact(self) -> None:
        port = FakeSerial(
            [{"event": "motor_scan_started", "read_only": True},
             {"event": "motor_scan", "ok": True, "motion_ready": True,
              "baud": 115200, "address": 1}]
        )
        execute(port, argparse.Namespace(command="scan", timeout=0.01))
        self.assertEqual(port.writes, [b"motor scan\n"])

    def test_run_sequence_probes_status_and_arms_before_motion(self) -> None:
        port = FakeSerial(
            [
                {"event": "motor_probe", "ok": True},
                {"event": "motor_status", "ok": True, "stalled": False},
                {"event": "motor_armed"},
                {"event": "motor_running", "rpm": -30, "seconds": 2},
                {"event": "motor_stopped", "reason": "run_timeout",
                 "settled": True, "final_rpm": 0},
                {"event": "motor_action_ack", "action": "disable", "accepted": True},
                {"event": "motor_status", "ok": True, "rpm": 0,
                 "enabled": False, "stalled": False, "stall_protect": False},
            ]
        )
        execute(port, run_args(rpm=-30, seconds=2))
        self.assertEqual(
            port.writes,
            [
                b"motor probe\n",
                b"motor status\n",
                b"motor arm\n",
                b"motor run -30 2\n",
                b"motor status\n",
            ],
        )

    def test_run_fails_closed_if_final_status_is_not_disabled(self) -> None:
        port = FakeSerial(
            [
                {"event": "motor_probe", "ok": True},
                {"event": "motor_status", "ok": True, "stalled": False},
                {"event": "motor_armed"},
                {"event": "motor_running", "rpm": 30, "seconds": 1},
                {"event": "motor_stopped", "reason": "run_timeout",
                 "settled": True, "final_rpm": 0},
                {"event": "motor_action_ack", "action": "disable", "accepted": True},
                {"event": "motor_status", "ok": True, "rpm": 0,
                 "enabled": True, "stalled": False, "stall_protect": False},
            ]
        )
        with self.assertRaisesRegex(RuntimeError, "unsafe post-run motor state"):
            execute(port, run_args(seconds=1))
        self.assertEqual(port.writes[-1], b"motor stop\n")

    def test_run_fails_closed_if_timeout_stop_did_not_settle(self) -> None:
        port = FakeSerial(
            [
                {"event": "motor_probe", "ok": True},
                {"event": "motor_status", "ok": True, "stalled": False},
                {"event": "motor_armed"},
                {"event": "motor_running", "rpm": -120, "seconds": 1},
                {"event": "motor_stopped", "reason": "run_timeout",
                 "settled": False, "final_rpm": 16},
            ]
        )
        with self.assertRaisesRegex(RuntimeError, "did not settle"):
            execute(port, run_args(rpm=-120, seconds=1))
        self.assertEqual(port.writes[-1], b"motor stop\n")

    def test_noise_is_ignored_while_waiting_for_event(self) -> None:
        port = FakeSerial(
            [
                "not-json",
                {"event": "nfc_tag", "uid": "1234"},
                {"event": "motor_status", "ok": True},
            ]
        )
        payload = wait_event(port, "motor_status", 0.05)
        self.assertTrue(payload["ok"])

    def test_send_line_appends_one_newline(self) -> None:
        port = FakeSerial()
        send_line(port, "motor stop")
        self.assertEqual(port.writes, [b"motor stop\n"])


if __name__ == "__main__":
    unittest.main()
