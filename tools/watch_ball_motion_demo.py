#!/usr/bin/env python3
"""Watch the research-only on-Ball motion demo over encrypted BLE SMP."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from putttrack.tag import status_from_smp  # noqa: E402

MGMT_GROUP_ID = 64
STATUS_COMMAND = 0
POWER_AUTO_COMMAND = 20
POWER_RESEARCH_COMMAND = 21
MOTION_DEMO_COMMAND = 24
RETRY_BASE_SECONDS = 0.5

QUALITY_FLAG_NAMES = {
    1 << 0: "sensor_invalid",
    1 << 1: "sequence_gap",
    1 << 2: "time_regression",
    1 << 3: "baseline_not_stationary",
    1 << 4: "insufficient_window",
    1 << 5: "gyro_clipped",
}

STATE_HINTS = {
    "BOOTSTRAP": "keep the Ball still for about 1 second",
    "STATIONARY": "ready",
    "ACTIVE_PENDING": "collecting the 1-second decision window",
    "ROLLING_CANDIDATE": "sustained single-axis rotation candidate",
    "CARRIED_CANDIDATE": "pickup-from-rest event was detected",
    "ACTIVE_UNKNOWN": "motion is real, but the supported demo paths do not identify it",
    "UNKNOWN_QUALITY": "evidence is incomplete or clipped; no semantic decision",
}


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--device-name", default="PuttTrack-")
    result.add_argument("--ble-address")
    result.add_argument(
        "--address-type",
        choices=("public", "random", "public-identity", "random-identity"),
    )
    result.add_argument("--expected-device-id")
    result.add_argument("--hci-port", default="/dev/cu.usbmodem101")
    result.add_argument("--scan-timeout", type=int, default=15)
    result.add_argument("--timeout", type=int, default=30)
    result.add_argument("--request-retries", type=int, default=5)
    result.add_argument("--poll-interval", type=float, default=0.35)
    result.add_argument(
        "--duration-seconds",
        type=float,
        default=0.0,
        help="stop automatically after this many seconds; zero means Ctrl+C",
    )
    result.add_argument("--nrfutil", type=Path)
    result.add_argument(
        "--no-set-research",
        action="store_true",
        help="do not switch the Ball to the forced 50 Hz research policy",
    )
    result.add_argument(
        "--no-restore-auto",
        action="store_true",
        help="leave the selected power policy unchanged on exit",
    )
    result.add_argument(
        "--all-samples",
        action="store_true",
        help="print every poll instead of only state/event/quality changes",
    )
    result.add_argument("--jsonl", type=Path, help="optional append-only poll log")
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


def build_request_command(
    nrfutil: Path,
    args: argparse.Namespace,
    *,
    operation: int,
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
        str(operation),
        "--group-id",
        str(MGMT_GROUP_ID),
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


def request(
    nrfutil: Path,
    args: argparse.Namespace,
    *,
    operation: int,
    command_id: int,
) -> dict[str, Any]:
    command = build_request_command(
        nrfutil, args, operation=operation, command_id=command_id
    )
    detail = "no response"
    for attempt in range(1, args.request_retries + 1):
        completed = subprocess.run(
            command,
            text=True,
            capture_output=True,
            check=False,
            stdin=subprocess.DEVNULL,
        )
        if completed.returncode == 0:
            for line in reversed(completed.stdout.splitlines()):
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict):
                    return payload
            detail = "request returned no JSON object"
        else:
            detail = (completed.stderr or completed.stdout).strip()
        if attempt < args.request_retries:
            print(
                f"WARN: command {command_id} attempt {attempt} failed; retrying",
                file=sys.stderr,
                flush=True,
            )
            time.sleep(min(RETRY_BASE_SECONDS * attempt, 2.0))
    raise RuntimeError(
        f"SMP command {command_id} failed after {args.request_retries} attempts: "
        f"{detail}"
    )


def quality_names(flags: int) -> tuple[str, ...]:
    names = [name for bit, name in QUALITY_FLAG_NAMES.items() if flags & bit]
    unknown = flags & ~sum(QUALITY_FLAG_NAMES)
    if unknown:
        names.append(f"unknown_bits_0x{unknown:x}")
    return tuple(names)


def validate_demo_payload(payload: dict[str, Any]) -> dict[str, Any]:
    required = {
        "demo_id",
        "authority",
        "candidate_only",
        "state",
        "state_code",
        "last_event",
        "event_code",
        "quality_flags",
        "transition_count",
        "event_count",
        "impulse_milli_mps",
        "gyro_mean_milli_rads",
        "axis_milli",
        "pickup_config_sha256",
        "stream_hz",
    }
    missing = sorted(required - payload.keys())
    if missing:
        raise ValueError(f"motion demo response is missing fields: {missing}")
    if payload["authority"] is not False or payload["candidate_only"] is not True:
        raise ValueError("motion demo must remain candidate-only with authority=false")
    if not isinstance(payload["state"], str) or not payload["state"]:
        raise ValueError("motion demo state must be non-empty text")
    normalized = dict(payload)
    normalized["quality_names"] = quality_names(int(payload["quality_flags"]))
    normalized["impulse_mps"] = int(payload["impulse_milli_mps"]) / 1000.0
    normalized["gyro_mean_rads"] = int(payload["gyro_mean_milli_rads"]) / 1000.0
    normalized["axis_consistency"] = int(payload["axis_milli"]) / 1000.0
    return normalized


def display_line(payload: dict[str, Any]) -> str:
    quality = ",".join(payload["quality_names"]) or "ok"
    state = payload["state"]
    hint = STATE_HINTS.get(state, "candidate state")
    return (
        f"{datetime.now().astimezone().strftime('%H:%M:%S')}  "
        f"{state:<19} event={payload['last_event']:<16} "
        f"impulse={payload['impulse_mps']:.3f} m/s  "
        f"gyro={payload['gyro_mean_rads']:.2f} rad/s  "
        f"axis={payload['axis_consistency']:.3f}  "
        f"quality={quality}  [{hint}]"
    )


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "host_time_ns": time.time_ns(),
        "record_type": "mcu_motion_demo_v0",
        **payload,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def wait_for_policy(
    nrfutil: Path,
    args: argparse.Namespace,
    expected_policy: str,
    timeout_s: float = 8.0,
) -> Any:
    deadline = time.monotonic() + timeout_s
    last = None
    while time.monotonic() < deadline:
        last = status_from_smp(
            request(
                nrfutil,
                args,
                operation=0,
                command_id=STATUS_COMMAND,
            )
        )
        if last.power_policy == expected_policy:
            return last
        time.sleep(0.2)
    raise RuntimeError(
        f"Ball did not enter {expected_policy!r}; last status was {last}"
    )


def main() -> int:
    args = parser().parse_args()
    if args.address_type and not args.ble_address:
        raise SystemExit("--address-type requires --ble-address")
    if args.poll_interval <= 0:
        raise SystemExit("--poll-interval must be positive")
    if args.duration_seconds < 0:
        raise SystemExit("--duration-seconds cannot be negative")
    if args.request_retries <= 0:
        raise SystemExit("--request-retries must be positive")
    if not Path(args.hci_port).exists():
        raise SystemExit(f"HCI serial port does not exist: {args.hci_port}")

    nrfutil = find_nrfutil(args.nrfutil)
    switched = False
    status = status_from_smp(
        request(nrfutil, args, operation=0, command_id=STATUS_COMMAND)
    )
    if args.expected_device_id and status.device_id != args.expected_device_id.lower():
        raise RuntimeError(
            f"connected device {status.device_id} does not match "
            f"--expected-device-id {args.expected_device_id.lower()}"
        )

    try:
        if not args.no_set_research and status.power_policy != "research":
            request(
                nrfutil,
                args,
                operation=2,
                command_id=POWER_RESEARCH_COMMAND,
            )
            status = wait_for_policy(nrfutil, args, "research")
            switched = True
        print(
            f"Connected Ball {status.device_id} · firmware {status.firmware_version} · "
            f"policy {status.power_policy}. Results are candidate-only; Ctrl+C stops."
        )

        deadline = (
            time.monotonic() + args.duration_seconds
            if args.duration_seconds > 0
            else None
        )
        previous_key: tuple[Any, ...] | None = None
        while deadline is None or time.monotonic() < deadline:
            payload = validate_demo_payload(
                request(
                    nrfutil,
                    args,
                    operation=0,
                    command_id=MOTION_DEMO_COMMAND,
                )
            )
            key = (
                payload["state_code"],
                payload["event_count"],
                payload["quality_flags"],
            )
            if args.all_samples or key != previous_key:
                print(display_line(payload), flush=True)
            if args.jsonl:
                append_jsonl(args.jsonl, payload)
            previous_key = key
            time.sleep(args.poll_interval)
    except KeyboardInterrupt:
        print("\nStopped by operator.")
    finally:
        if switched and not args.no_restore_auto:
            try:
                request(
                    nrfutil,
                    args,
                    operation=2,
                    command_id=POWER_AUTO_COMMAND,
                )
                wait_for_policy(nrfutil, args, "auto")
                print("Ball restored to auto power policy.")
            except Exception as exc:  # pragma: no cover - physical cleanup path
                print(f"WARN: failed to restore auto policy: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
