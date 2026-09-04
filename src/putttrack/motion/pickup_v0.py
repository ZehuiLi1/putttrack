"""Reproducible evaluator for the frozen PuttTrack stationary-start pickup V0.

This module is intentionally evidence-only.  It implements the exact motion
feature path documented in ``configs/research/pickup_detector_v0.json`` and
makes the existing pre-GO stationary policy explicit through a separate
execution profile.  It does not mutate Gameplay or score.

The implementation has no third-party dependencies and accepts the canonical
PuttTrack JSONL capture format directly.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import json
import math
from pathlib import Path
import statistics
from typing import Any, Mapping, Sequence


MICRO = 1_000_000.0


class PickupDecision(str, Enum):
    PICKUP_SUSPECTED = "PICKUP_SUSPECTED"
    NOT_PICKUP = "NOT_PICKUP"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class MotionSample:
    sequence: int
    source_monotonic_us: int
    accel_mps2: tuple[float, float, float]
    gyro_rads: tuple[float, float, float]
    adxl367_valid: bool
    bmi270_valid: bool
    sensor_error_bits: int


@dataclass(frozen=True)
class CaptureEnvelope:
    path: str
    label: str | None
    go_source_monotonic_us: int | None
    samples: tuple[MotionSample, ...]
    capture_passed: bool
    status: Mapping[str, Any] | None
    parse_warnings: tuple[str, ...]


@dataclass(frozen=True)
class PickupFeatures:
    source_rate_hz: float
    baseline_sample_count: int
    baseline_duration_s: float
    baseline_accel_norm_stdev_mps2: float
    baseline_gyro_norm_rms_rads: float
    onset_source_monotonic_us: int | None
    onset_offset_from_go_s: float | None
    positive_vertical_impulse_mps: float | None
    mean_gyro_norm_1s_rads: float | None
    gyro_axis_consistency_1s: float | None
    gyro_clip_samples_1s: int
    feature_sample_count_gyro: int
    feature_sample_count_impulse: int


@dataclass(frozen=True)
class PickupResult:
    detector_id: str
    detector_config_sha256: str
    evaluation_profile_sha256: str
    decision: PickupDecision
    reason_codes: tuple[str, ...]
    rule_passes: Mapping[str, bool]
    features: PickupFeatures | None
    authority: bool = False

    def to_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row["decision"] = self.decision.value
        return row


def _canonical_sha256(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return payload


def _tuple3(
    values: Sequence[Any], *, field: str, path: Path, line_number: int
) -> tuple[float, float, float]:
    if len(values) != 3:
        raise ValueError(f"{path}:{line_number}: {field} must contain three values")
    return tuple(float(value) / MICRO for value in values)  # type: ignore[return-value]


def read_capture_jsonl(path: Path) -> CaptureEnvelope:
    """Read the canonical capture and preserve the device-side action marker."""

    samples: list[MotionSample] = []
    labels: set[str] = set()
    go_markers: list[int] = []
    window_go_markers: list[int] = []
    status: Mapping[str, Any] | None = None
    capture_passed = False
    saw_capture_result = False
    warnings: list[str] = []

    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        if not raw_line.strip():
            continue
        try:
            payload = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_number}: invalid JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"{path}:{line_number}: expected a JSON object")

        label = payload.get("episode_label")
        if isinstance(label, str) and label.strip():
            labels.add(label.strip().lower())

        record_type = payload.get("record_type")
        if record_type == "tag_status" and status is None:
            status = payload
        elif (
            record_type == "tag_episode_marker"
            and payload.get("marker_kind") == "action_start"
        ):
            go_markers.append(int(payload["source_monotonic_us"]))
        elif (
            record_type == "tag_episode_window"
            and payload.get("action_start_source_monotonic_us") is not None
        ):
            window_go_markers.append(int(payload["action_start_source_monotonic_us"]))
        elif record_type == "tag_motion":
            accel_raw = payload.get("bmi270_accel_micro_ms2")
            gyro_raw = payload.get("bmi270_gyro_micro_rads")
            if not isinstance(accel_raw, list) or not isinstance(gyro_raw, list):
                raise ValueError(f"{path}:{line_number}: missing BMI270 vectors")
            samples.append(
                MotionSample(
                    sequence=int(payload["sequence"]),
                    source_monotonic_us=int(payload["source_monotonic_us"]),
                    accel_mps2=_tuple3(
                        accel_raw,
                        field="bmi270_accel_micro_ms2",
                        path=path,
                        line_number=line_number,
                    ),
                    gyro_rads=_tuple3(
                        gyro_raw,
                        field="bmi270_gyro_micro_rads",
                        path=path,
                        line_number=line_number,
                    ),
                    adxl367_valid=bool(payload.get("adxl367_valid", False)),
                    bmi270_valid=bool(payload.get("bmi270_valid", False)),
                    sensor_error_bits=int(payload.get("sensor_error_bits", 0)),
                )
            )
        elif record_type == "tag_capture_result":
            saw_capture_result = True
            capture_passed = payload.get("status") == "PASS"
            if not capture_passed:
                warnings.append("capture_result_not_pass")

    if not saw_capture_result:
        warnings.append("missing_capture_result")
    if len(labels) > 1:
        warnings.append("multiple_episode_labels")
    if len(go_markers) > 1:
        warnings.append("multiple_action_start_markers")
    if go_markers and window_go_markers and go_markers[0] != window_go_markers[0]:
        warnings.append("action_start_marker_mismatch")

    go = go_markers[0] if len(go_markers) == 1 else None
    if go is None and len(window_go_markers) == 1:
        go = window_go_markers[0]
        warnings.append("using_episode_window_action_start_fallback")

    return CaptureEnvelope(
        path=str(path),
        label=next(iter(labels)) if len(labels) == 1 else None,
        go_source_monotonic_us=go,
        samples=tuple(samples),
        capture_passed=capture_passed,
        status=status,
        parse_warnings=tuple(warnings),
    )


def _norm(vector: Sequence[float]) -> float:
    return math.sqrt(sum(value * value for value in vector))


def _normalize(vector: Sequence[float]) -> tuple[float, float, float]:
    magnitude = _norm(vector)
    if magnitude <= 1e-12:
        raise ValueError("cannot normalize a near-zero vector")
    return tuple(value / magnitude for value in vector)  # type: ignore[return-value]


def _cross(a: Sequence[float], b: Sequence[float]) -> tuple[float, float, float]:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _mean_vector(
    vectors: Sequence[Sequence[float]],
) -> tuple[float, float, float]:
    if not vectors:
        raise ValueError("mean vector requires samples")
    return tuple(
        statistics.fmean(vector[index] for vector in vectors) for index in range(3)
    )  # type: ignore[return-value]


def _observed_rate(samples: Sequence[MotionSample]) -> float:
    if len(samples) < 2:
        return 0.0
    duration_s = (
        samples[-1].source_monotonic_us - samples[0].source_monotonic_us
    ) / MICRO
    return (len(samples) - 1) / duration_s if duration_s > 0 else 0.0


def _slice_time(
    samples: Sequence[MotionSample],
    start_us: int,
    end_us: int,
    *,
    end_exclusive: bool = True,
) -> list[MotionSample]:
    if end_exclusive:
        return [
            sample
            for sample in samples
            if start_us <= sample.source_monotonic_us < end_us
        ]
    return [
        sample
        for sample in samples
        if start_us <= sample.source_monotonic_us <= end_us
    ]


def _structural_reasons(
    capture: CaptureEnvelope,
    detector: Mapping[str, Any],
    profile: Mapping[str, Any],
) -> list[str]:
    reasons: list[str] = []
    if not capture.capture_passed:
        reasons.append("capture_not_pass")
    if capture.go_source_monotonic_us is None:
        reasons.append("missing_device_side_go_marker")
    if len(capture.samples) < 2:
        reasons.append("insufficient_samples")
        return reasons

    for previous, current in zip(capture.samples, capture.samples[1:]):
        if current.sequence != previous.sequence + 1:
            reasons.append("sequence_gap_or_reordering")
            break
    for previous, current in zip(capture.samples, capture.samples[1:]):
        if current.source_monotonic_us <= previous.source_monotonic_us:
            reasons.append("source_time_regression")
            break
    if any(
        not sample.adxl367_valid
        or not sample.bmi270_valid
        or sample.sensor_error_bits != 0
        for sample in capture.samples
    ):
        reasons.append("sensor_invalid_or_error_bits_nonzero")

    expected_rate = float(detector["expected_source_rate_hz"])
    observed_rate = _observed_rate(capture.samples)
    tolerance = float(profile.get("source_rate_tolerance_fraction", 0.10))
    if observed_rate <= 0 or abs(observed_rate - expected_rate) > expected_rate * tolerance:
        reasons.append("unexpected_source_rate")
    if "multiple_action_start_markers" in capture.parse_warnings:
        reasons.append("multiple_action_start_markers")
    if "action_start_marker_mismatch" in capture.parse_warnings:
        reasons.append("action_start_marker_mismatch")
    return reasons


def _find_onset(
    samples: Sequence[MotionSample],
    *,
    go_us: int,
    detector: Mapping[str, Any],
) -> int | None:
    onset = detector["onset"]
    search_start = go_us + int(float(onset["search_start_after_go_s"]) * MICRO)
    candidates = [
        index
        for index, sample in enumerate(samples)
        if sample.source_monotonic_us >= search_start
    ]
    if not candidates:
        return None
    first_index = candidates[0]
    lookahead = int(onset["lookahead_samples"])
    minimum_active = int(onset["minimum_active_samples"])
    accel_threshold = float(onset["accel_norm_deviation_mps2"])
    gyro_threshold = float(onset["gyro_norm_rads"])
    gravity = float(detector["gravity_mps2"])

    for index in range(first_index, len(samples)):
        block = samples[index : index + lookahead]
        if len(block) < lookahead:
            break
        active = sum(
            abs(_norm(sample.accel_mps2) - gravity) >= accel_threshold
            or _norm(sample.gyro_rads) >= gyro_threshold
            for sample in block
        )
        if active >= minimum_active:
            return index
    return None


def _propagated_up_vectors(
    samples: Sequence[MotionSample],
    *,
    initial_up: Sequence[float],
    start_us: int,
    end_us: int,
) -> dict[int, tuple[float, float, float]]:
    """Propagate venue-up in body coordinates using the frozen Euler equation."""

    selected = [
        sample
        for sample in samples
        if start_us <= sample.source_monotonic_us < end_us
    ]
    if not selected:
        return {}
    up = _normalize(initial_up)
    output: dict[int, tuple[float, float, float]] = {selected[0].sequence: up}
    previous = selected[0]
    for current in selected[1:]:
        dt = (current.source_monotonic_us - previous.source_monotonic_us) / MICRO
        derivative = _cross(previous.gyro_rads, up)
        candidate = tuple(up[index] - derivative[index] * dt for index in range(3))
        up = _normalize(candidate)
        output[current.sequence] = up
        previous = current
    return output


def evaluate_pickup_v0(
    capture: CaptureEnvelope,
    detector: Mapping[str, Any],
    profile: Mapping[str, Any],
    *,
    manifest_label: str | None = None,
) -> PickupResult:
    """Evaluate one episode and fail closed on unsupported or corrupt evidence."""

    detector_hash = _canonical_sha256(detector)
    profile_hash = _canonical_sha256(profile)
    detector_id = str(detector.get("detector_id", "unknown-detector"))

    unsupported = set(
        str(item).lower() for item in profile.get("unsupported_manifest_labels", [])
    )
    effective_label = (manifest_label or capture.label or "").lower()
    if effective_label in unsupported:
        return PickupResult(
            detector_id=detector_id,
            detector_config_sha256=detector_hash,
            evaluation_profile_sha256=profile_hash,
            decision=PickupDecision.UNKNOWN,
            reason_codes=("unsupported_rolling_start_path",),
            rule_passes={},
            features=None,
        )

    reasons = _structural_reasons(capture, detector, profile)
    if reasons:
        return PickupResult(
            detector_id=detector_id,
            detector_config_sha256=detector_hash,
            evaluation_profile_sha256=profile_hash,
            decision=PickupDecision.UNKNOWN,
            reason_codes=tuple(sorted(set(reasons))),
            rule_passes={},
            features=None,
        )

    assert capture.go_source_monotonic_us is not None
    go_us = capture.go_source_monotonic_us
    expected_rate = float(detector["expected_source_rate_hz"])
    baseline_seconds = float(detector["required_pre_go_stationary_s"])
    baseline_start = go_us - int(baseline_seconds * MICRO)
    baseline = _slice_time(capture.samples, baseline_start, go_us)
    baseline_policy = profile["pre_go_stationary"]
    expected_baseline_samples = expected_rate * baseline_seconds
    minimum_baseline_samples = math.ceil(
        expected_baseline_samples
        * float(baseline_policy["minimum_sample_fraction_of_expected"])
    )
    if len(baseline) < minimum_baseline_samples:
        return PickupResult(
            detector_id=detector_id,
            detector_config_sha256=detector_hash,
            evaluation_profile_sha256=profile_hash,
            decision=PickupDecision.UNKNOWN,
            reason_codes=("insufficient_pre_go_baseline_samples",),
            rule_passes={},
            features=None,
        )

    baseline_duration = (
        baseline[-1].source_monotonic_us - baseline[0].source_monotonic_us
    ) / MICRO
    accel_norms = [_norm(sample.accel_mps2) for sample in baseline]
    gyro_norms = [_norm(sample.gyro_rads) for sample in baseline]
    baseline_accel_sd = statistics.pstdev(accel_norms)
    baseline_gyro_rms = math.sqrt(
        statistics.fmean(value * value for value in gyro_norms)
    )
    baseline_stationary = (
        baseline_duration >= float(baseline_policy["minimum_duration_s"])
        and baseline_accel_sd
        <= float(baseline_policy["maximum_accel_norm_stdev_mps2"])
        and baseline_gyro_rms
        <= float(baseline_policy["maximum_gyro_norm_rms_rads"])
    )
    if not baseline_stationary:
        return PickupResult(
            detector_id=detector_id,
            detector_config_sha256=detector_hash,
            evaluation_profile_sha256=profile_hash,
            decision=PickupDecision.UNKNOWN,
            reason_codes=("pre_go_baseline_not_stationary",),
            rule_passes={},
            features=PickupFeatures(
                source_rate_hz=_observed_rate(capture.samples),
                baseline_sample_count=len(baseline),
                baseline_duration_s=baseline_duration,
                baseline_accel_norm_stdev_mps2=baseline_accel_sd,
                baseline_gyro_norm_rms_rads=baseline_gyro_rms,
                onset_source_monotonic_us=None,
                onset_offset_from_go_s=None,
                positive_vertical_impulse_mps=None,
                mean_gyro_norm_1s_rads=None,
                gyro_axis_consistency_1s=None,
                gyro_clip_samples_1s=0,
                feature_sample_count_gyro=0,
                feature_sample_count_impulse=0,
            ),
        )

    onset_index = _find_onset(capture.samples, go_us=go_us, detector=detector)
    if onset_index is None:
        return PickupResult(
            detector_id=detector_id,
            detector_config_sha256=detector_hash,
            evaluation_profile_sha256=profile_hash,
            decision=PickupDecision.NOT_PICKUP,
            reason_codes=("no_motion_onset",),
            rule_passes={
                "positive_vertical_impulse": False,
                "mean_gyro_norm": False,
                "axis_consistency": False,
            },
            features=PickupFeatures(
                source_rate_hz=_observed_rate(capture.samples),
                baseline_sample_count=len(baseline),
                baseline_duration_s=baseline_duration,
                baseline_accel_norm_stdev_mps2=baseline_accel_sd,
                baseline_gyro_norm_rms_rads=baseline_gyro_rms,
                onset_source_monotonic_us=None,
                onset_offset_from_go_s=None,
                positive_vertical_impulse_mps=None,
                mean_gyro_norm_1s_rads=None,
                gyro_axis_consistency_1s=None,
                gyro_clip_samples_1s=0,
                feature_sample_count_gyro=0,
                feature_sample_count_impulse=0,
            ),
        )

    onset_sample = capture.samples[onset_index]
    onset_us = onset_sample.source_monotonic_us
    impulse_config = detector["vertical_impulse"]
    gyro_config = detector["gyro_shape"]
    impulse_start = onset_us + int(
        float(impulse_config["window_start_relative_to_onset_s"]) * MICRO
    )
    impulse_end = onset_us + int(
        float(impulse_config["window_end_relative_to_onset_s"]) * MICRO
    )
    gyro_start = onset_us + int(
        float(gyro_config["window_start_relative_to_onset_s"]) * MICRO
    )
    gyro_end = onset_us + int(
        float(gyro_config["window_end_relative_to_onset_s"]) * MICRO
    )

    impulse_samples = _slice_time(capture.samples, impulse_start, impulse_end)
    gyro_samples = _slice_time(capture.samples, gyro_start, gyro_end)
    required_impulse = max(
        2,
        math.floor(
            (impulse_end - impulse_start) / MICRO * expected_rate * 0.8
        ),
    )
    required_gyro = max(
        2,
        math.floor((gyro_end - gyro_start) / MICRO * expected_rate * 0.8),
    )
    if len(impulse_samples) < required_impulse or len(gyro_samples) < required_gyro:
        return PickupResult(
            detector_id=detector_id,
            detector_config_sha256=detector_hash,
            evaluation_profile_sha256=profile_hash,
            decision=PickupDecision.UNKNOWN,
            reason_codes=("insufficient_feature_window",),
            rule_passes={},
            features=None,
        )

    gyro_clip_boundary = int(profile["bmi270_gyro_clip_micro_rads"]) / MICRO
    clipped = sum(
        max(abs(value) for value in sample.gyro_rads) >= gyro_clip_boundary
        for sample in gyro_samples
    )
    if clipped:
        features = PickupFeatures(
            source_rate_hz=_observed_rate(capture.samples),
            baseline_sample_count=len(baseline),
            baseline_duration_s=baseline_duration,
            baseline_accel_norm_stdev_mps2=baseline_accel_sd,
            baseline_gyro_norm_rms_rads=baseline_gyro_rms,
            onset_source_monotonic_us=onset_us,
            onset_offset_from_go_s=(onset_us - go_us) / MICRO,
            positive_vertical_impulse_mps=None,
            mean_gyro_norm_1s_rads=None,
            gyro_axis_consistency_1s=None,
            gyro_clip_samples_1s=clipped,
            feature_sample_count_gyro=len(gyro_samples),
            feature_sample_count_impulse=len(impulse_samples),
        )
        return PickupResult(
            detector_id=detector_id,
            detector_config_sha256=detector_hash,
            evaluation_profile_sha256=profile_hash,
            decision=PickupDecision.UNKNOWN,
            reason_codes=("bmi270_gyro_clipping_inside_feature_window",),
            rule_passes={},
            features=features,
        )

    initial_up = _mean_vector([sample.accel_mps2 for sample in baseline])
    propagation_start = go_us
    propagation_end = max(impulse_end, gyro_end) + int(MICRO / expected_rate)
    up_by_sequence = _propagated_up_vectors(
        capture.samples,
        initial_up=initial_up,
        start_us=propagation_start,
        end_us=propagation_end,
    )
    gravity = float(detector["gravity_mps2"])
    positive_impulse = 0.0
    for previous, current in zip(impulse_samples, impulse_samples[1:]):
        dt = (current.source_monotonic_us - previous.source_monotonic_us) / MICRO
        up = up_by_sequence.get(current.sequence)
        if up is None:
            continue
        vertical_dynamic = _dot(current.accel_mps2, up) - gravity
        positive_impulse += max(0.0, vertical_dynamic) * dt

    gyro_vectors = [sample.gyro_rads for sample in gyro_samples]
    gyro_norms = [_norm(vector) for vector in gyro_vectors]
    mean_gyro_norm = statistics.fmean(gyro_norms)
    mean_gyro_vector = _mean_vector(gyro_vectors)
    axis_consistency = (
        _norm(mean_gyro_vector) / mean_gyro_norm if mean_gyro_norm > 1e-12 else 0.0
    )

    features = PickupFeatures(
        source_rate_hz=_observed_rate(capture.samples),
        baseline_sample_count=len(baseline),
        baseline_duration_s=baseline_duration,
        baseline_accel_norm_stdev_mps2=baseline_accel_sd,
        baseline_gyro_norm_rms_rads=baseline_gyro_rms,
        onset_source_monotonic_us=onset_us,
        onset_offset_from_go_s=(onset_us - go_us) / MICRO,
        positive_vertical_impulse_mps=positive_impulse,
        mean_gyro_norm_1s_rads=mean_gyro_norm,
        gyro_axis_consistency_1s=axis_consistency,
        gyro_clip_samples_1s=0,
        feature_sample_count_gyro=len(gyro_samples),
        feature_sample_count_impulse=len(impulse_samples),
    )

    impulse_pass = positive_impulse > float(impulse_config["minimum_mps"])
    gyro_pass = mean_gyro_norm < float(gyro_config["maximum_mean_norm_rads"])
    axis_pass = axis_consistency < float(
        gyro_config["maximum_axis_consistency"]
    )
    passes = {
        "positive_vertical_impulse": impulse_pass,
        "mean_gyro_norm": gyro_pass,
        "axis_consistency": axis_pass,
    }
    decision = (
        PickupDecision.PICKUP_SUSPECTED
        if all(passes.values())
        else PickupDecision.NOT_PICKUP
    )
    failed = tuple(name for name, passed in passes.items() if not passed)
    return PickupResult(
        detector_id=detector_id,
        detector_config_sha256=detector_hash,
        evaluation_profile_sha256=profile_hash,
        decision=decision,
        reason_codes=failed,
        rule_passes=passes,
        features=features,
    )


def evaluate_capture_path(
    capture_path: Path,
    detector_config_path: Path,
    evaluation_profile_path: Path,
    *,
    manifest_label: str | None = None,
) -> PickupResult:
    detector = load_json(detector_config_path)
    profile = load_json(evaluation_profile_path)
    capture = read_capture_jsonl(capture_path)
    return evaluate_pickup_v0(
        capture,
        detector,
        profile,
        manifest_label=manifest_label,
    )


__all__ = [
    "CaptureEnvelope",
    "MotionSample",
    "PickupDecision",
    "PickupFeatures",
    "PickupResult",
    "evaluate_capture_path",
    "evaluate_pickup_v0",
    "load_json",
    "read_capture_jsonl",
]
