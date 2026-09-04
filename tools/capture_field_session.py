#!/usr/bin/env python3
"""Collect a batch of operator-led Ball IMU episodes with one Enter per run."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
CAPTURE_TOOL = REPO_ROOT / "tools" / "capture_tag_smp.py"
ANALYZE_TOOL = REPO_ROOT / "tools" / "analyze_tag_capture.py"
POWER_TOOL = REPO_ROOT / "tools" / "set_tag_power_mode.py"


def project_python() -> str:
    for candidate in (
        REPO_ROOT / ".venv" / "bin" / "python",
        REPO_ROOT / ".venv" / "Scripts" / "python.exe",
    ):
        if candidate.is_file():
            return str(candidate)
    return sys.executable


PYTHON = project_python()


@dataclass(frozen=True)
class Profile:
    label: str
    episode_seconds: float
    instruction: str


PROFILES = {
    "pickup_carry": Profile(
        label="pickup_carry",
        episode_seconds=12.0,
        instruction="GO 后等约 1 秒，拿起球、行走 2–3 秒、放下，然后不要再碰球。",
    ),
    "pickup_drop": Profile(
        label="pickup_drop",
        episode_seconds=12.0,
        instruction=(
            "GO 后等约 1 秒，拿起球、行走 2–3 秒，再从正常手持低高度随手丢下；"
            "不要用力砸球，落地后不要再碰。"
        ),
    ),
    "handling": Profile(
        label="handling",
        episode_seconds=8.0,
        instruction=(
            "GO 后等约 1 秒，只做一次普通触摸、原地转动或轻微挪动；"
            "球必须始终接触地面，不能拿起，然后保持静止。"
        ),
    ),
    "putt_gentle": Profile(
        label="putt_gentle",
        episode_seconds=12.0,
        instruction="GO 后等约 1 秒，轻推一次，让球自然停止；结束提示前不要捡球。",
    ),
    "putt_normal": Profile(
        label="putt_normal",
        episode_seconds=12.0,
        instruction="GO 后等约 1 秒，正常推击一次，让球自然停止；结束提示前不要捡球。",
    ),
    "putt_firm": Profile(
        label="putt_firm",
        episode_seconds=12.0,
        instruction="GO 后等约 1 秒，较重推击一次，让球自然停止；结束提示前不要捡球。",
    ),
    "hand_roll": Profile(
        label="hand_roll",
        episode_seconds=10.0,
        instruction="GO 后等约 1 秒，用手推动一次，不使用球杆，让球自然停止。",
    ),
    "putt_rail_collision": Profile(
        label="putt_rail_collision",
        episode_seconds=12.0,
        instruction=(
            "GO 后等约 1 秒，正常推击一次，让球碰撞一次固定边轨后自然停止；"
            "结束提示前不要捡球。"
        ),
    ),
    "track_step_drop": Profile(
        label="track_step_drop",
        episode_seconds=12.0,
        instruction=(
            "GO 后等约 1 秒，让球滚过一次赛道小台阶并自然停止；"
            "不要用手抛球，结束提示前不要捡球。"
        ),
    ),
    "rolling_pickup": Profile(
        label="rolling_pickup",
        episode_seconds=12.0,
        instruction=(
            "GO 后等约 1 秒，先用手推动球；球仍在滚动时将它拿起，"
            "手持约 2 秒再放下，然后不要再碰球。"
        ),
    ),
}


def default_session_id() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", choices=tuple(PROFILES))
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--start-index", type=int, default=1)
    parser.add_argument("--session-id", default=default_session_id())
    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / "runs")
    parser.add_argument("--hci-port", default="/dev/cu.usbmodem101")
    parser.add_argument("--expected-device-id", required=True)
    parser.add_argument("--device-name", default="PuttTrack-")
    parser.add_argument("--ble-address")
    parser.add_argument(
        "--address-type",
        choices=("public", "random", "public-identity", "random-identity"),
    )
    parser.add_argument("--notes", help="notes appended to every episode in this batch")
    return parser


def validate_args(args: argparse.Namespace) -> None:
    if args.count <= 0:
        raise ValueError("--count must be positive")
    if args.start_index <= 0:
        raise ValueError("--start-index must be positive")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", args.session_id):
        raise ValueError(
            "--session-id must contain only letters, digits, hyphen or underscore"
        )
    if not re.fullmatch(r"[0-9a-fA-F]{16}", args.expected_device_id):
        raise ValueError("--expected-device-id must be exactly 16 hexadecimal characters")
    if args.address_type and not args.ble_address:
        raise ValueError("--address-type requires --ble-address")


def selector_args(args: argparse.Namespace) -> list[str]:
    if args.ble_address:
        result = ["--ble-address", args.ble_address]
        if args.address_type:
            result.extend(("--address-type", args.address_type))
        return result
    return ["--device-name", args.device_name]


def output_path(args: argparse.Namespace, repetition: int) -> Path:
    return args.output_dir / (
        f"field-{args.session_id}-{PROFILES[args.profile].label}-r{repetition:02d}.jsonl"
    )


def build_power_command(args: argparse.Namespace, mode: str) -> list[str]:
    return [
        PYTHON,
        str(POWER_TOOL),
        mode,
        "--hci-port",
        args.hci_port,
        *selector_args(args),
    ]


def build_capture_command(
    args: argparse.Namespace,
    repetition: int,
    *,
    wait_for_go_ack: bool = False,
) -> list[str]:
    profile = PROFILES[args.profile]
    notes = profile.instruction
    if args.notes:
        notes = f"{notes} {args.notes}"
    command = [
        PYTHON,
        str(CAPTURE_TOOL),
        "--mode",
        "frozen",
        "--hci-port",
        args.hci_port,
        *selector_args(args),
        "--expected-device-id",
        args.expected_device_id.lower(),
        "--armed-countdown",
        "3",
        "--episode-seconds",
        str(profile.episode_seconds),
        "--audible-cue",
        "--label",
        profile.label,
        "--notes",
        notes,
        "--output",
        str(output_path(args, repetition)),
    ]
    if wait_for_go_ack:
        command.extend(("--wait-for-go-ack", "--go-ack-timeout", "20"))
    return command


def run_command(command: list[str]) -> int:
    return subprocess.run(command, cwd=REPO_ROOT, check=False).returncode


def run(args: argparse.Namespace) -> int:
    profile = PROFILES[args.profile]
    planned = range(args.start_index, args.start_index + args.count)
    existing = [output_path(args, repetition) for repetition in planned]
    existing = [path for path in existing if path.exists()]
    if existing:
        raise ValueError(f"refusing to overwrite existing capture: {existing[0]}")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n动作：{args.profile}")
    print(f"每组：{profile.instruction}")
    print("每组只按一次 Enter 开始；采集会自动结束。输入 q 可结束整个批次。")

    research_active = False
    completed = 0
    exit_code = 0
    try:
        print("\n正在将 Ball 切换到 research 模式……")
        if run_command(build_power_command(args, "research")) != 0:
            print("错误：无法进入 research 模式，未开始采集。", file=sys.stderr)
            return 1
        research_active = True

        for repetition in planned:
            answer = input(
                f"\n[{completed + 1}/{args.count}] 摆好球并保持静止；按 Enter 开始，输入 q 结束："
            ).strip().lower()
            if answer == "q":
                break
            capture = output_path(args, repetition)
            print(f"保存到 {capture}")
            if run_command(build_capture_command(args, repetition)) != 0:
                print("错误：本组采集失败，已保留诊断文件并停止批次。", file=sys.stderr)
                exit_code = 1
                break
            if run_command([PYTHON, str(ANALYZE_TOOL), str(capture)]) != 0:
                print("错误：本组分析未通过，停止批次以避免继续采集坏数据。", file=sys.stderr)
                exit_code = 1
                break
            completed += 1
            print("\a本组完成；现在可以拿回或重新摆放球。")
    except (EOFError, KeyboardInterrupt):
        print("\n采集已由用户结束。")
    finally:
        if research_active:
            print("\n正在将 Ball 恢复为 auto 低功耗模式……")
            if run_command(build_power_command(args, "auto")) != 0:
                print(
                    "警告：自动恢复低功耗失败，请手动运行 set_tag_power_mode.py auto。",
                    file=sys.stderr,
                )
                exit_code = 1

    print(f"批次结束：成功保存 {completed}/{args.count} 组。")
    return exit_code


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
