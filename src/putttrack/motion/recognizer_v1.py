"""Physics-guided dual-head semi-Markov motion recognition primitives.

The module implements the architecture selected for PuttTrack Research Ball IMU
state recognition:

* a persistent-state head decoded with an explicit-duration HSMM;
* a separate transient-event head;
* first-class UNKNOWN/abstention and sensor-quality handling;
* dependency-free causal multiscale feature extraction.

It intentionally does not ship trained commercial coefficients. Those must be
fitted with group-held-out labels (day/operator/Ball/surface) and then frozen in
a versioned model file. Untrained/low-confidence paths abstain.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import math
import statistics
from typing import Any, Mapping, Sequence

from .pickup_v0 import MotionSample


NEG_INF = float("-inf")


class PersistentState(str, Enum):
    STATIONARY = "STATIONARY"
    ROLLING = "ROLLING"
    SETTLING = "SETTLING"
    CARRIED = "CARRIED"
    AIRBORNE = "AIRBORNE"
    UNKNOWN = "UNKNOWN"


class TransientEvent(str, Enum):
    MOTION_ONSET = "MOTION_ONSET"
    IMPACT_CANDIDATE = "IMPACT_CANDIDATE"
    PICKUP_TRANSITION = "PICKUP_TRANSITION"
    ROLLING_PICKUP = "ROLLING_PICKUP"
    COLLISION_OR_STEP_CANDIDATE = "COLLISION_OR_STEP_CANDIDATE"
    DROP_LANDING_CANDIDATE = "DROP_LANDING_CANDIDATE"


@dataclass(frozen=True)
class FeatureFrame:
    source_monotonic_us: int
    values: Mapping[str, float]
    quality_ok: bool
    quality_reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class EmissionFrame:
    source_monotonic_us: int
    log_probabilities: Mapping[str, float]
    raw_probabilities: Mapping[str, float]
    abstained: bool
    abstain_reasons: tuple[str, ...]


@dataclass(frozen=True)
class DurationSpec:
    minimum_frames: int
    maximum_frames: int
    preferred_frames: int
    log_duration_penalty: float = 0.25

    def score(self, duration: int) -> float:
        if duration < self.minimum_frames or duration > self.maximum_frames:
            return NEG_INF
        preferred = max(1, self.preferred_frames)
        ratio = max(duration, 1) / preferred
        return -self.log_duration_penalty * abs(math.log(ratio))


@dataclass(frozen=True)
class HSMMConfig:
    states: tuple[str, ...]
    start_log_probabilities: Mapping[str, float]
    transition_log_probabilities: Mapping[str, Mapping[str, float]]
    durations: Mapping[str, DurationSpec]


@dataclass(frozen=True)
class HSMMResult:
    states: tuple[str, ...]
    score: float
    runner_up_score: float
    sequence_margin: float
    segments: tuple[tuple[str, int, int], ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EventCandidate:
    event: str
    source_monotonic_us: int
    probability: float
    supporting_transition: str | None
    quality_reasons: tuple[str, ...] = ()
    authority: bool = False


@dataclass(frozen=True)
class RecognitionResult:
    state_path: tuple[str, ...]
    hsmm_score: float
    hsmm_margin: float
    state_frames: tuple[EmissionFrame, ...]
    events: tuple[EventCandidate, ...]
    authority: bool = False


@dataclass(frozen=True)
class LinearModelSpec:
    """Standardized linear softmax model exported by group-held-out training."""

    labels: tuple[str, ...]
    feature_order: tuple[str, ...]
    means: tuple[float, ...]
    scales: tuple[float, ...]
    coefficients: Mapping[str, tuple[float, ...]]
    intercepts: Mapping[str, float]

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "LinearModelSpec":
        labels = tuple(str(item) for item in payload["labels"])
        feature_order = tuple(str(item) for item in payload["feature_order"])
        means = tuple(float(item) for item in payload["means"])
        scales = tuple(float(item) for item in payload["scales"])
        if not (len(feature_order) == len(means) == len(scales)):
            raise ValueError("feature_order, means and scales must have equal length")
        coefficients: dict[str, tuple[float, ...]] = {}
        intercepts: dict[str, float] = {}
        raw_coefficients = payload["coefficients"]
        raw_intercepts = payload["intercepts"]
        for label in labels:
            row = tuple(float(item) for item in raw_coefficients[label])
            if len(row) != len(feature_order):
                raise ValueError(f"coefficient length mismatch for {label}")
            coefficients[label] = row
            intercepts[label] = float(raw_intercepts[label])
        return cls(
            labels=labels,
            feature_order=feature_order,
            means=means,
            scales=scales,
            coefficients=coefficients,
            intercepts=intercepts,
        )


class SelectiveLinearSoftmax:
    """Calibrated state emissions with confidence/margin abstention."""

    def __init__(
        self,
        spec: LinearModelSpec,
        *,
        unknown_label: str = PersistentState.UNKNOWN.value,
        minimum_probability: float = 0.98,
        minimum_margin: float = 0.25,
    ) -> None:
        self.spec = spec
        self.unknown_label = unknown_label
        self.output_labels = (
            spec.labels if unknown_label in spec.labels else spec.labels + (unknown_label,)
        )
        self.minimum_probability = minimum_probability
        self.minimum_margin = minimum_margin

    def predict(self, frame: FeatureFrame) -> EmissionFrame:
        if not frame.quality_ok:
            probabilities = {
                label: 1.0 if label == self.unknown_label else 0.0
                for label in self.output_labels
            }
            return EmissionFrame(
                source_monotonic_us=frame.source_monotonic_us,
                log_probabilities={
                    label: 0.0 if label == self.unknown_label else NEG_INF
                    for label in self.output_labels
                },
                raw_probabilities=probabilities,
                abstained=True,
                abstain_reasons=frame.quality_reasons or ("quality_gate",),
            )

        missing = [name for name in self.spec.feature_order if name not in frame.values]
        non_finite = [
            name
            for name in self.spec.feature_order
            if name in frame.values and not math.isfinite(float(frame.values[name]))
        ]
        if missing or non_finite:
            reasons = tuple(
                [f"missing_feature:{name}" for name in missing]
                + [f"non_finite_feature:{name}" for name in non_finite]
            )
            probabilities = {
                label: 1.0 if label == self.unknown_label else 0.0
                for label in self.output_labels
            }
            return EmissionFrame(
                source_monotonic_us=frame.source_monotonic_us,
                log_probabilities={
                    label: 0.0 if label == self.unknown_label else NEG_INF
                    for label in self.output_labels
                },
                raw_probabilities=probabilities,
                abstained=True,
                abstain_reasons=reasons,
            )

        standardized = []
        for name, mean, scale in zip(
            self.spec.feature_order,
            self.spec.means,
            self.spec.scales,
        ):
            safe_scale = scale if abs(scale) > 1e-12 else 1.0
            standardized.append((float(frame.values[name]) - mean) / safe_scale)

        logits: dict[str, float] = {}
        for label in self.spec.labels:
            logits[label] = self.spec.intercepts[label] + sum(
                weight * value
                for weight, value in zip(self.spec.coefficients[label], standardized)
            )
        maximum = max(logits.values())
        exponentials = {
            label: math.exp(value - maximum) for label, value in logits.items()
        }
        denominator = sum(exponentials.values())
        probabilities = {
            label: value / denominator for label, value in exponentials.items()
        }
        ranked = sorted(probabilities.items(), key=lambda item: item[1], reverse=True)
        best_label, best_probability = ranked[0]
        second_probability = ranked[1][1] if len(ranked) > 1 else 0.0
        margin = best_probability - second_probability

        reasons: list[str] = []
        if best_probability < self.minimum_probability:
            reasons.append("low_posterior")
        if margin < self.minimum_margin:
            reasons.append("low_top_two_margin")
        if reasons and best_label != self.unknown_label:
            # Decoder-visible probabilities fail closed to UNKNOWN while raw
            # fitted probabilities remain available for audit/calibration.
            log_probabilities = {
                label: 0.0 if label == self.unknown_label else NEG_INF
                for label in self.output_labels
            }
            raw_probabilities = dict(probabilities)
            if self.unknown_label not in raw_probabilities:
                raw_probabilities[self.unknown_label] = 0.0
            return EmissionFrame(
                source_monotonic_us=frame.source_monotonic_us,
                log_probabilities=log_probabilities,
                raw_probabilities=raw_probabilities,
                abstained=True,
                abstain_reasons=tuple(reasons),
            )

        epsilon = 1e-300
        output_probabilities = dict(probabilities)
        if self.unknown_label not in output_probabilities:
            output_probabilities[self.unknown_label] = 0.0
        log_probabilities = {
            label: (
                math.log(max(output_probabilities[label], epsilon))
                if label in probabilities
                else math.log(1e-12)
            )
            for label in self.output_labels
        }
        return EmissionFrame(
            source_monotonic_us=frame.source_monotonic_us,
            log_probabilities=log_probabilities,
            raw_probabilities=output_probabilities,
            abstained=best_label == self.unknown_label,
            abstain_reasons=("model_selected_unknown",)
            if best_label == self.unknown_label
            else (),
        )


def decode_hsmm(emissions: Sequence[EmissionFrame], config: HSMMConfig) -> HSMMResult:
    """Exact offline explicit-duration Viterbi decoding with a true runner-up."""

    frame_count = len(emissions)
    if frame_count == 0:
        return HSMMResult((), NEG_INF, NEG_INF, 0.0, ())
    states = config.states
    state_set = set(states)
    for frame in emissions:
        if not state_set.issubset(frame.log_probabilities):
            missing = sorted(state_set - set(frame.log_probabilities))
            raise ValueError(f"emission frame missing states: {missing}")

    def segment_emission(state: str, start: int, end: int) -> float:
        values = [
            emissions[index].log_probabilities[state] for index in range(start, end)
        ]
        if any(value == NEG_INF for value in values):
            return NEG_INF
        return sum(values)

    # Each cell retains the two best complete paths ending in that state.  A
    # terminal-state-only runner-up can miss the real second-best sequence when
    # both best paths end in the same state, which overstates confidence.
    # Entry: (score, start, previous_state, previous_rank, duration).
    entries: list[
        dict[str, list[tuple[float, int, str | None, int | None, int]]]
    ] = [{state: [] for state in states} for _ in range(frame_count + 1)]

    for end in range(1, frame_count + 1):
        for state in states:
            duration_spec = config.durations[state]
            maximum_duration = min(duration_spec.maximum_frames, end)
            candidates: list[tuple[float, int, str | None, int | None, int]] = []
            for duration in range(
                duration_spec.minimum_frames, maximum_duration + 1
            ):
                start = end - duration
                emission_score = segment_emission(state, start, end)
                if emission_score == NEG_INF:
                    continue
                duration_score = duration_spec.score(duration)
                if start == 0:
                    start_score = config.start_log_probabilities.get(state, NEG_INF)
                    if start_score != NEG_INF:
                        candidates.append(
                            (
                                start_score + duration_score + emission_score,
                                start,
                                None,
                                None,
                                duration,
                            )
                        )
                else:
                    for candidate_previous in states:
                        # Explicit duration represents the whole dwell. Adjacent
                        # same-state segments duplicate one state path.
                        if candidate_previous == state:
                            continue
                        transition = config.transition_log_probabilities.get(
                            candidate_previous, {}
                        ).get(state, NEG_INF)
                        if transition == NEG_INF:
                            continue
                        for previous_rank, previous_entry in enumerate(
                            entries[start][candidate_previous]
                        ):
                            candidates.append(
                                (
                                    previous_entry[0]
                                    + transition
                                    + duration_score
                                    + emission_score,
                                    start,
                                    candidate_previous,
                                    previous_rank,
                                    duration,
                                )
                            )
            candidates.sort(key=lambda item: item[0], reverse=True)
            entries[end][state] = candidates[:2]

    final_paths = sorted(
        (
            (entry[0], state, rank)
            for state in states
            for rank, entry in enumerate(entries[frame_count][state])
        ),
        key=lambda item: item[0],
        reverse=True,
    )
    if not final_paths:
        best_score = NEG_INF
        best_state = PersistentState.UNKNOWN.value
        best_rank = 0
    else:
        best_score, best_state, best_rank = final_paths[0]
    runner_up = final_paths[1][0] if len(final_paths) > 1 else NEG_INF
    if best_score == NEG_INF:
        unknown = PersistentState.UNKNOWN.value
        return HSMMResult(
            states=tuple(unknown for _ in emissions),
            score=NEG_INF,
            runner_up_score=NEG_INF,
            sequence_margin=0.0,
            segments=((unknown, 0, frame_count),),
        )

    segments_reversed: list[tuple[str, int, int]] = []
    end = frame_count
    state: str | None = best_state
    rank: int | None = best_rank
    while end > 0 and state is not None:
        if rank is None or rank >= len(entries[end][state]):
            unknown = PersistentState.UNKNOWN.value
            return HSMMResult(
                states=tuple(unknown for _ in emissions),
                score=NEG_INF,
                runner_up_score=runner_up,
                sequence_margin=0.0,
                segments=((unknown, 0, frame_count),),
            )
        _, start, previous_state, previous_rank, _ = entries[end][state][rank]
        segments_reversed.append((state, start, end))
        end = start
        state = previous_state
        rank = previous_rank

    segments = tuple(reversed(segments_reversed))
    path = [PersistentState.UNKNOWN.value] * frame_count
    for label, start, end in segments:
        for index in range(start, end):
            path[index] = label
    margin = best_score - runner_up if runner_up != NEG_INF else math.inf
    return HSMMResult(
        states=tuple(path),
        score=best_score,
        runner_up_score=runner_up,
        sequence_margin=margin,
        segments=segments,
    )


def _norm(vector: Sequence[float]) -> float:
    return math.sqrt(sum(value * value for value in vector))


def _mean_vector(
    vectors: Sequence[Sequence[float]],
) -> tuple[float, float, float]:
    return tuple(
        statistics.fmean(vector[index] for vector in vectors) for index in range(3)
    )  # type: ignore[return-value]


def _percentile(values: Sequence[float], probability: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = min(max(probability, 0.0), 1.0) * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def _angle_between(a: Sequence[float], b: Sequence[float]) -> float:
    a_norm = _norm(a)
    b_norm = _norm(b)
    if a_norm <= 1e-12 or b_norm <= 1e-12:
        return math.pi
    cosine = sum(x * y for x, y in zip(a, b)) / (a_norm * b_norm)
    return math.acos(min(1.0, max(-1.0, cosine)))


def _vector_autocorrelation_peak(
    vectors: Sequence[Sequence[float]],
    timestamps_us: Sequence[int],
) -> tuple[float, float]:
    """Return normalized 3-axis autocorrelation peak and candidate period."""

    if len(vectors) < 6 or len(vectors) != len(timestamps_us):
        return 0.0, 0.0
    mean = _mean_vector(vectors)
    centered = [
        tuple(vector[index] - mean[index] for index in range(3))
        for vector in vectors
    ]
    best_score = -1.0
    best_lag = 0
    maximum_lag = max(2, len(centered) // 2)
    for lag in range(2, maximum_lag + 1):
        left = centered[:-lag]
        right = centered[lag:]
        numerator = sum(
            sum(a * b for a, b in zip(x, y)) for x, y in zip(left, right)
        )
        left_energy = sum(
            sum(value * value for value in vector) for vector in left
        )
        right_energy = sum(
            sum(value * value for value in vector) for vector in right
        )
        denominator = math.sqrt(left_energy * right_energy)
        if denominator <= 1e-12:
            continue
        score = numerator / denominator
        if score > best_score:
            best_score = score
            best_lag = lag
    if best_lag == 0:
        return 0.0, 0.0
    deltas = [
        (current - previous) / 1_000_000.0
        for previous, current in zip(timestamps_us, timestamps_us[1:])
        if current > previous
    ]
    sample_period = statistics.median(deltas) if deltas else 0.0
    return max(-1.0, min(1.0, best_score)), best_lag * sample_period


def _dominant_axis_ratio(vectors: Sequence[Sequence[float]]) -> float:
    """Largest eigenvalue / trace of gyro second-moment matrix."""

    if not vectors:
        return 0.0
    matrix = [[0.0] * 3 for _ in range(3)]
    for vector in vectors:
        for row in range(3):
            for column in range(3):
                matrix[row][column] += vector[row] * vector[column]
    scale = float(len(vectors))
    matrix = [[value / scale for value in row] for row in matrix]
    trace = sum(matrix[index][index] for index in range(3))
    if trace <= 1e-12:
        return 0.0

    # Closed-form eigenvalue for a real symmetric 3x3 matrix.  A single-seed
    # power iteration can be exactly orthogonal to the dominant physical axis
    # (for example axis (1, -1, 0)) and incorrectly return zero.
    mean_diagonal = trace / 3.0
    centered_diagonal = [
        matrix[index][index] - mean_diagonal for index in range(3)
    ]
    squared_scale = (
        sum(value * value for value in centered_diagonal)
        + 2.0
        * (
            matrix[0][1] ** 2
            + matrix[0][2] ** 2
            + matrix[1][2] ** 2
        )
    ) / 6.0
    if squared_scale <= 1e-24:
        largest = mean_diagonal
    else:
        scale = math.sqrt(squared_scale)
        normalized = [
            [
                (matrix[row][column] - (mean_diagonal if row == column else 0.0))
                / scale
                for column in range(3)
            ]
            for row in range(3)
        ]
        determinant = (
            normalized[0][0]
            * (
                normalized[1][1] * normalized[2][2]
                - normalized[1][2] * normalized[2][1]
            )
            - normalized[0][1]
            * (
                normalized[1][0] * normalized[2][2]
                - normalized[1][2] * normalized[2][0]
            )
            + normalized[0][2]
            * (
                normalized[1][0] * normalized[2][1]
                - normalized[1][1] * normalized[2][0]
            )
        )
        angle = math.acos(min(1.0, max(-1.0, determinant / 2.0))) / 3.0
        largest = mean_diagonal + 2.0 * scale * math.cos(angle)
    return min(max(largest / trace, 0.0), 1.0)


def extract_causal_multiscale_frame(
    samples: Sequence[MotionSample],
    *,
    end_source_monotonic_us: int,
    windows_s: Sequence[float] = (0.08, 0.20, 0.60, 1.00, 2.00),
    gravity_mps2: float = 9.80665,
    gyro_clip_rads: float = 34.208453,
) -> FeatureFrame:
    """Extract causal, orientation-independent shape features at one timestamp."""

    values: dict[str, float] = {}
    reasons: list[str] = []
    maximum_window_s = max((float(value) for value in windows_s), default=0.0)
    earliest_us = end_source_monotonic_us - int(maximum_window_s * 1_000_000)
    causal_samples = [
        sample
        for sample in samples
        if earliest_us <= sample.source_monotonic_us <= end_source_monotonic_us
    ]
    if len(causal_samples) < 2:
        return FeatureFrame(
            source_monotonic_us=end_source_monotonic_us,
            values={},
            quality_ok=False,
            quality_reasons=("insufficient_samples",),
        )
    for previous, current in zip(causal_samples, causal_samples[1:]):
        if current.sequence != previous.sequence + 1:
            reasons.append("sequence_gap_or_reordering")
            break
        if current.source_monotonic_us <= previous.source_monotonic_us:
            reasons.append("time_regression")
            break

    for window_s in windows_s:
        start_us = end_source_monotonic_us - int(window_s * 1_000_000)
        window = [
            sample
            for sample in causal_samples
            if start_us <= sample.source_monotonic_us <= end_source_monotonic_us
        ]
        suffix = f"_{int(round(window_s * 1000))}ms"
        if len(window) < 2:
            reasons.append(f"insufficient_window{suffix}")
            continue
        if any(
            not sample.adxl367_valid
            or not sample.bmi270_valid
            or sample.sensor_error_bits != 0
            for sample in window
        ):
            reasons.append(f"invalid_sensor{suffix}")

        accel_norms = [_norm(sample.accel_mps2) for sample in window]
        gyro_vectors = [sample.gyro_rads for sample in window]
        gyro_norms = [_norm(vector) for vector in gyro_vectors]
        jerks: list[float] = []
        for previous, current, previous_norm, current_norm in zip(
            window,
            window[1:],
            accel_norms,
            accel_norms[1:],
        ):
            dt = (
                current.source_monotonic_us - previous.source_monotonic_us
            ) / 1_000_000.0
            if dt > 0:
                jerks.append(abs(current_norm - previous_norm) / dt)

        mean_gyro_vector = _mean_vector(gyro_vectors)
        mean_gyro_norm = statistics.fmean(gyro_norms)
        half = max(1, len(gyro_norms) // 2)
        first_half = statistics.fmean(gyro_norms[:half])
        second_half = statistics.fmean(gyro_norms[-half:])
        first_axis = _mean_vector(gyro_vectors[:half])
        second_axis = _mean_vector(gyro_vectors[-half:])
        axis_drift = _angle_between(first_axis, second_axis)
        periodicity, candidate_period_s = _vector_autocorrelation_peak(
            [sample.accel_mps2 for sample in window],
            [sample.source_monotonic_us for sample in window],
        )
        dominant_axis_ratio = _dominant_axis_ratio(gyro_vectors)
        rolling_coherence = (
            dominant_axis_ratio
            * max(0.0, periodicity)
            * max(0.0, 1.0 - axis_drift / math.pi)
        )
        values.update(
            {
                f"accel_norm_mean{suffix}": statistics.fmean(accel_norms),
                f"accel_norm_stdev{suffix}": statistics.pstdev(accel_norms),
                f"accel_residual_rms{suffix}": math.sqrt(
                    statistics.fmean(
                        (value - gravity_mps2) ** 2 for value in accel_norms
                    )
                ),
                f"accel_norm_min{suffix}": min(accel_norms),
                f"accel_norm_max{suffix}": max(accel_norms),
                f"gyro_norm_mean{suffix}": mean_gyro_norm,
                f"gyro_norm_rms{suffix}": math.sqrt(
                    statistics.fmean(value * value for value in gyro_norms)
                ),
                f"gyro_norm_p95{suffix}": _percentile(gyro_norms, 0.95),
                f"gyro_norm_max{suffix}": max(gyro_norms),
                f"gyro_axis_consistency{suffix}": (
                    _norm(mean_gyro_vector) / mean_gyro_norm
                    if mean_gyro_norm > 1e-12
                    else 0.0
                ),
                f"gyro_dominant_axis_ratio{suffix}": dominant_axis_ratio,
                f"gyro_axis_drift_rad{suffix}": axis_drift,
                f"gyro_decay_ratio{suffix}": second_half / max(first_half, 1e-9),
                f"accel_rotation_periodicity{suffix}": periodicity,
                f"accel_rotation_candidate_period_s{suffix}": candidate_period_s,
                f"rolling_coherence{suffix}": rolling_coherence,
                f"jerk_rms{suffix}": (
                    math.sqrt(statistics.fmean(value * value for value in jerks))
                    if jerks
                    else 0.0
                ),
                f"jerk_p95{suffix}": _percentile(jerks, 0.95),
                f"jerk_peak{suffix}": max(jerks) if jerks else 0.0,
                f"freefall_fraction{suffix}": sum(value < 2.0 for value in accel_norms)
                / len(accel_norms),
                f"active_fraction{suffix}": sum(
                    abs(accel - gravity_mps2) >= 0.5 or gyro >= 0.25
                    for accel, gyro in zip(accel_norms, gyro_norms)
                )
                / len(window),
                f"gyro_clip_fraction{suffix}": sum(
                    max(abs(value) for value in vector) >= gyro_clip_rads
                    for vector in gyro_vectors
                )
                / len(gyro_vectors),
            }
        )

    return FeatureFrame(
        source_monotonic_us=end_source_monotonic_us,
        values=values,
        quality_ok=not reasons,
        quality_reasons=tuple(sorted(set(reasons))),
    )


def build_hsmm_config(
    payload: Mapping[str, Any],
    *,
    frames_per_second: float,
) -> HSMMConfig:
    states = tuple(str(item) for item in payload["states"])
    start = {
        state: float(payload["start_log_probabilities"].get(state, NEG_INF))
        for state in states
    }
    transitions = {
        source: {
            target: float(
                payload["transition_log_probabilities"]
                .get(source, {})
                .get(target, NEG_INF)
            )
            for target in states
        }
        for source in states
    }
    durations: dict[str, DurationSpec] = {}
    for state in states:
        raw = payload["durations_seconds"][state]
        durations[state] = DurationSpec(
            minimum_frames=max(
                1, round(float(raw["minimum"]) * frames_per_second)
            ),
            maximum_frames=max(
                1, round(float(raw["maximum"]) * frames_per_second)
            ),
            preferred_frames=max(
                1, round(float(raw["preferred"]) * frames_per_second)
            ),
            log_duration_penalty=float(raw.get("log_penalty", 0.25)),
        )
    return HSMMConfig(
        states=states,
        start_log_probabilities=start,
        transition_log_probabilities=transitions,
        durations=durations,
    )


def derive_transition_events(
    state_path: Sequence[str],
    frames: Sequence[FeatureFrame],
    event_probabilities: Sequence[Mapping[str, float]],
    *,
    threshold: float = 0.90,
) -> tuple[EventCandidate, ...]:
    """Apply physical transition context to independent event-head outputs."""

    if not (len(state_path) == len(frames) == len(event_probabilities)):
        raise ValueError(
            "state path, feature frames and event probabilities must align"
        )
    events: list[EventCandidate] = []
    for index, (state, frame, probabilities) in enumerate(
        zip(state_path, frames, event_probabilities)
    ):
        previous = state_path[index - 1] if index else state
        transition = f"{previous}->{state}" if previous != state else None
        candidates: list[str] = []
        if (
            previous == PersistentState.STATIONARY.value
            and state == PersistentState.ROLLING.value
        ):
            candidates.extend(
                [
                    TransientEvent.MOTION_ONSET.value,
                    TransientEvent.IMPACT_CANDIDATE.value,
                ]
            )
        if (
            state == PersistentState.CARRIED.value
            and previous != PersistentState.CARRIED.value
        ):
            candidates.append(TransientEvent.PICKUP_TRANSITION.value)
            if previous in (
                PersistentState.ROLLING.value,
                PersistentState.SETTLING.value,
            ):
                candidates.append(TransientEvent.ROLLING_PICKUP.value)
        if previous == PersistentState.ROLLING.value and state in (
            PersistentState.ROLLING.value,
            PersistentState.SETTLING.value,
        ):
            candidates.append(TransientEvent.COLLISION_OR_STEP_CANDIDATE.value)
        if (
            previous == PersistentState.AIRBORNE.value
            and state != PersistentState.AIRBORNE.value
        ):
            candidates.append(TransientEvent.DROP_LANDING_CANDIDATE.value)

        for event in candidates:
            probability = float(probabilities.get(event, 0.0))
            if probability >= threshold and frame.quality_ok:
                events.append(
                    EventCandidate(
                        event=event,
                        source_monotonic_us=frame.source_monotonic_us,
                        probability=probability,
                        supporting_transition=transition,
                    )
                )
    return tuple(events)


def recognize_sequence(
    feature_frames: Sequence[FeatureFrame],
    state_model: SelectiveLinearSoftmax,
    hsmm_config: HSMMConfig,
    event_probabilities: Sequence[Mapping[str, float]],
    *,
    event_threshold: float = 0.90,
) -> RecognitionResult:
    emissions = tuple(state_model.predict(frame) for frame in feature_frames)
    decoded = decode_hsmm(emissions, hsmm_config)
    events = derive_transition_events(
        decoded.states,
        feature_frames,
        event_probabilities,
        threshold=event_threshold,
    )
    return RecognitionResult(
        state_path=decoded.states,
        hsmm_score=decoded.score,
        hsmm_margin=decoded.sequence_margin,
        state_frames=emissions,
        events=events,
    )


__all__ = [
    "DurationSpec",
    "EmissionFrame",
    "EventCandidate",
    "FeatureFrame",
    "HSMMConfig",
    "HSMMResult",
    "LinearModelSpec",
    "PersistentState",
    "RecognitionResult",
    "SelectiveLinearSoftmax",
    "TransientEvent",
    "build_hsmm_config",
    "decode_hsmm",
    "derive_transition_events",
    "extract_causal_multiscale_frame",
    "recognize_sequence",
]
