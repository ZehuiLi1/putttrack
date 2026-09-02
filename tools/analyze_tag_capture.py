#!/usr/bin/env python3
"""Extract generic motion features from a Tag capture JSONL file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from putttrack.contracts import canonical_json  # noqa: E402
from putttrack.motion import (  # noqa: E402
    build_provisional_motion_observation,
    extract_window_features,
    provisional_generic_motion_check,
)
from putttrack.tag import MotionRecord, StatusRecord  # noqa: E402


def motion_from_json(payload: dict[str, object]) -> MotionRecord:
    return MotionRecord(
        protocol_version=int(payload["protocol_version"]),
        sequence=int(payload["sequence"]),
        source_monotonic_us=int(payload["source_monotonic_us"]),
        adxl367_valid=bool(payload["adxl367_valid"]),
        bmi270_valid=bool(payload["bmi270_valid"]),
        adxl367_accel_micro_ms2=tuple(int(value) for value in payload["adxl367_accel_micro_ms2"]),
        bmi270_accel_micro_ms2=tuple(int(value) for value in payload["bmi270_accel_micro_ms2"]),
        bmi270_gyro_micro_rads=tuple(int(value) for value in payload["bmi270_gyro_micro_rads"]),
        sensor_error_bits=int(payload["sensor_error_bits"]),
    )


def status_from_json(payload: dict[str, object]) -> StatusRecord:
    return StatusRecord(
        protocol_version=int(payload["protocol_version"]),
        sequence=int(payload["sequence"]),
        uptime_ms=int(payload["uptime_ms"]),
        reset_cause=int(payload["reset_cause"]),
        sensor_error_count=int(payload["sensor_error_count"]),
        notify_drop_count=int(payload["notify_drop_count"]),
        adxl367_ready=bool(payload["adxl367_ready"]),
        bmi270_ready=bool(payload["bmi270_ready"]),
        notify_active=bool(payload["notify_active"]),
        device_id=str(payload["device_id"]),
        boot_id=str(payload["boot_id"]),
        firmware_version=str(payload["firmware_version"]),
        stream_rate_hz=(
            int(payload["stream_rate_hz"])
            if payload.get("stream_rate_hz") is not None
            else None
        ),
        adxl367_odr_hz=(
            int(payload["adxl367_odr_hz"])
            if payload.get("adxl367_odr_hz") is not None
            else None
        ),
        adxl367_range_g=(
            int(payload["adxl367_range_g"])
            if payload.get("adxl367_range_g") is not None
            else None
        ),
        bmi270_accel_odr_hz=(
            int(payload["bmi270_accel_odr_hz"])
            if payload.get("bmi270_accel_odr_hz") is not None
            else None
        ),
        bmi270_accel_range_g=(
            int(payload["bmi270_accel_range_g"])
            if payload.get("bmi270_accel_range_g") is not None
            else None
        ),
        bmi270_gyro_odr_hz=(
            int(payload["bmi270_gyro_odr_hz"])
            if payload.get("bmi270_gyro_odr_hz") is not None
            else None
        ),
        bmi270_gyro_range_dps=(
            int(payload["bmi270_gyro_range_dps"])
            if payload.get("bmi270_gyro_range_dps") is not None
            else None
        ),
        adxl367_clip_count=int(payload.get("adxl367_clip_count", 0)),
        bmi270_accel_clip_count=int(payload.get("bmi270_accel_clip_count", 0)),
        bmi270_gyro_clip_count=int(payload.get("bmi270_gyro_clip_count", 0)),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--emit-observation", type=Path)
    parser.add_argument("--ball-id")
    parser.add_argument("--hole-id")
    parser.add_argument("--trace-id")
    parser.add_argument("--correlation-id")
    args = parser.parse_args()

    if args.emit_observation and (not args.ball_id or not args.hole_id):
        parser.error("--emit-observation requires --ball-id and --hole-id")

    records = []
    status = None
    final_status = None
    edge_received_ns = 0
    episode_labels: set[str] = set()
    capture_result = None
    for line_number, line in enumerate(args.capture.read_text(encoding="utf-8").splitlines(), 1):
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise SystemExit(f"line {line_number} is not a JSON object")
        if payload.get("record_type") == "tag_motion":
            records.append(motion_from_json(payload))
            edge_received_ns = max(edge_received_ns, int(payload["host_received_ns"]))
        elif payload.get("record_type") == "tag_status" and status is None:
            status = status_from_json(payload)
        elif payload.get("record_type") == "tag_status_final":
            final_status = status_from_json(payload)
        elif payload.get("record_type") == "tag_capture_result":
            capture_result = payload
        label = payload.get("episode_label")
        if isinstance(label, str) and label.strip():
            episode_labels.add(label.strip().lower())

    if capture_result is not None and capture_result.get("status") != "PASS":
        issues = capture_result.get("issues", [])
        raise SystemExit(
            f"capture continuity failed ({issues}); refusing motion analysis"
        )

    features = extract_window_features(records)
    diagnostic = provisional_generic_motion_check(features)
    expected_states = {
        "stationary": ("STATIONARY_CANDIDATE",),
        "pickup_carry": ("ACTIVE_MOTION_CANDIDATE",),
        "handling": ("UNCLASSIFIED", "ACTIVE_MOTION_CANDIDATE"),
    }
    if len(episode_labels) > 1:
        label_consistency = {
            "status": "FAIL",
            "labels": sorted(episode_labels),
            "reason": "capture_contains_multiple_episode_labels",
        }
    elif episode_labels and next(iter(episode_labels)) in expected_states:
        episode_label = next(iter(episode_labels))
        allowed_states = expected_states[episode_label]
        label_consistency = {
            "status": (
                "PASS" if diagnostic.state in allowed_states else "FAIL"
            ),
            "label": episode_label,
            "allowed_states": list(allowed_states),
            "observed_state": diagnostic.state,
        }
    else:
        label_consistency = {
            "status": "NOT_CHECKED",
            "labels": sorted(episode_labels),
            "reason": "no_validated_expectation_for_episode_label",
        }
    observation = None
    if args.emit_observation:
        if label_consistency["status"] == "FAIL":
            raise SystemExit(
                "episode label is inconsistent with measured motion; refusing to emit observation"
            )
        if status is None:
            raise SystemExit("capture contains no tag_status record")
        observation = build_provisional_motion_observation(
            records,
            final_status or status,
            ball_id=args.ball_id,
            hole_id=args.hole_id,
            raw_window_ref=str(args.capture),
            edge_received_ns=edge_received_ns,
            trace_id=args.trace_id,
            correlation_id=args.correlation_id,
        )
        args.emit_observation.parent.mkdir(parents=True, exist_ok=True)
        with args.emit_observation.open("x", encoding="utf-8") as output:
            output.write(canonical_json(observation) + "\n")
    print(
        json.dumps(
            {
                "capture": str(args.capture),
                "features": features.to_dict(),
                "label_consistency": label_consistency,
                "provisional_diagnostic": diagnostic.to_dict(),
                "observation_output": (
                    str(args.emit_observation) if args.emit_observation else None
                ),
                "observation_event_id": observation.event_id if observation else None,
                "warning": "development smoke thresholds only; not authoritative gameplay evidence",
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 1 if label_consistency["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
