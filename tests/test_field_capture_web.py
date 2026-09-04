from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

from tools.run_field_capture_ui import (
    ANALYZE_TOOL,
    FieldCaptureApp,
    page_for_token,
    validate_server_args,
)


def args(**overrides: object) -> argparse.Namespace:
    values: dict[str, object] = {
        "host": "127.0.0.1",
        "port": 8765,
        "hci_port": "/dev/fake-hci",
        "expected_device_id": "f383571202836e6f",
        "device_name": "PuttTrack-",
        "ble_address": None,
        "address_type": None,
        "output_dir": Path("runs"),
        "idle_timeout_seconds": 60.0,
        "no_browser": True,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


class FakeProcess:
    def __init__(self) -> None:
        self.stderr = io.StringIO(
            "ARMED: GO in 3\nGO: action window is 10.00 seconds\n"
            "FREEZING: keep the Ball untouched\n"
        )
        self.terminated = False

    def wait(self, timeout: float | None = None) -> int:
        return 0

    def poll(self) -> int | None:
        return 0

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.terminated = True


def wait_for_phase(app: FieldCaptureApp, phase: str) -> dict[str, object]:
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline:
        state = app.snapshot()
        if state["phase"] == phase:
            return state
        time.sleep(0.005)
    raise AssertionError(f"phase never became {phase}: {app.snapshot()}")


class FieldCaptureWebTests(unittest.TestCase):
    def test_page_injects_token_and_uses_safe_text_rendering(self) -> None:
        page = page_for_token("secret-token")
        self.assertNotIn("__TOKEN__", page)
        self.assertIn('const TOKEN="secret-token"', page)
        self.assertIn("textContent", page)
        self.assertNotIn("innerHTML", page)

    def test_server_rejects_non_loopback_and_invalid_timeout(self) -> None:
        for values, message in (
            (args(host="0.0.0.0"), "loopback"),
            (args(port=0), "port"),
            (args(idle_timeout_seconds=0), "idle-timeout"),
            (args(address_type="random"), "requires"),
        ):
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                validate_server_args(values)

    def test_one_capture_runs_to_completion_and_restores_auto(self) -> None:
        commands: list[list[str]] = []

        def command_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
            commands.append(command)
            if str(ANALYZE_TOOL) in command:
                return subprocess.CompletedProcess(
                    command,
                    0,
                    stdout=json.dumps(
                        {
                            "features": {
                                "sample_count": 500,
                                "gyro_norm_max_rads": 4.25,
                            },
                            "provisional_diagnostic": {
                                "state": "ACTIVE_MOTION_CANDIDATE"
                            },
                        }
                    ),
                    stderr="",
                )
            return subprocess.CompletedProcess(command, 0, stdout="{}", stderr="")

        with tempfile.TemporaryDirectory() as directory:
            app = FieldCaptureApp(
                args(output_dir=Path(directory)),
                command_runner=command_runner,
                popen_factory=lambda *unused_args, **unused_kwargs: FakeProcess(),
            )
            app.prepare(
                {
                    "profile": "pickup_carry",
                    "count": 1,
                    "session_id": "web-test",
                    "notes": "test",
                }
            )
            wait_for_phase(app, "ready")
            app.start_capture()
            state = wait_for_phase(app, "complete")
            app.close()

        self.assertEqual(state["completed"], 1)
        self.assertTrue(state["low_power"])
        self.assertEqual(state["last_result"]["samples"], 500)
        self.assertIn("research", commands[0])
        self.assertTrue(any(str(ANALYZE_TOOL) in command for command in commands))
        self.assertIn("auto", commands[-1])

    def test_existing_capture_is_rejected_before_power_change(self) -> None:
        calls = 0

        def command_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
            nonlocal calls
            calls += 1
            return subprocess.CompletedProcess(command, 0, stdout="{}", stderr="")

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "field-same-pickup_carry-r01.jsonl"
            output.touch()
            app = FieldCaptureApp(
                args(output_dir=Path(directory)), command_runner=command_runner
            )
            with self.assertRaisesRegex(ValueError, "文件已存在"):
                app.prepare(
                    {
                        "profile": "pickup_carry",
                        "count": 1,
                        "session_id": "same",
                    }
                )
            app.close()

        self.assertEqual(calls, 0)

    def test_waiting_timeout_restores_auto_without_a_capture(self) -> None:
        commands: list[list[str]] = []

        def command_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
            commands.append(command)
            return subprocess.CompletedProcess(command, 0, stdout="{}", stderr="")

        with tempfile.TemporaryDirectory() as directory:
            app = FieldCaptureApp(
                args(output_dir=Path(directory)), command_runner=command_runner
            )
            app.prepare(
                {
                    "profile": "handling",
                    "count": 5,
                    "session_id": "timeout-test",
                }
            )
            wait_for_phase(app, "ready")
            app._ready_timeout()
            state = wait_for_phase(app, "idle")
            app.close()

        self.assertTrue(state["low_power"])
        self.assertEqual(len(commands), 2)
        self.assertIn("research", commands[0])
        self.assertIn("auto", commands[1])


if __name__ == "__main__":
    unittest.main()
