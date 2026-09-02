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
    parse_motion,
    parse_status,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device-name", default="PuttTrack-Tag-v0.1")
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

    device = await BleakScanner.find_device_by_filter(
        lambda candidate, advertisement: bool(
            advertisement.local_name
            and args.device_name in advertisement.local_name
        ),
        timeout=args.scan_timeout,
    )
    if device is None:
        raise SystemExit(f"Tag containing name {args.device_name!r} was not found")

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
    output = args.output.open("x", encoding="utf-8") if args.output else None
    records = 0
    first_sequence: int | None = None
    last_sequence: int | None = None
    gaps = 0

    def emit(payload: dict[str, Any]) -> None:
        line = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        if output:
            output.write(line + "\n")
            output.flush()
        else:
            print(line)

    async with BleakClient(device) as client:
        raw_status = await client.read_gatt_char(STATUS_CHARACTERISTIC_UUID)
        status = parse_status(raw_status)
        emit({"record_type": "tag_status", "host_received_ns": time.time_ns(), **status.to_dict()})

        def on_motion(_: Any, data: bytearray) -> None:
            nonlocal records, first_sequence, last_sequence, gaps
            motion = parse_motion(data)
            if first_sequence is None:
                first_sequence = motion.sequence
            if last_sequence is not None and motion.sequence != last_sequence + 1:
                gaps += max(0, motion.sequence - last_sequence - 1)
            last_sequence = motion.sequence
            records += 1
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

        final_status = parse_status(await client.read_gatt_char(STATUS_CHARACTERISTIC_UUID))
        emit(
            {
                "record_type": "tag_status_final",
                "host_received_ns": time.time_ns(),
                **final_status.to_dict(),
            }
        )

    if output:
        output.close()
    print(
        json.dumps(
            {
                "status": "PASS",
                "motion_records": records,
                "first_sequence": first_sequence,
                "last_sequence": last_sequence,
                "sequence_gaps": gaps,
                "output": str(args.output) if args.output else None,
            },
            sort_keys=True,
        ),
        file=sys.stderr,
    )
    return 0


def main() -> int:
    args = build_parser().parse_args()
    if args.scan_timeout <= 0:
        raise SystemExit("--scan-timeout must be positive")
    if args.duration < 0:
        raise SystemExit("--duration must not be negative")
    return asyncio.run(capture(args))


if __name__ == "__main__":
    raise SystemExit(main())
