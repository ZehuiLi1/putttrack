#!/usr/bin/env python3
"""Run one bounded roller action inside an identity-locked frozen IMU capture."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
CAPTURE_TOOL = REPO_ROOT / "tools" / "capture_tag_smp.py"
MOTOR_TOOL = REPO_ROOT / "tools" / "control_roller_motor.py"
ANALYZE_TOOL = REPO_ROOT / "tools" / "analyze_tag_capture.py"
MAX_ABS_RPM = 300
HISTORY_BUDGET_SECONDS = 17.0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hci-port", required=True)
    parser.add_argument("--motor-port", required=True)
    parser.add_argument("--expected-device-id", required=True)
    parser.add_argument("--rpm", type=int, required=True)
    parser.add_argument("--seconds", type=int, required=True)
    parser.add_argument(
        "--acceleration",
        type=int,
        default=20,
        help="Emm_V5 acceleration level 0-255; 0 requests direct acceleration",
    )
    parser.add_argument(
        "--deceleration",
        type=int,
        help="optional Emm_V5 0-255 ramp-to-zero level; omit for immediate stop",
    )
    parser.add_argument("--pre-roll-seconds", type=float, default=3.0)
    parser.add_argument("--tail-seconds", type=float, default=3.0)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--label")
    parser.add_argument("--notes")
    parser.add_argument(
        "--confirm-clear",
        action="store_true",
        help="confirm that the ball is secured and the guarded roller is clear",
    )
    return parser


def validate_args(args: argparse.Namespace) -> None:
    if not args.confirm_clear:
        raise ValueError("roller capture requires --confirm-clear")
    if args.rpm == 0 or abs(args.rpm) > MAX_ABS_RPM:
        raise ValueError(f"--rpm must be non-zero and within +/-{MAX_ABS_RPM}")
    if args.seconds <= 0:
        raise ValueError("--seconds must be positive")
    if not 0 <= args.acceleration <= 255:
        raise ValueError("--acceleration must be between 0 and 255")
    if args.deceleration is not None and not 0 <= args.deceleration <= 255:
        raise ValueError("--deceleration must be between 0 and 255")
    if args.pre_roll_seconds <= 0 or args.tail_seconds <= 0:
        raise ValueError("pre-roll and tail durations must be positive")
    if args.pre_roll_seconds + args.seconds + args.tail_seconds > HISTORY_BUDGET_SECONDS:
        raise ValueError(
            "pre-roll, motor run, and tail exceed the frozen-history budget of "
            f"{HISTORY_BUDGET_SECONDS:.1f} seconds"
        )
    if args.output.exists():
        raise ValueError(f"output already exists: {args.output}")


def episode_label(args: argparse.Namespace) -> str:
    return args.label or f"roller_{args.rpm}rpm"


def build_capture_command(args: argparse.Namespace) -> list[str]:
    episode_seconds = args.seconds + args.tail_seconds
    command = [
        sys.executable,
        str(CAPTURE_TOOL),
        "--hci-port",
        args.hci_port,
        "--mode",
        "frozen",
        "--armed-countdown",
        str(args.pre_roll_seconds),
        "--episode-seconds",
        str(episode_seconds),
        "--expected-device-id",
        args.expected_device_id,
        "--label",
        episode_label(args),
        "--output",
        str(args.output),
    ]
    if args.notes:
        command.extend(("--notes", args.notes))
    return command


def build_motor_command(args: argparse.Namespace, command: str = "run") -> list[str]:
    base = [sys.executable, str(MOTOR_TOOL), "--port", args.motor_port]
    if command == "run":
        command_line = base + [
            "run",
            "--rpm",
            str(args.rpm),
            "--seconds",
            str(args.seconds),
            "--acceleration",
            str(args.acceleration),
            "--confirm-clear",
        ]
        if args.deceleration is not None:
            command_line[-1:-1] = ["--deceleration", str(args.deceleration)]
        return command_line
    return base + [command]


def stop_and_disable(args: argparse.Namespace) -> None:
    for command in ("stop", "disable"):
        subprocess.run(build_motor_command(args, command), check=False)


def run(args: argparse.Namespace) -> int:
    capture = subprocess.Popen(
        build_capture_command(args),
        cwd=REPO_ROOT,
        stdout=None,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    assert capture.stderr is not None
    motor_started = False
    try:
        for line in capture.stderr:
            print(line, end="", file=sys.stderr, flush=True)
            if line.startswith("GO:"):
                motor_started = True
                motor_result = subprocess.run(
                    build_motor_command(args),
                    cwd=REPO_ROOT,
                    check=False,
                )
                if motor_result.returncode != 0:
                    stop_and_disable(args)
                    capture.wait()
                    return motor_result.returncode
        capture_result = capture.wait()
    except BaseException:
        if motor_started:
            stop_and_disable(args)
        if capture.poll() is None:
            capture.terminate()
        raise

    if not motor_started:
        print("error: capture exited before its GO marker", file=sys.stderr)
        return 2
    if capture_result != 0:
        print(f"error: frozen capture exited with {capture_result}", file=sys.stderr)
        return capture_result

    return subprocess.run(
        [sys.executable, str(ANALYZE_TOOL), str(args.output)],
        cwd=REPO_ROOT,
        check=False,
    ).returncode


def main() -> int:
    args = build_parser().parse_args()
    try:
        validate_args(args)
        return run(args)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
