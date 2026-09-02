#!/usr/bin/env python3
"""Select and verify the nRF54L15 Tag low-power policy over encrypted BLE SMP."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from putttrack.tag import status_from_smp  # noqa: E402


COMMAND_BY_MODE = {"auto": 20, "research": 21, "idle": 22}


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("mode", choices=tuple(COMMAND_BY_MODE))
    result.add_argument("--device-name", default="PuttTrack-Tag-v0.1")
    result.add_argument("--hci-port", default="/dev/cu.usbmodem101")
    result.add_argument("--scan-timeout", type=int, default=15)
    result.add_argument("--timeout", type=int, default=30)
    result.add_argument("--apply-timeout", type=float, default=8.0)
    result.add_argument("--nrfutil", type=Path)
    return result


def find_nrfutil(explicit: Path | None) -> Path:
    if explicit is not None:
        candidate = explicit.expanduser()
    else:
        found = shutil.which("nrfutil")
        candidate = Path(found) if found else Path.home() / ".local/bin/nrfutil"
    if not candidate.is_file():
        raise SystemExit(f"nrfutil was not found at {candidate}")
    return candidate


def request(
    nrfutil: Path,
    args: argparse.Namespace,
    *,
    operation: int,
    command_id: int,
) -> dict:
    command = [
        str(nrfutil),
        "mcu-manager",
        "ble",
        "--hci-serial-port",
        args.hci_port,
        "--timeout",
        str(args.timeout),
        "--log-output=stdout",
        "--log-level=warn",
        "raw-smp-request",
        "--device-name",
        args.device_name,
        "--scan-timeout",
        str(args.scan_timeout),
        "--pair",
        "--secure-connection",
        "--operation",
        str(operation),
        "--group-id",
        "64",
        "--command-id",
        str(command_id),
    ]
    completed = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
        stdin=subprocess.DEVNULL,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise RuntimeError(f"SMP request failed: {detail}")
    for line in reversed(completed.stdout.splitlines()):
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    raise RuntimeError("SMP request returned no JSON object")


def main() -> int:
    args = parser().parse_args()
    if not Path(args.hci_port).exists():
        raise SystemExit(f"HCI serial port does not exist: {args.hci_port}")
    if args.apply_timeout <= 0:
        raise SystemExit("--apply-timeout must be positive")

    nrfutil = find_nrfutil(args.nrfutil)
    acknowledgement = request(
        nrfutil,
        args,
        operation=2,
        command_id=COMMAND_BY_MODE[args.mode],
    )
    deadline = time.monotonic() + args.apply_timeout
    expected_state = {"research": "active", "idle": "idle"}.get(args.mode)
    status = None
    while time.monotonic() < deadline:
        status = status_from_smp(request(nrfutil, args, operation=0, command_id=0))
        if status.power_policy == args.mode and (
            expected_state is None or status.runtime_state == expected_state
        ):
            break
        time.sleep(0.2)
    else:
        raise RuntimeError(
            f"Tag did not apply mode {args.mode!r}; last status was {status}"
        )

    print(
        json.dumps(
            {
                "acknowledgement": acknowledgement,
                "battery_supported": status.battery_supported,
                "firmware_version": status.firmware_version,
                "mode": status.power_policy,
                "runtime_state": status.runtime_state,
                "stream_rate_hz": status.stream_rate_hz,
                "adxl367_odr_hz": status.adxl367_odr_hz,
                "bmi270_accel_odr_hz": status.bmi270_accel_odr_hz,
                "bmi270_gyro_odr_hz": status.bmi270_gyro_odr_hz,
                "advertising_interval_min_ms": status.advertising_interval_min_ms,
                "advertising_interval_max_ms": status.advertising_interval_max_ms,
                "advertising_start_error_count": status.advertising_start_error_count,
                "power_management_error_count": status.power_management_error_count,
                "bmi270_spi_suspended": status.bmi270_spi_suspended,
                "idle_wake_interrupt_enabled": status.idle_wake_interrupt_enabled,
                "adxl367_wakeup_mode_enabled": status.adxl367_wakeup_mode_enabled,
                "power_transition_count": status.power_transition_count,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
