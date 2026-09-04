#!/usr/bin/env python3
"""Arm and read the nRF54L15 Pickup V0 MCU shadow evaluator over BLE SMP."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from putttrack.tag import (  # noqa: E402
    pickup_shadow_arm_from_smp,
    pickup_shadow_result_from_smp,
    status_from_smp,
)

try:  # pragma: no cover - import shape differs for module/script execution
    from tools.set_tag_power_mode import find_nrfutil, request
except ModuleNotFoundError:  # pragma: no cover
    from set_tag_power_mode import find_nrfutil, request


PICKUP_SHADOW_ARM_COMMAND = 24
PICKUP_SHADOW_RESULT_COMMAND = 25
POWER_RESEARCH_COMMAND = 21
POWER_AUTO_COMMAND = 20


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument(
        "--expect",
        choices=("PICKUP_SUSPECTED", "NOT_PICKUP", "UNKNOWN"),
        help="fail if the final shadow decision differs",
    )
    result.add_argument("--expected-device-id", required=True)
    result.add_argument("--device-name", default="PuttTrack-")
    result.add_argument("--ble-address")
    result.add_argument(
        "--address-type",
        choices=("public", "random", "public-identity", "random-identity"),
    )
    result.add_argument("--hci-port", default="/dev/cu.usbmodem101")
    result.add_argument("--scan-timeout", type=int, default=15)
    result.add_argument("--timeout", type=int, default=30)
    result.add_argument("--request-retries", type=int, default=5)
    result.add_argument("--baseline-seconds", type=float, default=1.5)
    result.add_argument("--observation-seconds", type=float, default=4.2)
    result.add_argument("--nrfutil", type=Path)
    result.add_argument("--keep-research", action="store_true")
    return result


def canonical_sha256(path: Path) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_identity(status, expected_device_id: str) -> None:
    expected = expected_device_id.strip().lower()
    try:
        expected_bytes = bytes.fromhex(expected)
    except ValueError as exc:
        raise ValueError("--expected-device-id must be hexadecimal") from exc
    if not expected_bytes:
        raise ValueError("--expected-device-id must not be empty")
    if status.device_id != expected:
        raise RuntimeError(
            f"connected Tag identity {status.device_id} does not match {expected}"
        )


def main() -> int:
    args = parser().parse_args()
    if not Path(args.hci_port).exists():
        raise SystemExit(f"HCI serial port does not exist: {args.hci_port}")
    if args.address_type and not args.ble_address:
        raise SystemExit("--address-type requires --ble-address")
    if args.request_retries <= 0:
        raise SystemExit("--request-retries must be positive")
    if args.baseline_seconds < 1.1:
        raise SystemExit("--baseline-seconds must be at least 1.1")
    if args.observation_seconds < 4.0:
        raise SystemExit("--observation-seconds must be at least 4.0")

    nrfutil = find_nrfutil(args.nrfutil)
    expected_hash = canonical_sha256(
        ROOT / "configs" / "research" / "pickup_detector_v0.json"
    )
    status = status_from_smp(request(nrfutil, args, operation=0, command_id=0))
    validate_identity(status, args.expected_device_id)
    if status.pickup_shadow_supported is not True:
        raise RuntimeError(
            f"Tag firmware {status.firmware_version} has no Pickup V0 shadow support"
        )

    restored = False
    try:
        request(
            nrfutil,
            args,
            operation=2,
            command_id=POWER_RESEARCH_COMMAND,
        )
        deadline = time.monotonic() + 8.0
        while time.monotonic() < deadline:
            status = status_from_smp(
                request(nrfutil, args, operation=0, command_id=0)
            )
            validate_identity(status, args.expected_device_id)
            if (
                status.power_policy == "research"
                and status.runtime_state == "active"
                and status.capture_safe is True
            ):
                break
            time.sleep(0.2)
        else:
            raise RuntimeError(f"Tag did not become capture-safe: {status}")

        print(
            f"保持球静止 {args.baseline_seconds:.1f} 秒……",
            file=sys.stderr,
            flush=True,
        )
        time.sleep(args.baseline_seconds)
        arm = pickup_shadow_arm_from_smp(
            request(
                nrfutil,
                args,
                operation=2,
                command_id=PICKUP_SHADOW_ARM_COMMAND,
            )
        )
        if not arm.accepted:
            raise RuntimeError(f"MCU refused shadow arm: error={arm.error}")
        print(
            "\aGO：现在执行动作；结果只记录为 shadow evidence。",
            file=sys.stderr,
            flush=True,
        )
        time.sleep(args.observation_seconds)
        result = pickup_shadow_result_from_smp(
            request(
                nrfutil,
                args,
                operation=0,
                command_id=PICKUP_SHADOW_RESULT_COMMAND,
            )
        )
        if result.generation != arm.generation or (
            result.go_source_monotonic_us != arm.go_source_monotonic_us
        ):
            raise RuntimeError("shadow result does not belong to the armed attempt")
        if result.detector_sha256 != expected_hash:
            raise RuntimeError(
                "MCU detector hash does not match the repository frozen config"
            )
        if result.authority:
            raise RuntimeError("MCU shadow result unexpectedly claimed authority")
        if result.decision == "PENDING":
            raise RuntimeError("MCU shadow result remained PENDING after observation")
        if args.expect and result.decision != args.expect:
            raise RuntimeError(
                f"expected {args.expect}, received {result.decision}"
            )
        print(
            json.dumps(
                {
                    "arm": asdict(arm),
                    "result": result.to_dict(),
                    "device_id": status.device_id,
                    "boot_id": status.boot_id,
                    "firmware_version": status.firmware_version,
                    "repository_detector_sha256": expected_hash,
                },
                indent=2,
                sort_keys=True,
            )
        )
    finally:
        if not args.keep_research:
            try:
                request(
                    nrfutil,
                    args,
                    operation=2,
                    command_id=POWER_AUTO_COMMAND,
                )
                restored = True
            except RuntimeError as exc:
                print(f"WARN: failed to restore auto mode: {exc}", file=sys.stderr)
        else:
            restored = True
    if not restored:
        raise RuntimeError("Tag may still be in research power mode")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
