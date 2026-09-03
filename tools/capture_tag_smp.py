#!/usr/bin/env python3
"""Capture identity-locked Tag status and motion through a USB HCI adapter."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import threading
import time
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from putttrack.tag import (  # noqa: E402
    TagCaptureSession,
    frozen_history_from_smp,
    frozen_history_metadata_from_smp,
    motion_from_smp,
    motion_window_from_smp,
    status_from_smp,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device-name", default="PuttTrack-")
    parser.add_argument(
        "--ble-address",
        help="pin every nrfutil request to one BLE address instead of scanning by name",
    )
    parser.add_argument(
        "--address-type",
        choices=("public", "random", "public-identity", "random-identity"),
        help="optional nrfutil address type; valid only with --ble-address",
    )
    parser.add_argument(
        "--expected-device-id",
        help="stable hexadecimal Tag DEVICE_ID; abort before output if different",
    )
    parser.add_argument("--hci-port", default="/dev/cu.usbmodem101")
    parser.add_argument(
        "--mode",
        choices=("frozen", "window", "snapshot"),
        default="window",
        help=(
            "frozen retrieves the latest 20.48 s atomically on firmware >=0.1.7; "
            "window streams overlapping 64-sample rings; snapshot supports older firmware"
        ),
    )
    parser.add_argument("--count", type=int, default=3, help="number of SMP requests")
    parser.add_argument("--interval", type=float, default=0.1)
    parser.add_argument("--scan-timeout", type=int, default=15)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--request-retries", type=int, default=3)
    parser.add_argument("--max-consecutive-request-failures", type=int, default=5)
    parser.add_argument("--nrfutil", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--label", help="episode label, for example stationary or pickup_carry")
    parser.add_argument("--notes", help="free-text physical setup note")
    parser.add_argument(
        "--until-enter",
        action="store_true",
        help="keep requesting windows until Enter is received or --count is reached",
    )
    return parser


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
    command_id: int,
) -> dict[str, Any]:
    command = build_request_command(nrfutil, args, command_id)
    last_detail = "no response"
    for attempt in range(1, args.request_retries + 1):
        result = subprocess.run(
            command,
            text=True,
            capture_output=True,
            check=False,
            stdin=subprocess.DEVNULL,
        )
        if result.returncode == 0:
            for line in reversed(result.stdout.splitlines()):
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict):
                    return payload
            last_detail = "request returned no JSON object"
        else:
            last_detail = (result.stderr or result.stdout).strip()
        if attempt < args.request_retries:
            print(
                f"WARN: nrfutil request {command_id} attempt {attempt} failed; retrying",
                file=sys.stderr,
                flush=True,
            )
            time.sleep(0.25)
    raise RuntimeError(
        f"nrfutil request {command_id} failed after {args.request_retries} attempts: "
        f"{last_detail}"
    )


def build_request_command(
    nrfutil: Path,
    args: argparse.Namespace,
    command_id: int,
) -> list[str]:
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
        "--pair",
        "--secure-connection",
        "--operation",
        "0",
        "--group-id",
        "64",
        "--command-id",
        str(command_id),
    ]
    if args.ble_address:
        command.extend(("--address", args.ble_address))
        if args.address_type:
            command.extend(("--address-type", args.address_type))
    else:
        command.extend(
            (
                "--device-name",
                args.device_name,
                "--scan-timeout",
                str(args.scan_timeout),
            )
        )
    return command


def vector_norm(values: tuple[int, int, int]) -> float:
    return math.sqrt(sum(value * value for value in values)) / 1_000_000.0


def main() -> int:
    args = build_parser().parse_args()
    if args.count <= 0:
        raise SystemExit("--count must be positive")
    if args.interval < 0:
        raise SystemExit("--interval must not be negative")
    if args.scan_timeout <= 0 or args.timeout <= 0:
        raise SystemExit("timeouts must be positive")
    if args.request_retries <= 0 or args.max_consecutive_request_failures <= 0:
        raise SystemExit("request retry limits must be positive")
    if args.mode == "frozen" and args.until_enter:
        raise SystemExit("--until-enter is unnecessary with the always-on frozen history")
    if not Path(args.hci_port).exists():
        raise SystemExit(f"HCI serial port does not exist: {args.hci_port}")
    if args.address_type and not args.ble_address:
        raise SystemExit("--address-type requires --ble-address")

    nrfutil = find_nrfutil(args.nrfutil)
    status = status_from_smp(request(nrfutil, args, 0))
    capture_session = TagCaptureSession(
        expected_device_id=args.expected_device_id,
    )
    capture_session.start(status)
    if not status.adxl367_ready or not status.bmi270_ready:
        raise RuntimeError("Tag reports that one or more motion sensors are not ready")
    if status.sensor_health is not None and (
        status.sensor_health != "healthy" or status.capture_safe is not True
    ):
        raise RuntimeError(
            f"Tag capture is not safe: health={status.sensor_health!r}, "
            f"capture_safe={status.capture_safe!r}"
        )
    if status.sensor_health is None and status.sensor_error_count != 0:
        raise RuntimeError(
            "Tag reports pre-existing sensor errors; reboot and diagnose before collecting labels"
        )

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
    output = args.output.open("x", encoding="utf-8") if args.output else None

    def emit(record: dict[str, Any]) -> None:
        line = json.dumps(record, separators=(",", ":"), sort_keys=True)
        if output is None:
            print(line)
        else:
            output.write(line + "\n")
            output.flush()

    emit(
        {
            "record_type": "tag_status",
            "transport": f"smp_{args.mode}",
            "host_received_ns": time.time_ns(),
            "episode_label": args.label,
            "episode_notes": args.notes,
            **status.to_dict(),
        }
    )

    stop_requested = threading.Event()
    if args.until_enter:
        print("ARMED: capture continues until Enter is received", file=sys.stderr, flush=True)

        def wait_for_enter() -> None:
            sys.stdin.readline()
            stop_requested.set()

        threading.Thread(target=wait_for_enter, daemon=True).start()

    motions_by_sequence = {}
    motions_in_receive_order = []
    final_status = status
    capture_report = None
    request_failures_total = 0
    consecutive_request_failures = 0
    try:
        if args.mode == "frozen":
            frozen_metadata = frozen_history_metadata_from_smp(
                request(nrfutil, args, 3)
            )
            chunk_payloads = [
                request(nrfutil, args, 4 + chunk_index)
                for chunk_index in range(frozen_metadata.chunk_count)
            ]
            batch = frozen_history_from_smp(frozen_metadata, chunk_payloads)
            emit(
                {
                    "record_type": "tag_frozen_history",
                    "transport": "smp_frozen",
                    "host_received_ns": time.time_ns(),
                    "episode_label": args.label,
                    "episode_notes": args.notes,
                    **frozen_metadata.to_dict(),
                }
            )
            received_ns = time.time_ns()
            for motion in batch:
                motions_by_sequence[motion.sequence] = motion
                motions_in_receive_order.append(motion)
                emit(
                    {
                        "record_type": "tag_motion",
                        "transport": f"smp_{args.mode}",
                        "host_received_ns": received_ns,
                        "episode_label": args.label,
                        "episode_notes": args.notes,
                        **motion.to_dict(),
                    }
                )
        else:
            for index in range(args.count):
                if stop_requested.is_set() and motions_by_sequence:
                    break
                try:
                    if args.mode == "window":
                        batch = motion_window_from_smp(request(nrfutil, args, 2))
                    else:
                        batch = (motion_from_smp(request(nrfutil, args, 1)),)
                except RuntimeError as exc:
                    request_failures_total += 1
                    consecutive_request_failures += 1
                    if (
                        consecutive_request_failures
                        >= args.max_consecutive_request_failures
                    ):
                        raise
                    print(
                        f"WARN: transient capture request failure: {exc}",
                        file=sys.stderr,
                        flush=True,
                    )
                    time.sleep(max(args.interval, 0.25))
                    continue
                consecutive_request_failures = 0
                received_ns = time.time_ns()
                for motion in batch:
                    if motion.sequence in motions_by_sequence:
                        continue
                    motions_by_sequence[motion.sequence] = motion
                    motions_in_receive_order.append(motion)
                    emit(
                        {
                            "record_type": "tag_motion",
                            "transport": f"smp_{args.mode}",
                            "host_received_ns": received_ns,
                            "episode_label": args.label,
                            "episode_notes": args.notes,
                            **motion.to_dict(),
                        }
                    )
                if index + 1 < args.count and args.interval:
                    time.sleep(args.interval)
        final_status = status_from_smp(request(nrfutil, args, 0))
        emit(
            {
                "record_type": "tag_status_final",
                "transport": f"smp_{args.mode}",
                "host_received_ns": time.time_ns(),
                "episode_label": args.label,
                "episode_notes": args.notes,
                **final_status.to_dict(),
            }
        )
        for motion in motions_in_receive_order:
            capture_session.observe_motion(motion)
        capture_report = capture_session.finalize(final_status)
        emit(
            {
                "record_type": "tag_capture_result",
                "transport": f"smp_{args.mode}",
                "host_received_ns": time.time_ns(),
                "episode_label": args.label,
                "episode_notes": args.notes,
                **capture_report.to_dict(),
            }
        )
    finally:
        if output is not None:
            output.close()

    motions = [motions_by_sequence[key] for key in sorted(motions_by_sequence)]
    if not motions:
        raise RuntimeError("Tag returned no motion samples")
    if capture_report is None:
        raise RuntimeError("Tag capture continuity report was not produced")
    bmi_accel_norms = [vector_norm(item.bmi270_accel_micro_ms2) for item in motions]
    gyro_norms = [vector_norm(item.bmi270_gyro_micro_rads) for item in motions]
    sequence_gaps = sum(
        max(0, current.sequence - previous.sequence - 1)
        for previous, current in zip(motions, motions[1:])
    )
    sensor_error_count_delta = (
        final_status.sensor_error_count - status.sensor_error_count
    )
    valid = (
        all(
            item.adxl367_valid
            and item.bmi270_valid
            and item.sensor_error_bits == 0
            for item in motions
        )
        and sequence_gaps == 0
        and sensor_error_count_delta == 0
        and capture_report.passed
    )
    summary = {
        "status": "PASS" if valid else "FAIL",
        "transport": f"smp_{args.mode}",
        "warning": (
            "snapshot mode is low-rate diagnostics only"
            if args.mode == "snapshot"
            else None
        ),
        "device_id": status.device_id,
        "boot_id": status.boot_id,
        "firmware_version": status.firmware_version,
        "power_policy": final_status.power_policy,
        "runtime_state": final_status.runtime_state,
        "power_transition_count": final_status.power_transition_count,
        "battery_supported": final_status.battery_supported,
        "battery_sample_valid": final_status.battery_sample_valid,
        "battery_sample_error": final_status.battery_sample_error,
        "battery_voltage_mv": final_status.battery_voltage_mv,
        "battery_soc_percent": final_status.battery_soc_percent,
        "battery_soc_estimated": final_status.battery_soc_estimated,
        "advertising_interval_min_ms": final_status.advertising_interval_min_ms,
        "advertising_interval_max_ms": final_status.advertising_interval_max_ms,
        "advertising_start_error_count": final_status.advertising_start_error_count,
        "power_management_error_count": final_status.power_management_error_count,
        "bmi270_spi_suspended": final_status.bmi270_spi_suspended,
        "idle_wake_interrupt_enabled": final_status.idle_wake_interrupt_enabled,
        "adxl367_wakeup_mode_enabled": final_status.adxl367_wakeup_mode_enabled,
        "stream_rate_hz": final_status.stream_rate_hz,
        "adxl367_odr_hz": final_status.adxl367_odr_hz,
        "adxl367_range_g": final_status.adxl367_range_g,
        "bmi270_accel_odr_hz": final_status.bmi270_accel_odr_hz,
        "bmi270_accel_range_g": final_status.bmi270_accel_range_g,
        "bmi270_gyro_odr_hz": final_status.bmi270_gyro_odr_hz,
        "bmi270_gyro_range_dps": final_status.bmi270_gyro_range_dps,
        "sensor_error_count_start": status.sensor_error_count,
        "sensor_error_count_end": final_status.sensor_error_count,
        "sensor_error_count_delta": sensor_error_count_delta,
        "notify_drop_count_start": status.notify_drop_count,
        "notify_drop_count_end": final_status.notify_drop_count,
        "notify_drop_count_delta": (
            final_status.notify_drop_count - status.notify_drop_count
        ),
        "adxl367_clip_count_start": status.adxl367_clip_count,
        "adxl367_clip_count_end": final_status.adxl367_clip_count,
        "adxl367_clip_count_delta": (
            final_status.adxl367_clip_count - status.adxl367_clip_count
        ),
        "bmi270_accel_clip_count_start": status.bmi270_accel_clip_count,
        "bmi270_accel_clip_count_end": final_status.bmi270_accel_clip_count,
        "bmi270_accel_clip_count_delta": (
            final_status.bmi270_accel_clip_count - status.bmi270_accel_clip_count
        ),
        "bmi270_gyro_clip_count_start": status.bmi270_gyro_clip_count,
        "bmi270_gyro_clip_count_end": final_status.bmi270_gyro_clip_count,
        "bmi270_gyro_clip_count_delta": (
            final_status.bmi270_gyro_clip_count - status.bmi270_gyro_clip_count
        ),
        "episode_label": args.label,
        "episode_notes": args.notes,
        "request_failures_total": request_failures_total,
        "records": len(motions),
        "first_sequence": motions[0].sequence,
        "last_sequence": motions[-1].sequence,
        "sequence_gaps_expected": sequence_gaps,
        "capture_continuity": capture_report.to_dict(),
        "bmi_accel_norm_mean_mps2": statistics.fmean(bmi_accel_norms),
        "bmi_accel_norm_stdev_mps2": statistics.pstdev(bmi_accel_norms),
        "bmi_gyro_norm_rms_rads": math.sqrt(statistics.fmean(value * value for value in gyro_norms)),
        "output": str(args.output) if args.output else None,
    }
    print(json.dumps(summary, indent=2, sort_keys=True), file=sys.stderr)
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
