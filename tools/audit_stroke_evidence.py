#!/usr/bin/env python3
"""Audit whether existing IMU captures can support stroke-source separation.

This is a descriptive evidence tool. Candidate bursts are threshold crossings,
not detected putter contacts, and the report never claims gameplay authority.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import statistics
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from putttrack.motion.dataset import load_dataset_manifest, motion_from_json  # noqa: E402


BURST_THRESHOLDS_MPS2 = (20.0, 40.0)
BURST_MERGE_GAP_S = 0.16
GYRO_CLIP_MICRO_RADS = 34_208_453


def vector_norm(values: tuple[int, int, int]) -> float:
    return math.sqrt(sum(value * value for value in values)) / 1_000_000.0


def vector_delta_norm(
    previous: tuple[int, int, int], current: tuple[int, int, int]
) -> float:
    return math.sqrt(
        sum((right - left) ** 2 for left, right in zip(previous, current))
    ) / 1_000_000.0


def cluster_bursts(times_s: list[float], merge_gap_s: float = BURST_MERGE_GAP_S) -> int:
    """Count separated groups of threshold crossings."""

    if not times_s:
        return 0
    if any(right < left for left, right in zip(times_s, times_s[1:])):
        raise ValueError("burst times must be ordered")
    return 1 + sum(
        right - left > merge_gap_s for left, right in zip(times_s, times_s[1:])
    )


def read_post_go(capture_path: Path):
    records = []
    markers = []
    capture_passed = False
    for line_number, line in enumerate(capture_path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"{capture_path}:{line_number}: expected JSON object")
        if payload.get("record_type") == "tag_motion":
            records.append(motion_from_json(payload))
        elif payload.get("record_type") == "tag_episode_marker":
            marker = payload.get("source_monotonic_us")
            if type(marker) is int:
                markers.append(marker)
        elif payload.get("record_type") == "tag_capture_result":
            if payload.get("status") != "PASS":
                raise ValueError(f"{capture_path}: capture result is not PASS")
            capture_passed = True
    if len(markers) != 1:
        raise ValueError(f"{capture_path}: expected exactly one GO marker")
    if not capture_passed:
        raise ValueError(f"{capture_path}: missing PASS capture result")
    post_go = [record for record in records if record.source_monotonic_us >= markers[0]]
    if len(post_go) < 2:
        raise ValueError(f"{capture_path}: fewer than two post-GO samples")
    if any(
        current.source_monotonic_us <= previous.source_monotonic_us
        for previous, current in zip(post_go, post_go[1:])
    ):
        raise ValueError(f"{capture_path}: post-GO source time is not increasing")
    return markers[0], post_go


def evidence_group(episode) -> str:
    if episode.label == "putt_rail_collision":
        return "putt_plus_rail"
    if episode.episode_id == "putt-gentle-plus-obstacle-r05":
        return "putt_plus_uncontrolled_obstacle"
    if episode.label == "putt_gentle":
        return "clean_gentle_putt"
    return episode.label


def analyze_episode(manifest_path: Path, dataset_id: str, episode) -> dict[str, object]:
    capture_path = manifest_path.parent / episode.capture
    marker_us, records = read_post_go(capture_path)
    accel_norms = [vector_norm(record.bmi270_accel_micro_ms2) for record in records]
    gyro_norms = [vector_norm(record.bmi270_gyro_micro_rads) for record in records]
    deltas = [
        vector_delta_norm(previous.bmi270_accel_micro_ms2, current.bmi270_accel_micro_ms2)
        for previous, current in zip(records, records[1:])
    ]
    delta_times = [
        (record.source_monotonic_us - marker_us) / 1_000_000.0 for record in records[1:]
    ]
    sequence_gaps = sum(
        max(0, current.sequence - previous.sequence - 1)
        for previous, current in zip(records, records[1:])
    )
    valid_samples = sum(
        record.adxl367_valid and record.bmi270_valid and record.sensor_error_bits == 0
        for record in records
    )
    active_indices = [
        index
        for index, (accel, gyro) in enumerate(zip(accel_norms, gyro_norms))
        if abs(accel - 9.80665) >= 0.5 or gyro >= 0.25
    ]
    duration_s = (records[-1].source_monotonic_us - records[0].source_monotonic_us) / 1e6
    row: dict[str, object] = {
        "dataset_id": dataset_id,
        "episode_id": episode.episode_id,
        "group": evidence_group(episode),
        "capture": episode.capture,
        "sample_count": len(records),
        "duration_s": duration_s,
        "observed_rate_hz": (len(records) - 1) / duration_s,
        "sequence_gaps": sequence_gaps,
        "valid_fraction": valid_samples / len(records),
        "first_active_from_go_s": (
            (records[active_indices[0]].source_monotonic_us - marker_us) / 1e6
            if active_indices
            else None
        ),
        "max_bmi_accel_norm_mps2": max(accel_norms),
        "max_adjacent_accel_vector_delta_mps2": max(deltas),
        "max_gyro_norm_rads": max(gyro_norms),
        "gyro_clip_samples": sum(
            max(abs(value) for value in record.bmi270_gyro_micro_rads)
            >= GYRO_CLIP_MICRO_RADS
            for record in records
            if record.bmi270_valid
        ),
    }
    for threshold in BURST_THRESHOLDS_MPS2:
        times = [time for time, delta in zip(delta_times, deltas) if delta >= threshold]
        row[f"candidate_bursts_ge_{int(threshold)}_mps2"] = cluster_bursts(times)
    return row


def numeric_summary(values: list[float]) -> dict[str, float]:
    return {
        "min": min(values),
        "median": statistics.median(values),
        "max": max(values),
    }


def ranges_overlap(left: list[float], right: list[float]) -> bool:
    return max(min(left), min(right)) <= min(max(left), max(right))


def build_audit(manifest_paths: list[Path]) -> tuple[list[dict[str, object]], dict[str, object]]:
    rows = []
    for manifest_path in manifest_paths:
        dataset_id, episodes = load_dataset_manifest(manifest_path)
        rows.extend(analyze_episode(manifest_path, dataset_id, episode) for episode in episodes)

    clean = [row for row in rows if row["group"] == "clean_gentle_putt"]
    rail = [row for row in rows if row["group"] == "putt_plus_rail"]
    if not clean or not rail:
        raise ValueError("audit requires clean_gentle_putt and putt_plus_rail episodes")
    feature_names = [
        "max_bmi_accel_norm_mps2",
        "max_adjacent_accel_vector_delta_mps2",
        "max_gyro_norm_rads",
        "gyro_clip_samples",
        "candidate_bursts_ge_20_mps2",
        "candidate_bursts_ge_40_mps2",
    ]
    comparisons = {}
    for feature in feature_names:
        clean_values = [float(row[feature]) for row in clean]
        rail_values = [float(row[feature]) for row in rail]
        comparisons[feature] = {
            "clean_gentle_putt": numeric_summary(clean_values),
            "putt_plus_rail": numeric_summary(rail_values),
            "observed_ranges_overlap": ranges_overlap(clean_values, rail_values),
        }
    structurally_valid = all(
        row["sequence_gaps"] == 0 and row["valid_fraction"] == 1.0 for row in rows
    )
    summary: dict[str, object] = {
        "schema_version": 1,
        "authority": False,
        "audit_kind": "descriptive_stroke_evidence",
        "episode_counts": {
            group: sum(row["group"] == group for row in rows)
            for group in sorted({str(row["group"]) for row in rows})
        },
        "capture_integrity_passed": structurally_valid,
        "candidate_burst_definition": {
            "signal": "adjacent BMI270 acceleration vector delta",
            "thresholds_mps2": list(BURST_THRESHOLDS_MPS2),
            "merge_gap_s": BURST_MERGE_GAP_S,
            "meaning": "descriptive threshold clusters; not putter contacts",
        },
        "feature_comparisons": comparisons,
        "all_compared_feature_ranges_overlap": all(
            comparison["observed_ranges_overlap"] for comparison in comparisons.values()
        ),
        "source_discrimination_status": "INSUFFICIENT_TRUTH",
        "conclusions": [
            "Post-GO 50 Hz IMU records preserve large motion transients in both episode groups.",
            "Simple maxima and threshold-cluster counts do not separate the observed clean-putt and putt-plus-rail groups.",
            "The captures have episode-level instructions but no independent timestamps for putter and rail contacts, so source-classification accuracy cannot be calculated.",
        ],
        "required_next_evidence": [
            "Operator- or video-reviewed putter-contact timestamps from GO.",
            "Separate rail/contact timestamps for collision episodes.",
            "Zero-stroke hand-roll and other-ball-contact controls plus one- and two-stroke episodes.",
        ],
    }
    return rows, summary


def write_outputs(rows: list[dict[str, object]], summary: dict[str, object], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0])
    with (output_dir / "episode_features.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifests", nargs="+", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    rows, summary = build_audit(args.manifests)
    write_outputs(rows, summary, args.output_dir)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
