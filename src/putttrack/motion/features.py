"""Orientation-independent features for generic Tag motion windows."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import statistics
from typing import Any, Sequence

from putttrack.tag import MotionRecord


@dataclass(frozen=True)
class MotionWindowFeatures:
    sample_count: int
    duration_s: float
    observed_rate_hz: float
    sequence_gaps: int
    valid_fraction: float
    accel_norm_mean_mps2: float
    accel_norm_stdev_mps2: float
    accel_norm_min_mps2: float
    accel_norm_max_mps2: float
    gyro_norm_rms_rads: float
    gyro_norm_max_rads: float
    jerk_norm_rms_mps3: float
    jerk_norm_peak_mps3: float
    active_sample_fraction: float
    first_active_offset_s: float | None
    last_active_offset_s: float | None
    adxl367_clip_samples: int
    bmi270_accel_clip_samples: int
    bmi270_gyro_clip_samples: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProvisionalStationaryThresholds:
    """Development smoke gates; these are not measured product thresholds."""

    min_duration_s: float = 1.0
    min_valid_fraction: float = 1.0
    max_sequence_gaps: int = 0
    max_accel_norm_stdev_mps2: float = 0.15
    max_gyro_norm_rms_rads: float = 0.08


@dataclass(frozen=True)
class ProvisionalGenericMotionThresholds:
    """Wide smoke-test separation between stationary and clearly active motion.

    These gates are deliberately not a pickup, impact or rolling classifier.
    They only preserve the measured distinction between the physical stationary
    baseline and unmistakable motion while more labelled episode families are
    collected.
    """

    min_duration_s: float = 1.0
    min_valid_fraction: float = 1.0
    max_sequence_gaps: int = 0
    max_stationary_accel_norm_stdev_mps2: float = 0.15
    max_stationary_gyro_norm_rms_rads: float = 0.08
    min_active_accel_norm_stdev_mps2: float = 0.5
    min_active_gyro_norm_rms_rads: float = 0.25


@dataclass(frozen=True)
class ProvisionalMotionResult:
    state: str
    passed: bool
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _norm(values: tuple[int, int, int]) -> float:
    return math.sqrt(sum(value * value for value in values)) / 1_000_000.0


def extract_window_features(records: Sequence[MotionRecord]) -> MotionWindowFeatures:
    """Extract deterministic SI-unit features from a source-ordered window."""

    if len(records) < 2:
        raise ValueError("motion feature extraction requires at least two samples")
    if any(
        current.sequence <= previous.sequence
        for previous, current in zip(records, records[1:])
    ):
        raise ValueError("motion records must be strictly increasing by sequence")
    if any(
        current.source_monotonic_us <= previous.source_monotonic_us
        for previous, current in zip(records, records[1:])
    ):
        raise ValueError("motion records must be strictly increasing in source time")

    duration_s = (
        records[-1].source_monotonic_us - records[0].source_monotonic_us
    ) / 1_000_000.0
    accel_norms = [_norm(record.bmi270_accel_micro_ms2) for record in records]
    gyro_norms = [_norm(record.bmi270_gyro_micro_rads) for record in records]
    active_indices = [
        index
        for index, (accel_norm, gyro_norm) in enumerate(zip(accel_norms, gyro_norms))
        if abs(accel_norm - 9.80665) >= 0.5 or gyro_norm >= 0.25
    ]
    jerk = [
        abs(current_accel - previous_accel)
        / ((current.source_monotonic_us - previous.source_monotonic_us) / 1_000_000.0)
        for previous, current, previous_accel, current_accel in zip(
            records,
            records[1:],
            accel_norms,
            accel_norms[1:],
        )
    ]
    gaps = sum(
        max(0, current.sequence - previous.sequence - 1)
        for previous, current in zip(records, records[1:])
    )
    valid_count = sum(
        record.adxl367_valid
        and record.bmi270_valid
        and record.sensor_error_bits == 0
        for record in records
    )

    return MotionWindowFeatures(
        sample_count=len(records),
        duration_s=duration_s,
        observed_rate_hz=(len(records) - 1) / duration_s,
        sequence_gaps=gaps,
        valid_fraction=valid_count / len(records),
        accel_norm_mean_mps2=statistics.fmean(accel_norms),
        accel_norm_stdev_mps2=statistics.pstdev(accel_norms),
        accel_norm_min_mps2=min(accel_norms),
        accel_norm_max_mps2=max(accel_norms),
        gyro_norm_rms_rads=math.sqrt(statistics.fmean(value * value for value in gyro_norms)),
        gyro_norm_max_rads=max(gyro_norms),
        jerk_norm_rms_mps3=math.sqrt(statistics.fmean(value * value for value in jerk)),
        jerk_norm_peak_mps3=max(jerk),
        active_sample_fraction=len(active_indices) / len(records),
        first_active_offset_s=(
            (
                records[active_indices[0]].source_monotonic_us
                - records[0].source_monotonic_us
            )
            / 1_000_000.0
            if active_indices
            else None
        ),
        last_active_offset_s=(
            (
                records[active_indices[-1]].source_monotonic_us
                - records[0].source_monotonic_us
            )
            / 1_000_000.0
            if active_indices
            else None
        ),
        adxl367_clip_samples=sum(
            max(abs(value) for value in record.adxl367_accel_micro_ms2) >= 19_221_034
            for record in records
            if record.adxl367_valid
        ),
        bmi270_accel_clip_samples=sum(
            max(abs(value) for value in record.bmi270_accel_micro_ms2) >= 153_768_272
            for record in records
            if record.bmi270_valid
        ),
        bmi270_gyro_clip_samples=sum(
            max(abs(value) for value in record.bmi270_gyro_micro_rads) >= 34_208_453
            for record in records
            if record.bmi270_valid
        ),
    )


def provisional_stationary_check(
    features: MotionWindowFeatures,
    thresholds: ProvisionalStationaryThresholds | None = None,
) -> ProvisionalMotionResult:
    """Apply conservative lab smoke gates without claiming gameplay authority."""

    gates = thresholds or ProvisionalStationaryThresholds()
    failures = []
    if features.duration_s < gates.min_duration_s:
        failures.append("duration")
    if features.valid_fraction < gates.min_valid_fraction:
        failures.append("sensor_validity")
    if features.sequence_gaps > gates.max_sequence_gaps:
        failures.append("sequence_gaps")
    if features.accel_norm_stdev_mps2 > gates.max_accel_norm_stdev_mps2:
        failures.append("accel_variability")
    if features.gyro_norm_rms_rads > gates.max_gyro_norm_rms_rads:
        failures.append("gyro_activity")
    passed = not failures
    return ProvisionalMotionResult(
        state="STATIONARY_CANDIDATE" if passed else "UNCLASSIFIED",
        passed=passed,
        reasons=tuple(failures),
    )


def provisional_generic_motion_check(
    features: MotionWindowFeatures,
    thresholds: ProvisionalGenericMotionThresholds | None = None,
) -> ProvisionalMotionResult:
    """Classify only measured stationary versus unmistakably active motion.

    The dead band between the stationary and active gates fails closed as
    ``UNCLASSIFIED``. Active motion remains generic and has no scoring meaning.
    """

    gates = thresholds or ProvisionalGenericMotionThresholds()
    structural_failures = []
    if features.duration_s < gates.min_duration_s:
        structural_failures.append("duration")
    if features.valid_fraction < gates.min_valid_fraction:
        structural_failures.append("sensor_validity")
    if features.sequence_gaps > gates.max_sequence_gaps:
        structural_failures.append("sequence_gaps")
    if structural_failures:
        return ProvisionalMotionResult(
            state="UNCLASSIFIED",
            passed=False,
            reasons=tuple(structural_failures),
        )

    if (
        features.accel_norm_stdev_mps2
        <= gates.max_stationary_accel_norm_stdev_mps2
        and features.gyro_norm_rms_rads <= gates.max_stationary_gyro_norm_rms_rads
    ):
        return ProvisionalMotionResult(
            state="STATIONARY_CANDIDATE",
            passed=True,
            reasons=(),
        )

    if (
        features.accel_norm_stdev_mps2
        >= gates.min_active_accel_norm_stdev_mps2
        or features.gyro_norm_rms_rads >= gates.min_active_gyro_norm_rms_rads
    ):
        return ProvisionalMotionResult(
            state="ACTIVE_MOTION_CANDIDATE",
            passed=True,
            reasons=(),
        )

    return ProvisionalMotionResult(
        state="UNCLASSIFIED",
        passed=False,
        reasons=("motion_dead_band",),
    )
