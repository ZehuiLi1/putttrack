#!/usr/bin/env python3
"""Replay the embedded motion C engine against reviewed Research Ball JSONL.

This is a source-level regression and discovery tool. It does not establish
physical firmware timing, battery life, cross-operator generalisation, or any
Gameplay/scoring authority.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
ENGINE_DIR = ROOT / "firmware" / "nrf54l15_tag_motion_demo" / "src"
HARNESS = ROOT / "tests_research" / "embedded_motion_raw_replay.c"
GYRO_CLIP_MICRO_RADS = 34_208_453

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
ROLLING_CONTEXT_LABELS = {
    "rolling_pickup",
    "putt_gentle",
    "putt_rail_collision",
    "track_step_drop",
}

STATE_CODES = {
    "UNKNOWN": 0,
    "STATIONARY": 1,
    "ROLLING": 2,
    "SETTLING": 3,
    "CARRIED": 4,
    "AIRBORNE": 5,
}


@dataclass(frozen=True)
class Episode:
    dataset_id: str
    manifest: Path
    episode_id: str
    label: str
    capture: Path
    session: str
    operator: str
    surface: str
    mixed: bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifests", nargs="*", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--compiler", type=Path)
    parser.add_argument(
        "--fail-on-pickup-boundary",
        action="store_true",
        help="return nonzero if a stationary pickup is missed or any other label emits pickup",
    )
    return parser.parse_args()


def portable(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path.resolve())


def is_mixed(episode: dict[str, Any]) -> bool:
    text = " ".join(
        str(episode.get(key, ""))
        for key in ("episode_id", "strength", "notes")
    ).lower()
    return (
        bool(episode.get("exclude_from_clean_metrics", False))
        or "plus-obstacle" in text
        or "planned-mixed" in text
        or "preserve as a mixed" in text
        or "exclude from clean" in text
    )


def load_manifest(path: Path) -> list[Episode]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if int(payload.get("schema_version", -1)) != 1:
        raise ValueError(f"{path}: unsupported schema_version")
    defaults = payload.get("defaults", {})
    raw_episodes = payload.get("episodes")
    if not isinstance(defaults, dict) or not isinstance(raw_episodes, list):
        raise ValueError(f"{path}: malformed manifest")
    dataset_id = str(payload.get("dataset_id", "")).strip()
    if not dataset_id:
        raise ValueError(f"{path}: missing dataset_id")

    episodes: list[Episode] = []
    for raw in raw_episodes:
        if not isinstance(raw, dict):
            raise ValueError(f"{path}: episode entry must be an object")
        item = {**defaults, **raw}
        label = str(item.get("label", "")).strip().lower()
        episode_id = str(item.get("episode_id", "")).strip()
        capture = path.parent / str(item.get("capture", ""))
        if not episode_id or not label or not capture.is_file():
            raise ValueError(f"{path}: incomplete episode {episode_id!r}")
        episodes.append(
            Episode(
                dataset_id=dataset_id,
                manifest=path,
                episode_id=episode_id,
                label=label,
                capture=capture,
                session=str(item.get("session") or "<missing>"),
                operator=str(item.get("operator") or "<missing>"),
                surface=str(item.get("surface") or "<missing>"),
                mixed=is_mixed(item),
            )
        )
    return episodes


def find_compiler(explicit: Path | None) -> str:
    if explicit is not None:
        path = explicit.expanduser().resolve()
        if not path.is_file():
            raise SystemExit(f"compiler not found: {path}")
        return str(path)
    compiler = shutil.which("cc") or shutil.which("gcc")
    if compiler is None:
        raise SystemExit("a C11 compiler (cc or gcc) is required")
    return compiler


def compile_runner(compiler: str, output: Path) -> None:
    command = [
        compiler,
        "-std=c11",
        "-O2",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-pedantic",
        f"-I{ENGINE_DIR}",
        str(ENGINE_DIR / "motion_engine.c"),
        str(HARNESS),
        "-lm",
        "-o",
        str(output),
    ]
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "embedded motion replay C compile failed:\n"
            + completed.stdout
            + completed.stderr
        )


def capture_input(path: Path) -> tuple[str, int]:
    lines: list[str] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        if not line.strip():
            continue
        payload = json.loads(line)
        if payload.get("record_type") != "tag_motion":
            continue
        accel = payload["bmi270_accel_micro_ms2"]
        gyro = payload["bmi270_gyro_micro_rads"]
        clipped = max(abs(int(value)) for value in gyro) >= GYRO_CLIP_MICRO_RADS
        values = [
            int(payload["sequence"]),
            int(payload["source_monotonic_us"]),
            *(int(value) for value in accel),
            *(int(value) for value in gyro),
            int(payload.get("sensor_error_bits", 0)),
            int(bool(payload.get("bmi270_valid", False))),
            int(clipped),
        ]
        if len(values) != 11:
            raise ValueError(f"{path}:{line_number}: malformed motion vector")
        lines.append(",".join(str(value) for value in values))
    if len(lines) < 2:
        raise ValueError(f"{path}: insufficient motion samples")
    return "\n".join(lines) + "\n", len(lines)


def replay(runner: Path, capture: Path) -> dict[str, Any]:
    input_text, expected_samples = capture_input(capture)
    completed = subprocess.run(
        [str(runner)],
        cwd=ROOT,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"{capture}: replay failed: {completed.stderr}")
    result = json.loads(completed.stdout)
    if int(result["samples"]) != expected_samples:
        raise RuntimeError(f"{capture}: replay sample-count mismatch")
    return result


def seen_state(result: dict[str, Any], state: str) -> bool:
    return bool(int(result["seen_state_mask"]) & (1 << STATE_CODES[state]))


def write_csv(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    materialized = list(rows)
    fieldnames = sorted({key for row in materialized for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(materialized)


def ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def main() -> int:
    args = parse_args()
    manifests = tuple(path.resolve() for path in args.manifests) or DEFAULT_MANIFESTS
    episodes = [
        episode
        for manifest in sorted(manifests)
        for episode in load_manifest(manifest)
    ]
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    compiler = find_compiler(args.compiler)
    with tempfile.TemporaryDirectory(
        prefix="putttrack-embedded-motion-replay-", dir=Path.home()
    ) as temporary:
        runner = Path(temporary) / "embedded_motion_raw_replay"
        compile_runner(compiler, runner)
        for episode in sorted(episodes, key=lambda item: item.episode_id):
            result = replay(runner, episode.capture)
            pickup_expected = episode.label in PICKUP_POSITIVE_LABELS
            pickup_observed = int(result["pickup_events"]) > 0
            rows.append(
                {
                    "dataset_id": episode.dataset_id,
                    "manifest": portable(episode.manifest),
                    "episode_id": episode.episode_id,
                    "label": episode.label,
                    "session": episode.session,
                    "operator": episode.operator,
                    "surface": episode.surface,
                    "mixed": episode.mixed,
                    "capture": portable(episode.capture),
                    "pickup_expected": pickup_expected,
                    "pickup_observed": pickup_observed,
                    "pickup_boundary_correct": pickup_expected == pickup_observed,
                    "pickup_event_count": int(result["pickup_events"]),
                    "seen_stationary": seen_state(result, "STATIONARY"),
                    "seen_rolling": seen_state(result, "ROLLING"),
                    "seen_settling": seen_state(result, "SETTLING"),
                    "seen_carried": seen_state(result, "CARRIED"),
                    "seen_airborne": seen_state(result, "AIRBORNE"),
                    "seen_unknown": seen_state(result, "UNKNOWN"),
                    "rolling_start_events": int(result["rolling_start_events"]),
                    "settled_events": int(result["settled_events"]),
                    "landing_events": int(result["landing_events"]),
                    "final_state": result["final_state"],
                    "state_changes": int(result["state_changes"]),
                    "quality_or": int(result["quality_or"]),
                    "maximum_confidence": int(result["maximum_confidence"]),
                    "context_bytes": int(result["context_bytes"]),
                    "samples": int(result["samples"]),
                }
            )

    positives = [row for row in rows if row["pickup_expected"]]
    negatives = [row for row in rows if not row["pickup_expected"]]
    rolling_scope = [row for row in rows if row["label"] in ROLLING_CONTEXT_LABELS]
    by_label: dict[str, dict[str, Any]] = {}
    for label in sorted({str(row["label"]) for row in rows}):
        group = [row for row in rows if row["label"] == label]
        by_label[label] = {
            "episodes": len(group),
            "pickup_events": sum(bool(row["pickup_observed"]) for row in group),
            "seen_rolling": sum(bool(row["seen_rolling"]) for row in group),
            "seen_settling": sum(bool(row["seen_settling"]) for row in group),
            "seen_carried": sum(bool(row["seen_carried"]) for row in group),
            "seen_airborne": sum(bool(row["seen_airborne"]) for row in group),
            "seen_unknown": sum(bool(row["seen_unknown"]) for row in group),
            "quality_nonzero": sum(int(row["quality_or"]) != 0 for row in group),
        }

    detected_positives = sum(bool(row["pickup_observed"]) for row in positives)
    false_pickups = sum(bool(row["pickup_observed"]) for row in negatives)
    boundary_pass = detected_positives == len(positives) and false_pickups == 0
    summary = {
        "schema_version": 1,
        "engine": "firmware/nrf54l15_tag_motion_demo/src/motion_engine.c",
        "authority": False,
        "evaluation_scope": (
            "source-level C replay on reviewed same-day raw JSONL; not physical, "
            "cross-group or product accuracy"
        ),
        "episodes": len(rows),
        "pickup_positive_episodes": len(positives),
        "pickup_positive_detected": detected_positives,
        "pickup_positive_recall_observed": ratio(detected_positives, len(positives)),
        "pickup_negative_or_unsupported_episodes": len(negatives),
        "false_pickup_episodes": false_pickups,
        "false_pickup_rate_observed": ratio(false_pickups, len(negatives)),
        "pickup_boundary_pass": boundary_pass,
        "episodes_with_duplicate_pickup_events": sum(
            int(row["pickup_event_count"]) > 1 for row in rows
        ),
        "rolling_context_episodes": len(rolling_scope),
        "rolling_context_seen_rolling": sum(
            bool(row["seen_rolling"]) for row in rolling_scope
        ),
        "seen_settling_episodes": sum(bool(row["seen_settling"]) for row in rows),
        "seen_airborne_episodes": sum(bool(row["seen_airborne"]) for row in rows),
        "seen_unknown_episodes": sum(bool(row["seen_unknown"]) for row in rows),
        "context_bytes": max(int(row["context_bytes"]) for row in rows),
        "by_label": by_label,
        "limitations": [
            "same date, operator and Ball/core; most surfaces are unspecified",
            "episode operator labels are not frame-level independent event timestamps",
            "rolling, settling and airborne thresholds are post-hoc demo hypotheses",
            "source replay does not measure MCU timing, current or radio behaviour",
            "no Ball output has Gameplay, cup, stroke-count or penalty authority",
        ],
    }
    write_csv(output_dir / "episode_replay.csv", rows)
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    if args.fail_on_pickup_boundary and not boundary_pass:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
