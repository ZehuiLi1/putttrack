#!/usr/bin/env python3
"""Replay the MCU motion-demo C implementation against reviewed raw JSONL."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
FIRMWARE_SRC = ROOT / "firmware" / "nrf54l15_tag_app" / "src"
REPLAY_SOURCE = ROOT / "tools" / "c" / "motion_demo_v0_replay.c"
DEFAULT_MANIFESTS = tuple(
    ROOT / "experiments" / name / "manifest.json"
    for name in (
        "research_ball_r1_pickup_precision_1a",
        "research_ball_r1_pickup_precision_1b",
        "research_ball_r1_pickup_precision_1c",
        "research_ball_r1_pickup_precision_1c_drop",
        "research_ball_r1_pickup_precision_1d_gentle",
        "research_ball_r1_pickup_precision_1e_rail",
        "research_ball_r1_pickup_precision_1e_step",
    )
)
PICKUP_POSITIVE_LABELS = {"pickup_carry", "pickup_drop"}
ROLLING_DISPLAY_LABELS = {"rolling_pickup", "putt_gentle"}


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("manifests", nargs="*", type=Path)
    result.add_argument("--output-dir", type=Path, required=True)
    result.add_argument("--compiler", type=Path)
    return result


def find_compiler(explicit: Path | None) -> str:
    if explicit is not None:
        candidate = explicit.expanduser()
        if not candidate.is_file():
            raise SystemExit(f"compiler not found: {candidate}")
        return str(candidate)
    compiler = shutil.which("cc") or shutil.which("gcc")
    if compiler is None:
        raise SystemExit("a C11 compiler (cc or gcc) is required")
    return compiler


def compile_runner(compiler: str, output: Path) -> None:
    completed = subprocess.run(
        [
            compiler,
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-pedantic",
            f"-I{FIRMWARE_SRC}",
            str(FIRMWARE_SRC / "motion_demo_v0.c"),
            str(REPLAY_SOURCE),
            "-o",
            str(output),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "motion-demo replay compiler failed:\n"
            + completed.stdout
            + completed.stderr
        )


def load_manifest(path: Path) -> tuple[str, list[dict[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    defaults = payload.get("defaults", {})
    episodes = [{**defaults, **item} for item in payload["episodes"]]
    return str(payload["dataset_id"]), episodes


def capture_input(path: Path) -> tuple[str, int]:
    rows: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        payload = json.loads(line)
        if payload.get("record_type") != "tag_motion":
            continue
        values = [
            int(payload["sequence"]),
            int(payload["source_monotonic_us"]),
            *(int(value) for value in payload["bmi270_accel_micro_ms2"]),
            *(int(value) for value in payload["bmi270_gyro_micro_rads"]),
            int(bool(payload["bmi270_valid"])),
            int(payload["sensor_error_bits"]),
        ]
        rows.append(",".join(str(value) for value in values))
    return "\n".join(rows) + "\n", len(rows)


def replay_capture(runner: Path, capture: Path) -> dict[str, Any]:
    payload, expected_samples = capture_input(capture)
    completed = subprocess.run(
        [str(runner)],
        cwd=ROOT,
        input=payload,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"{capture}: replay failed: {completed.stderr}")
    result = json.loads(completed.stdout)
    if int(result["samples"]) != expected_samples:
        raise RuntimeError(f"{capture}: replay sample count mismatch")
    return result


def seen_state(result: dict[str, Any], state_code: int) -> bool:
    return bool(int(result["seen_state_mask"]) & (1 << state_code))


def portable(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path.resolve())


def write_csv(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    materialized = list(rows)
    fields = sorted({key for row in materialized for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(materialized)


def canonical_config_sha256() -> str:
    path = ROOT / "configs" / "research" / "pickup_detector_v0.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def main() -> int:
    args = parser().parse_args()
    manifests = tuple(path.resolve() for path in args.manifests) or DEFAULT_MANIFESTS
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    compiler = find_compiler(args.compiler)

    with tempfile.TemporaryDirectory(
        prefix="putttrack-motion-demo-replay-", dir=Path.home()
    ) as temporary:
        runner = Path(temporary) / "motion_demo_v0_replay"
        compile_runner(compiler, runner)
        rows: list[dict[str, Any]] = []
        for manifest in sorted(manifests):
            dataset_id, episodes = load_manifest(manifest)
            for episode in sorted(episodes, key=lambda item: str(item["episode_id"])):
                capture = manifest.parent / str(episode["capture"])
                result = replay_capture(runner, capture)
                label = str(episode["label"]).strip().lower()
                expected_event = label in PICKUP_POSITIVE_LABELS
                row = {
                    "dataset_id": dataset_id,
                    "manifest": portable(manifest),
                    "episode_id": episode["episode_id"],
                    "label": label,
                    "capture": portable(capture),
                    "expected_pickup_from_rest": expected_event,
                    "pickup_event_count": int(result["event_count"]),
                    "pickup_event_boundary_pass": (
                        int(result["event_count"]) > 0
                    ) == expected_event,
                    "seen_stationary": seen_state(result, 1),
                    "seen_rolling_candidate": seen_state(result, 3),
                    "seen_carried_candidate": seen_state(result, 4),
                    "seen_active_unknown": seen_state(result, 5),
                    "seen_unknown_quality": seen_state(result, 6),
                    "final_state": result["state"],
                    "final_quality_flags": int(result["quality_flags"]),
                    "transition_count": int(result["transition_count"]),
                    "vertical_impulse_mps": int(result["impulse_milli_mps"])
                    / 1000.0,
                    "gyro_mean_1s_rads": int(result["gyro_mean_milli_rads"])
                    / 1000.0,
                    "axis_consistency_1s": int(result["axis_milli"]) / 1000.0,
                    "sample_count": int(result["samples"]),
                    "context_bytes": int(result["context_bytes"]),
                }
                rows.append(row)

    positives = [row for row in rows if row["expected_pickup_from_rest"]]
    nonpositives = [row for row in rows if not row["expected_pickup_from_rest"]]
    rolling_scope = [row for row in rows if row["label"] in ROLLING_DISPLAY_LABELS]
    summary = {
        "schema_version": 1,
        "demo_id": "mcu_motion_demo_v0",
        "authority": False,
        "candidate_only": True,
        "evaluation_scope": "C streaming replay on reviewed same-day raw JSONL; not product accuracy",
        "pickup_config_canonical_sha256": canonical_config_sha256(),
        "episodes": len(rows),
        "pickup_positive_episodes": len(positives),
        "pickup_positive_events_detected": sum(
            int(row["pickup_event_count"]) > 0 for row in positives
        ),
        "nonpositive_episodes": len(nonpositives),
        "false_pickup_events": sum(
            int(row["pickup_event_count"]) > 0 for row in nonpositives
        ),
        "pickup_event_boundary_passed": all(
            bool(row["pickup_event_boundary_pass"]) for row in rows
        ),
        "rolling_display_scope_episodes": len(rolling_scope),
        "rolling_display_scope_seen": sum(
            bool(row["seen_rolling_candidate"]) for row in rolling_scope
        ),
        "episodes_seen_unknown_quality": sum(
            bool(row["seen_unknown_quality"]) for row in rows
        ),
        "context_bytes": max(int(row["context_bytes"]) for row in rows),
        "limitations": [
            "same date, operator, Ball/core and mostly unspecified surface",
            "rolling candidate is post-hoc and not rolling-pickup confirmation",
            "no frame-level independent contact, lift, impact or stop timestamps",
            "no hardware timing, power or signed-image physical validation in this replay",
            "no Gameplay or scoring authority"
        ]
    }
    write_csv(output_dir / "episode_replay.csv", rows)
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["pickup_event_boundary_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
