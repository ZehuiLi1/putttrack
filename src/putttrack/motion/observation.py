"""Build canonical generic-motion observations from validated Tag windows."""

from __future__ import annotations

import hashlib
import statistics
from typing import Sequence

from putttrack.contracts import MotionObservation
from putttrack.tag import MotionRecord, StatusRecord

from .features import extract_window_features, provisional_generic_motion_check


def build_provisional_motion_observation(
    records: Sequence[MotionRecord],
    status: StatusRecord,
    *,
    ball_id: str,
    hole_id: str,
    raw_window_ref: str,
    edge_received_ns: int,
    trace_id: str | None = None,
    correlation_id: str | None = None,
) -> MotionObservation:
    """Create a diagnostic-only observation without inventing confidence.

    The current classifier only separates measured stationary data from
    unmistakably active generic motion. Its confidence is therefore exported
    as zero and explicitly marked uncalibrated. A later measured classifier
    must replace that value before motion can participate in confirmation
    policy.
    """

    if not ball_id.strip() or not hole_id.strip() or not raw_window_ref.strip():
        raise ValueError("ball_id, hole_id and raw_window_ref are required")
    if edge_received_ns < 0:
        raise ValueError("edge_received_ns must be non-negative")

    features = extract_window_features(records)
    diagnostic = provisional_generic_motion_check(features)
    first = records[0]
    last = records[-1]
    identity = (
        f"{status.device_id}:{status.boot_id}:{first.sequence}:{last.sequence}:"
        "provisional-generic-motion-smoke-v0"
    )
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]

    def mean_axis(values: Sequence[tuple[int, int, int]], axis: int) -> float:
        return statistics.fmean(item[axis] for item in values) / 1_000_000.0

    accelerations = [record.bmi270_accel_micro_ms2 for record in records]
    gyros = [record.bmi270_gyro_micro_rads for record in records]
    return MotionObservation(
        event_id=f"motion-{digest}",
        event_type="ball.motion_observed",
        source_device_id=status.device_id,
        source_boot_id=status.boot_id,
        sequence=last.sequence,
        source_monotonic_ns=last.source_monotonic_us * 1_000,
        edge_received_ns=edge_received_ns,
        trace_id=trace_id or f"tag-{status.device_id}-{status.boot_id}",
        correlation_id=correlation_id,
        hole_id=hole_id,
        ball_id=ball_id,
        firmware_version=status.firmware_version,
        config_version="tag-motion-protocol-v1-50hz",
        model_version="provisional-generic-motion-smoke-v0",
        raw_evidence_refs=(raw_window_ref,),
        motion_state=diagnostic.state,
        confidence=0.0,
        accel_mps2=tuple(mean_axis(accelerations, axis) for axis in range(3)),
        gyro_rads=tuple(mean_axis(gyros, axis) for axis in range(3)),
        raw_window_ref=raw_window_ref,
        extensions={
            "diagnostic_only": True,
            "confidence_calibrated": False,
            "diagnostic_passed": diagnostic.passed,
            "diagnostic_reasons": list(diagnostic.reasons),
            "window_features": features.to_dict(),
            "sensor_config": {
                "stream_rate_hz": status.stream_rate_hz,
                "adxl367_odr_hz": status.adxl367_odr_hz,
                "adxl367_range_g": status.adxl367_range_g,
                "bmi270_accel_odr_hz": status.bmi270_accel_odr_hz,
                "bmi270_accel_range_g": status.bmi270_accel_range_g,
                "bmi270_gyro_odr_hz": status.bmi270_gyro_odr_hz,
                "bmi270_gyro_range_dps": status.bmi270_gyro_range_dps,
            },
            "clip_counts_at_capture": {
                "adxl367": status.adxl367_clip_count,
                "bmi270_accel": status.bmi270_accel_clip_count,
                "bmi270_gyro": status.bmi270_gyro_clip_count,
            },
        },
    )
