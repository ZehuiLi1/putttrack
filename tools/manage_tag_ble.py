#!/usr/bin/env python3
"""Inspect/control a known Tag and stage signed OTA images over native BLE.

Upload does not select, reset, or confirm an image. Test and confirm take the
explicit MCUboot image hash from image-list, never the whole-file upload hash.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from bleak import BleakClient, BleakScanner
from putttrack.tag.ble_smp import BleSmp, find_tag_device
from putttrack.tag.telemetry import (
    STATUS_CHARACTERISTIC_UUID,
    parse_status,
    status_from_smp,
)
from putttrack.tag.session import normalize_device_id


async def run(args: argparse.Namespace) -> dict:
    identity = normalize_device_id(args.device_id)
    device = await find_tag_device(
        identity, address=args.address, timeout=args.scan_timeout
    )
    if device is None:
        raise RuntimeError("Expected Tag advertisement not found")
    async with BleakClient(device, timeout=args.timeout) as client:
        status = parse_status(await client.read_gatt_char(STATUS_CHARACTERISTIC_UUID))
        if status.device_id != identity:
            raise RuntimeError("Connected device identity mismatch")
        async with BleSmp(client) as smp:
            if args.command == "status":
                return await smp.request(64, 0)
            if args.command == "images":
                return await smp.request(1, 0)
            if args.command == "upload":
                return await smp.upload(args.image.read_bytes(), progress=lambda n, total:
                                       print(f"\r{n}/{total}", file=sys.stderr, end="", flush=True))
            if args.command in ("test", "confirm"):
                image_hash = bytes.fromhex(args.hash)
                if len(image_hash) not in (32, 64):
                    raise ValueError("MCUboot image hash must be 32 or 64 bytes")
                images = (await smp.request(1, 0))["images"]
                match = next((i for i in images if i.get("hash") == image_hash), None)
                if match is None:
                    raise ValueError("Image hash is not present on the device")
                if args.command == "confirm" and not match.get("active"):
                    raise ValueError("Only the currently running image may be confirmed")
                if args.command == "test" and match.get("active"):
                    raise ValueError("Test requires an inactive image")
                return await smp.request(1, 0, {"hash": image_hash,
                                             "confirm": args.command == "confirm"}, write=True)
            if args.command == "reset":
                return await smp.request(0, 5, write=True)
            if args.command == "system-off":
                applied = status_from_smp(await smp.request(64, 0))
                if applied.system_off_supported is not True:
                    raise RuntimeError("Tag does not support System OFF")
                if applied.nfc_enabled is not True or applied.nfc_setup_error != 0:
                    raise RuntimeError(
                        "NFC is not healthy: "
                        f"enabled={applied.nfc_enabled}, "
                        f"setup_error={applied.nfc_setup_error}"
                    )
                if applied.nfc_field_present:
                    raise RuntimeError(
                        "Remove the Tag from the NFC reader before System OFF"
                    )
                if applied.system_off_pending:
                    raise RuntimeError("A System OFF request is already pending")
                acknowledgement = await smp.request(64, 23, write=True)
                if acknowledgement.get("accepted") is not True:
                    raise RuntimeError(
                        f"System OFF request was rejected: {acknowledgement}"
                    )
                return {
                    "device_id": applied.device_id,
                    "firmware_version": applied.firmware_version,
                    "boot_id_before": applied.boot_id,
                    "nfc_setup_error": applied.nfc_setup_error,
                    "battery_voltage_mv": applied.battery_voltage_mv,
                    "battery_soc_percent": applied.battery_soc_percent,
                    "acknowledgement": acknowledgement,
                    "expected_state": "system_off_after_acknowledged_delay",
                }
            acknowledgement = await smp.request(
                64,
                {"auto": 20, "research": 21, "idle": 22}[args.command],
                write=True,
            )
            expected_state = {"research": "active", "idle": "idle"}.get(
                args.command
            )
            deadline = time.monotonic() + 8.0
            while True:
                applied = status_from_smp(await smp.request(64, 0))
                if applied.power_policy == args.command and (
                    expected_state is None or applied.runtime_state == expected_state
                ):
                    return {
                        "acknowledgement": acknowledgement,
                        "mode": applied.power_policy,
                        **applied.to_dict(),
                    }
                if time.monotonic() >= deadline:
                    raise RuntimeError(
                        f"Tag did not apply mode {args.command!r}; "
                        f"last status was {applied}"
                    )
                await asyncio.sleep(0.2)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device-id", required=True)
    parser.add_argument("--address", help="Optional BLE address or macOS peripheral UUID; full device ID is still checked")
    parser.add_argument("--scan-timeout", type=float, default=15.0)
    parser.add_argument("--timeout", type=float, default=20.0)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in (
        "status",
        "images",
        "reset",
        "system-off",
        "auto",
        "research",
        "idle",
    ):
        sub.add_parser(name)
    sub.add_parser("upload").add_argument("image", type=Path)
    for name in ("test", "confirm"):
        sub.add_parser(name).add_argument("hash")
    args = parser.parse_args()
    if args.scan_timeout <= 0 or args.timeout <= 0:
        raise SystemExit("timeouts must be positive")
    result = asyncio.run(run(args))
    print(json.dumps(result, indent=2, default=lambda value: value.hex() if isinstance(value, bytes) else str(value)))


if __name__ == "__main__":
    main()
