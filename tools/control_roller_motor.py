#!/usr/bin/env python3
"""Safely probe and control the PuttTrack Emm_V5 roller over ESP32 USB CDC."""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any, Protocol

ESPRESSIF_USB_VID = 0x303A
DEFAULT_BAUD = 115200
MAX_ABS_RPM = 300
MAX_RUN_SECONDS = 30
DISABLED_COAST_TIMEOUT_SECONDS = 2.0
DISABLED_COAST_POLL_SECONDS = 0.05


class SerialLike(Protocol):
    def write(self, data: bytes) -> int: ...
    def flush(self) -> None: ...
    def readline(self) -> bytes: ...


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--port",
        help="ESP32 USB serial port; auto-selects the sole Espressif USB device",
    )
    parser.add_argument("--timeout", type=float, default=3.0)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("probe", help="read firmware/hardware version; never moves")
    subparsers.add_parser(
        "scan", help="read-only scan of documented baud rates and addresses 1-16"
    )
    subparsers.add_parser("status", help="read bus voltage, speed, and state; never moves")
    subparsers.add_parser("stop", help="send immediate stop")
    subparsers.add_parser("disable", help="stop if needed and release motor torque")

    run = subparsers.add_parser("run", help="perform one bounded speed-mode run")
    run.add_argument("--rpm", type=int, required=True)
    run.add_argument("--seconds", type=int, required=True)
    run.add_argument(
        "--confirm-clear",
        action="store_true",
        help="confirm the guarded roller is clear and the ball is secured",
    )
    return parser


def validate_args(args: argparse.Namespace) -> None:
    if args.timeout <= 0:
        raise ValueError("--timeout must be positive")
    if args.command != "run":
        return
    if not args.confirm_clear:
        raise ValueError("run requires --confirm-clear")
    if args.rpm == 0 or abs(args.rpm) > MAX_ABS_RPM:
        raise ValueError(f"--rpm must be non-zero and within +/-{MAX_ABS_RPM}")
    if not 1 <= args.seconds <= MAX_RUN_SECONDS:
        raise ValueError(f"--seconds must be between 1 and {MAX_RUN_SECONDS}")


def discover_port(requested: str | None) -> str:
    if requested:
        return requested
    try:
        from serial.tools import list_ports
    except ImportError as exc:
        raise RuntimeError(
            "pyserial is required; install the project hardware dependency"
        ) from exc

    candidates = [
        port.device for port in list_ports.comports() if port.vid == ESPRESSIF_USB_VID
    ]
    if len(candidates) != 1:
        rendered = ", ".join(candidates) if candidates else "none"
        raise RuntimeError(
            "expected exactly one Espressif USB serial device; "
            f"found {rendered}. Pass --port explicitly."
        )
    return candidates[0]


def send_line(serial_port: SerialLike, command: str) -> None:
    serial_port.write((command + "\n").encode("ascii"))
    serial_port.flush()


def wait_event(
    serial_port: SerialLike, event: str, timeout: float
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        raw = serial_port.readline()
        if not raw:
            continue
        text = raw.decode("utf-8", errors="replace").strip()
        if not text:
            continue
        print(text)
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        if payload.get("event") == event:
            return payload
    raise TimeoutError(f"timed out waiting for {event!r}")


def require_ok(payload: dict[str, Any], event: str) -> None:
    if payload.get("ok") is not True:
        raise RuntimeError(f"{event} did not pass: {payload}")


def wait_for_safe_disabled_zero(
    serial_port: SerialLike,
    status: dict[str, Any],
    request_timeout: float,
) -> dict[str, Any]:
    """Allow bounded passive coast only after output is confirmed disabled."""
    deadline = time.monotonic() + DISABLED_COAST_TIMEOUT_SECONDS
    current = status
    while True:
        require_ok(current, "post-run motor status")
        if (
            current.get("enabled") is not False
            or current.get("stalled") is True
            or current.get("stall_protect") is True
        ):
            raise RuntimeError(f"unsafe post-run motor state: {current}")
        if current.get("rpm") == 0:
            return current
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError(f"disabled motor did not coast to zero: {current}")
        time.sleep(min(DISABLED_COAST_POLL_SECONDS, remaining))
        send_line(serial_port, "motor status")
        current = wait_event(serial_port, "motor_status", min(request_timeout, remaining))


def execute(serial_port: SerialLike, args: argparse.Namespace) -> None:
    if args.command == "probe":
        send_line(serial_port, "motor probe")
        require_ok(wait_event(serial_port, "motor_probe", args.timeout), "motor probe")
        return
    if args.command == "scan":
        send_line(serial_port, "motor scan")
        result = wait_event(serial_port, "motor_scan", max(args.timeout, 50.0))
        require_ok(result, "motor scan")
        if result.get("motion_ready") is not True:
            raise RuntimeError(
                "driver replied using a diagnostic checksum mode; set it to fixed 0x6B "
                f"before motion: {result}"
            )
        return
    if args.command == "status":
        send_line(serial_port, "motor status")
        require_ok(wait_event(serial_port, "motor_status", args.timeout), "motor status")
        return
    if args.command == "stop":
        send_line(serial_port, "motor stop")
        wait_event(serial_port, "motor_stopped", args.timeout)
        return
    if args.command == "disable":
        send_line(serial_port, "motor disable")
        wait_event(serial_port, "motor_action_ack", args.timeout)
        return

    # Motion always proves two-way communication first and then consumes a
    # one-shot arm token. Firmware independently enforces the same bounds.
    send_line(serial_port, "motor probe")
    require_ok(wait_event(serial_port, "motor_probe", args.timeout), "motor probe")
    send_line(serial_port, "motor status")
    status = wait_event(serial_port, "motor_status", args.timeout)
    require_ok(status, "motor status")
    if status.get("stalled") or status.get("stall_protect"):
        raise RuntimeError(f"motor reports a stall condition: {status}")

    send_line(serial_port, "motor arm")
    wait_event(serial_port, "motor_armed", args.timeout)
    send_line(serial_port, f"motor run {args.rpm} {args.seconds}")
    wait_event(serial_port, "motor_running", args.timeout)
    try:
        stopped = wait_event(
            serial_port, "motor_stopped", args.seconds + args.timeout + 1.0
        )
        if stopped.get("reason") != "run_timeout":
            raise RuntimeError(f"run ended unexpectedly: {stopped}")
        if stopped.get("settled") is not True or stopped.get("final_rpm") != 0:
            raise RuntimeError(f"motor did not settle after timeout stop: {stopped}")
        disabled = wait_event(serial_port, "motor_action_ack", args.timeout)
        if disabled.get("action") != "disable" or disabled.get("accepted") is not True:
            raise RuntimeError(f"post-run disable was not acknowledged: {disabled}")
        send_line(serial_port, "motor status")
        final_status = wait_event(serial_port, "motor_status", args.timeout)
        wait_for_safe_disabled_zero(serial_port, final_status, args.timeout)
    except BaseException:
        send_line(serial_port, "motor stop")
        raise


def main() -> int:
    args = build_parser().parse_args()
    try:
        validate_args(args)
        port = discover_port(args.port)
        try:
            import serial
        except ImportError as exc:
            raise RuntimeError(
                "pyserial is required; install the project hardware dependency"
            ) from exc
        with serial.Serial(port, DEFAULT_BAUD, timeout=0.1) as serial_port:
            time.sleep(0.25)
            execute(serial_port, args)
    except (RuntimeError, TimeoutError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
