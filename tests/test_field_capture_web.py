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
    capture_telemetry,
    normalized_device_status,
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
    def __init__(self, *, returncode: int = 0, stderr: str | None = None) -> None:
        self.stderr = io.StringIO(
            stderr
            or "ARMED: GO in 3\nGO: action window is 10.00 seconds\n"
            "FREEZING: keep the Ball untouched\n"
        )
        self.stdin = io.StringIO()
        self.returncode = returncode
        self.terminated = False
        self.finished = False

    def wait(self, timeout: float | None = None) -> int:
        self.finished = True
        return self.returncode

    def poll(self) -> int | None:
        return self.returncode if self.finished else None

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.terminated = True


def power_result(
    command: list[str], *, voltage_mv: int = 2_850
) -> subprocess.CompletedProcess[str]:
    mode = "research" if "research" in command else "auto"
    payload = {
        "device_id": "f383571202836e6f",
        "firmware_version": "0.1.17",
        "battery_sample_valid": True,
        "battery_voltage_mv": voltage_mv,
        "battery_soc_percent": 40,
        "battery_soc_estimated": True,
        "sensor_health": "healthy",
        "capture_safe": mode == "research",
        "mode": mode,
        "runtime_state": "active" if mode == "research" else "idle",
        "stream_rate_hz": 50 if mode == "research" else 0,
        "bmi270_spi_suspended": mode == "auto",
        "adxl367_wakeup_mode_enabled": mode == "auto",
        "sensor_error_count": 0,
    }
    return subprocess.CompletedProcess(command, 0, stdout=json.dumps(payload), stderr="")


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
        self.assertIn("battery-chart", page)
        self.assertIn("imu-chart", page)
        self.assertIn("剩余电量", page)
        self.assertIn("确认 GO 标记", page)
        self.assertIn("重新连接并继续本批次", page)
        self.assertIn("/api/capture/go-ack", page)

    def test_go_ack_is_attempt_locked_and_writes_to_capture_stdin(self) -> None:
        app = FieldCaptureApp(args())
        process = FakeProcess()
        app.current_process = process
        app._set(phase="go_ready", attempt_id=7)

        with self.assertRaisesRegex(RuntimeError, "过期"):
            app.acknowledge_go(6)
        app.acknowledge_go(7)

        self.assertEqual(process.stdin.getvalue(), "GO\n")
        app.current_process = None

    def test_device_status_requires_expected_ball_and_marks_estimated_soc(self) -> None:
        payload = json.loads(power_result(["research"]).stdout)
        status = normalized_device_status(payload, "f383571202836e6f")
        self.assertEqual(status["battery_voltage_mv"], 2_850)
        self.assertEqual(status["battery_soc_percent"], 40)
        self.assertTrue(status["battery_soc_estimated"])
        with self.assertRaisesRegex(ValueError, "设备 ID 不匹配"):
            normalized_device_status(payload, "wrong-ball")

    def test_capture_telemetry_reads_final_status_and_continuity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            capture = Path(directory) / "capture.jsonl"
            final = json.loads(power_result(["research"], voltage_mv=2_832).stdout)
            final["record_type"] = "tag_status_final"
            final["power_policy"] = final.pop("mode")
            result = {
                "record_type": "tag_capture_result",
                "status": "PASS",
                "issues": [],
            }
            capture.write_text(
                json.dumps(final) + "\n" + json.dumps(result) + "\n",
                encoding="utf-8",
            )
            status, continuity = capture_telemetry(capture, "f383571202836e6f")

        self.assertIsNotNone(status)
        self.assertIsNotNone(continuity)
        self.assertEqual(status["battery_voltage_mv"], 2_832)
        self.assertEqual(continuity["status"], "PASS")

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
                                "gyro_norm_rms_rads": 1.25,
                                "accel_norm_stdev_mps2": 0.8,
                                "sequence_gaps": 0,
                                "adxl367_clip_samples": 0,
                                "bmi270_accel_clip_samples": 0,
                                "bmi270_gyro_clip_samples": 0,
                            },
                            "provisional_diagnostic": {
                                "state": "ACTIVE_MOTION_CANDIDATE"
                            },
                        }
                    ),
                    stderr="",
                )
            return power_result(command)

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
        self.assertEqual(state["last_result"]["gyro_rms"], 1.25)
        self.assertEqual(len(state["result_history"]), 1)
        self.assertEqual(len(state["battery_history"]), 2)
        self.assertEqual(state["device_status"]["mode"], "auto")
        self.assertIn("research", commands[0])
        self.assertTrue(any(str(ANALYZE_TOOL) in command for command in commands))
        self.assertIn("auto", commands[-1])

    def test_failed_capture_is_preserved_and_same_repetition_can_retry(self) -> None:
        def failed_process(command: list[str], **unused_kwargs: object) -> FakeProcess:
            output = Path(command[command.index("--output") + 1])
            output.write_text('{"record_type":"tag_status"}\n', encoding="utf-8")
            return FakeProcess(
                returncode=1,
                stderr=(
                    "ARMED: GO in 1\n"
                    "ARMED: confirming device marker; keep waiting for GO\n"
                    "RuntimeError: pairing failed\n"
                ),
            )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app = FieldCaptureApp(
                args(output_dir=root),
                command_runner=power_result,
                popen_factory=failed_process,
            )
            app.prepare(
                {
                    "profile": "pickup_drop",
                    "count": 2,
                    "session_id": "retry-test",
                }
            )
            wait_for_phase(app, "ready")
            app.start_capture()
            state = wait_for_phase(app, "ready")
            app.close()

            canonical = root / "field-retry-test-pickup_drop-r01.jsonl"
            failed = list(root.glob("field-retry-test-pickup_drop-r01.failed-*.jsonl"))

        self.assertEqual(state["completed"], 0)
        self.assertEqual(state["failure_count"], 1)
        self.assertEqual(state["last_failure"]["repetition"], 1)
        self.assertIn("pairing failed", state["last_failure"]["detail"])
        self.assertFalse(canonical.exists())
        self.assertEqual(len(failed), 1)

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
            return power_result(command)

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
        self.assertEqual(state["device_status"]["mode"], "auto")
        self.assertEqual(len(state["battery_history"]), 2)
        self.assertEqual(len(commands), 2)
        self.assertIn("research", commands[0])
        self.assertIn("auto", commands[1])


if __name__ == "__main__":
    unittest.main()
