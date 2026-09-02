#!/usr/bin/env python3
"""Read identity/health and capture raw PuttTrack Tag motion over BLE."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
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
    return parser


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
                    "host_received_ns": time.time_ns(),
                    **status.to_dict(),
                }
            )

            def on_motion(_: Any, data: bytearray) -> None:
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
                capture_session.observe_motion(motion)
                emit(
                    {
                        "record_type": "tag_motion",
                        "host_received_ns": time.time_ns(),
                        **motion.to_dict(),
                    }
                )

            if args.duration > 0:
                await client.start_notify(MOTION_CHARACTERISTIC_UUID, on_motion)
                await asyncio.sleep(args.duration)
                await client.stop_notify(MOTION_CHARACTERISTIC_UUID)

            final_status = parse_status(
                await client.read_gatt_char(STATUS_CHARACTERISTIC_UUID)
            )
            emit(
                {
                    "record_type": "tag_status_final",
                    "host_received_ns": time.time_ns(),
                    **final_status.to_dict(),
                }
            )
            report = capture_session.finalize(final_status)
            emit(
                {
                    "record_type": "tag_capture_result",
                    "host_received_ns": time.time_ns(),
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
    return asyncio.run(capture(args))


if __name__ == "__main__":
    raise SystemExit(main())
