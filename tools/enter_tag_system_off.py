#!/usr/bin/env python3
"""Preflight and explicitly place one identified Tag into NFC-wake System OFF."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from tools.set_tag_power_mode import find_nrfutil, request
except ModuleNotFoundError:  # Direct execution adds tools/, not the repo root.
    from set_tag_power_mode import find_nrfutil, request
from putttrack.tag import status_from_smp


ENTER_SYSTEM_OFF_COMMAND_ID = 23


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--ble-address", required=True)
    result.add_argument(
        "--address-type",
        required=True,
        choices=("public", "random", "public-identity", "random-identity"),
    )
    result.add_argument("--confirm-device-id", required=True)
    result.add_argument("--hci-port", default="/dev/cu.usbmodem1101")
    result.add_argument("--timeout", type=int, default=30)
    result.add_argument("--request-retries", type=int, default=3)
    result.add_argument("--nrfutil", type=Path)
    result.add_argument(
        "--execute",
        action="store_true",
        help="send the command after preflight; omission is a read-only dry run",
    )
    return result


def validate_preflight(status: object, expected_device_id: str) -> None:
    expected = expected_device_id.lower()
    if status.device_id != expected:
        raise RuntimeError(
            f"device identity mismatch: expected {expected}, got {status.device_id}"
        )
    if status.system_off_supported is not True:
        raise RuntimeError("firmware does not advertise System OFF test support")
    if status.nfc_enabled is not True or status.nfc_setup_error != 0:
        raise RuntimeError(
            f"NFC is not healthy: enabled={status.nfc_enabled}, "
            f"setup_error={status.nfc_setup_error}"
        )
    if status.nfc_field_present:
        raise RuntimeError("remove the NFC reader before entering System OFF")
    if status.system_off_pending:
        raise RuntimeError("a System OFF request is already pending")


def main() -> int:
    args = parser().parse_args()
    if not Path(args.hci_port).exists():
        raise SystemExit(f"HCI serial port does not exist: {args.hci_port}")
    if args.request_retries <= 0:
        raise SystemExit("--request-retries must be positive")

    nrfutil = find_nrfutil(args.nrfutil)
    status = status_from_smp(
        request(nrfutil, args, operation=0, command_id=0)
    )
    validate_preflight(status, args.confirm_device_id)

    result = {
        "device_id": status.device_id,
        "firmware_version": status.firmware_version,
        "boot_id_before": status.boot_id,
        "nfc_setup_error": status.nfc_setup_error,
        "battery_sample_valid": status.battery_sample_valid,
        "battery_voltage_mv": status.battery_voltage_mv,
        "battery_soc_percent": status.battery_soc_percent,
        "battery_soc_estimated": status.battery_soc_estimated,
        "dry_run": not args.execute,
    }

    if args.execute:
        acknowledgement = request(
            nrfutil,
            args,
            operation=2,
            command_id=ENTER_SYSTEM_OFF_COMMAND_ID,
        )
        if acknowledgement.get("accepted") is not True:
            raise RuntimeError(f"System OFF request was rejected: {acknowledgement}")
        result["acknowledgement"] = acknowledgement
        result["expected_state"] = "system_off_after_acknowledged_delay"
        result["recovery"] = "approach NFC reader; press Reset if NFC wake fails"

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
