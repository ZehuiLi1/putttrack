#!/usr/bin/env python3
"""Read identity/health and capture raw PuttTrack Tag motion over BLE."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import select
import sys
import time
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from putttrack.tag import (  # noqa: E402
    MOTION_CHARACTERISTIC_UUID,
    STATUS_CHARACTERISTIC_UUID,
    TagCaptureSession,
    TelemetryProtocolError,
    parse_motion,
    parse_status,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device-name", default="PuttTrack-")
    parser.add_argument(
        "--ble-address",
        help="optional OS BLE address/identifier used to select one same-name Tag",
    )
    parser.add_argument(
        "--expected-device-id",
        help="stable hexadecimal Tag DEVICE_ID; capture aborts before writing if different",
    )
    parser.add_argument("--scan-timeout", type=float, default=15.0)
    parser.add_argument("--duration", type=float, default=5.0)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--label")
    parser.add_argument("--notes")
    parser.add_argument("--armed-countdown", type=float)
    parser.add_argument("--episode-seconds", type=float)
    parser.add_argument("--wait-for-go-ack", action="store_true")
    parser.add_argument("--go-ack-timeout", type=float, default=20.0)
    return parser


async def countdown(seconds: float) -> None:
    deadline = time.monotonic() + seconds
    previous = None
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return
        displayed = max(1, int(remaining + 0.999))
        if displayed != previous:
            print(f"ARMED: GO in {displayed}", file=sys.stderr, flush=True)
            previous = displayed
        await asyncio.sleep(min(remaining, 0.1))


def wait_for_go(timeout: float) -> bool:
    readable, _, _ = select.select([sys.stdin], [], [], timeout)
    return bool(readable and sys.stdin.readline().strip() == "GO")


async def capture(args: argparse.Namespace) -> int:
    try:
        from bleak import BleakClient, BleakScanner
    except ImportError as exc:
        raise SystemExit(
            "bleak is required; install the project hardware dependency in a Python >=3.11 venv"
        ) from exc

    requested_address = args.ble_address.casefold() if args.ble_address else None

    def matches(candidate: Any, advertisement: Any) -> bool:
        if requested_address is not None:
            return str(candidate.address).casefold() == requested_address
        return bool(
            advertisement.local_name and args.device_name in advertisement.local_name
        )

    device = await BleakScanner.find_device_by_filter(
        matches,
        timeout=args.scan_timeout,
    )
    if device is None:
        selector = (
            f"BLE address/identifier {args.ble_address!r}"
            if args.ble_address
            else f"name containing {args.device_name!r}"
        )
        raise SystemExit(f"Tag matching {selector} was not found")

    output = None

    def emit(payload: dict[str, Any]) -> None:
        line = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        if output:
            output.write(line + "\n")
            output.flush()
        else:
            print(line)

    try:
        async with BleakClient(device) as client:
            raw_status = await client.read_gatt_char(STATUS_CHARACTERISTIC_UUID)
            status = parse_status(raw_status)
            capture_session = TagCaptureSession(
                expected_device_id=args.expected_device_id,
            )
            capture_session.start(status)
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                output = args.output.open("x", encoding="utf-8")
            emit(
                {
                    "record_type": "tag_status",
                    "transport": "native_ble",
                    "host_received_ns": time.time_ns(),
                    "episode_label": args.label,
                    "episode_notes": args.notes,
                    **status.to_dict(),
                }
            )

            latest_motion = None

            def on_motion(_: Any, data: bytearray) -> None:
                nonlocal latest_motion
                try:
                    motion = parse_motion(data)
                except TelemetryProtocolError as exc:
                    capture_session.record_malformed_motion()
                    emit(
                        {
                            "record_type": "tag_motion_error",
                            "host_received_ns": time.time_ns(),
                            "error": str(exc),
                            "raw_hex": bytes(data).hex(),
                        }
                    )
                    return
                latest_motion = motion
                capture_session.observe_motion(motion)
                emit(
                    {
                        "record_type": "tag_motion",
                        "transport": "native_ble",
                        "host_received_ns": time.time_ns(),
                        "episode_label": args.label,
                        "episode_notes": args.notes,
                        **motion.to_dict(),
                    }
                )

            capture_seconds = (
                args.episode_seconds
                if args.armed_countdown is not None
                else args.duration
            )
            if capture_seconds > 0 or args.armed_countdown is not None:
                await client.start_notify(MOTION_CHARACTERISTIC_UUID, on_motion)
                if args.armed_countdown is not None:
                    print(
                        "ARMED: setup must already be complete; keep the Ball untouched",
                        file=sys.stderr,
                        flush=True,
                    )
                    await countdown(args.armed_countdown)
                    print(
                        "ARMED: confirming device marker; keep waiting for GO",
                        file=sys.stderr,
                        flush=True,
                    )
                    marker_deadline = time.monotonic() + 2.0
                    while latest_motion is None and time.monotonic() < marker_deadline:
                        await asyncio.sleep(0.05)
                    if latest_motion is None:
                        raise RuntimeError("native BLE stream produced no device marker")
                    emit(
                        {
                            "record_type": "tag_episode_marker",
                            "transport": "native_ble",
                            "marker_kind": "action_start",
                            "host_received_ns": time.time_ns(),
                            "episode_label": args.label,
                            "episode_notes": args.notes,
                            "source_sequence": latest_motion.sequence,
                            "source_monotonic_us": latest_motion.source_monotonic_us,
                        }
                    )
                    if args.wait_for_go_ack:
                        print(
                            "GO_READY: device marker confirmed; waiting for controller",
                            file=sys.stderr,
                            flush=True,
                        )
                        if not await asyncio.to_thread(
                            wait_for_go, args.go_ack_timeout
                        ):
                            raise RuntimeError("GO acknowledgement timed out")
                    print(
                        f"GO: action window is {capture_seconds:.2f} seconds",
                        file=sys.stderr,
                        flush=True,
                    )
                await asyncio.sleep(capture_seconds)
                if args.armed_countdown is not None:
                    print("FREEZING: keep the Ball untouched", file=sys.stderr, flush=True)
                await client.stop_notify(MOTION_CHARACTERISTIC_UUID)

            final_status = parse_status(
                await client.read_gatt_char(STATUS_CHARACTERISTIC_UUID)
            )
            emit(
                {
                    "record_type": "tag_status_final",
                    "transport": "native_ble",
                    "host_received_ns": time.time_ns(),
                    "episode_label": args.label,
                    "episode_notes": args.notes,
                    **final_status.to_dict(),
                }
            )
            report = capture_session.finalize(final_status)
            emit(
                {
                    "record_type": "tag_capture_result",
                    "transport": "native_ble",
                    "host_received_ns": time.time_ns(),
                    "episode_label": args.label,
                    "episode_notes": args.notes,
                    **report.to_dict(),
                }
            )
    finally:
        if output:
            output.close()
    summary = {
        **report.to_dict(),
        "ble_address": str(device.address),
        "output": str(args.output) if args.output else None,
    }
    print(
        json.dumps(summary, sort_keys=True),
        file=sys.stderr,
    )
    return 0 if report.passed else 1


def main() -> int:
    args = build_parser().parse_args()
    if args.scan_timeout <= 0:
        raise SystemExit("--scan-timeout must be positive")
    if args.duration < 0:
        raise SystemExit("--duration must not be negative")
    if (args.armed_countdown is None) != (args.episode_seconds is None):
        raise SystemExit(
            "--armed-countdown and --episode-seconds must be provided together"
        )
    if args.armed_countdown is not None and (
        args.armed_countdown <= 0 or args.episode_seconds <= 0
    ):
        raise SystemExit("armed countdown and episode duration must be positive")
    if args.wait_for_go_ack and args.armed_countdown is None:
        raise SystemExit("--wait-for-go-ack requires armed capture")
    if args.go_ack_timeout <= 0:
        raise SystemExit("--go-ack-timeout must be positive")
    return asyncio.run(capture(args))


if __name__ == "__main__":
    raise SystemExit(main())
