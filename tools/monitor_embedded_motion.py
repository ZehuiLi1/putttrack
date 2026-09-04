#!/usr/bin/env python3
"""Live console monitor for the nRF54L15 embedded-motion demo service."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys
import time

from putttrack.tag.motion_evidence import (
    MOTION_EVIDENCE_CHARACTERISTIC_UUID,
    parse_motion_evidence,
)


async def run(address: str, output: Path | None) -> None:
    try:
        from bleak import BleakClient
    except ImportError as exc:  # pragma: no cover - hardware optional dependency
        raise SystemExit("bleak is required: pip install '.[hardware]'") from exc

    handle = output.open("a", encoding="utf-8") if output else None

    def on_packet(_: object, data: bytearray) -> None:
        evidence = parse_motion_evidence(data)
        payload = {
            "host_time_ns": time.time_ns(),
            **evidence.to_dict(),
        }
        events = ",".join(evidence.events) or "-"
        quality = ",".join(evidence.quality) or "OK"
        print(
            f"seq={evidence.source_sequence:>8} "
            f"state={evidence.motion_state:<10} "
            f"confidence={evidence.confidence:0.3f} "
            f"events={events:<28} quality={quality} "
            f"tee_epoch={evidence.tee_arm_epoch}"
        )
        if handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")
            handle.flush()

    try:
        async with BleakClient(address) as client:
            print(f"connected: {address}")
            initial = await client.read_gatt_char(MOTION_EVIDENCE_CHARACTERISTIC_UUID)
            on_packet(None, initial)
            await client.start_notify(MOTION_EVIDENCE_CHARACTERISTIC_UUID, on_packet)
            print("monitoring Motion Evidence; Ctrl+C to stop")
            while True:
                await asyncio.sleep(3600)
    finally:
        if handle:
            handle.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--address", required=True, help="BLE address / platform device identifier")
    parser.add_argument("--output", type=Path, help="optional append-only JSONL log")
    args = parser.parse_args()
    try:
        asyncio.run(run(args.address, args.output))
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
