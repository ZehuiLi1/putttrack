from __future__ import annotations

import math
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from putttrack.motion.pickup_v0 import MotionSample  # noqa: E402
from putttrack.motion.recognizer_v1 import (  # noqa: E402
    DurationSpec,
    EmissionFrame,
    FeatureFrame,
    HSMMConfig,
    LinearModelSpec,
    PersistentState,
    SelectiveLinearSoftmax,
    TransientEvent,
    decode_hsmm,
    derive_transition_events,
    extract_causal_multiscale_frame,
)


class RecognizerV1Tests(unittest.TestCase):
    def test_hsmm_respects_explicit_duration_and_transition(self) -> None:
        states = ("STATIONARY", "ROLLING", "UNKNOWN")
        config = HSMMConfig(
            states=states,
            start_log_probabilities={
                "STATIONARY": 0.0,
                "ROLLING": -5.0,
                "UNKNOWN": -5.0,
            },
            transition_log_probabilities={
                "STATIONARY": {
                    "STATIONARY": -0.1,
                    "ROLLING": 0.0,
                    "UNKNOWN": -2.0,
                },
                "ROLLING": {
                    "ROLLING": -0.1,
                    "STATIONARY": 0.0,
                    "UNKNOWN": -2.0,
                },
                "UNKNOWN": {
                    "UNKNOWN": -0.1,
                    "STATIONARY": 0.0,
                    "ROLLING": 0.0,
                },
            },
            durations={
                "STATIONARY": DurationSpec(2, 10, 3),
                "ROLLING": DurationSpec(2, 10, 3),
                "UNKNOWN": DurationSpec(1, 10, 1),
            },
        )
        emissions = []
        for index in range(6):
            probabilities = (
                {"STATIONARY": 0.97, "ROLLING": 0.02, "UNKNOWN": 0.01}
                if index < 3
                else {"STATIONARY": 0.02, "ROLLING": 0.97, "UNKNOWN": 0.01}
            )
            emissions.append(
                EmissionFrame(
                    source_monotonic_us=index * 20_000,
                    log_probabilities={
                        key: math.log(value) for key, value in probabilities.items()
                    },
                    raw_probabilities=probabilities,
                    abstained=False,
                    abstain_reasons=(),
                )
            )
        result = decode_hsmm(emissions, config)
        self.assertEqual(
            result.states, ("STATIONARY",) * 3 + ("ROLLING",) * 3
        )
        self.assertEqual(
            result.segments,
            (("STATIONARY", 0, 3), ("ROLLING", 3, 6)),
        )

    def test_hsmm_runner_up_includes_same_terminal_state_paths(self) -> None:
        states = ("A", "B", "UNKNOWN")
        config = HSMMConfig(
            states=states,
            start_log_probabilities={"A": 0.0, "B": -0.01, "UNKNOWN": -20.0},
            transition_log_probabilities={
                "A": {"B": -100.0, "UNKNOWN": -100.0},
                "B": {"A": 0.0, "UNKNOWN": -100.0},
                "UNKNOWN": {"A": -100.0, "B": -100.0},
            },
            durations={state: DurationSpec(1, 2, 2, 0.0) for state in states},
        )
        emissions = tuple(
            EmissionFrame(
                source_monotonic_us=index * 20_000,
                log_probabilities={
                    "A": math.log(0.9),
                    "B": math.log(0.1),
                    "UNKNOWN": math.log(1e-9),
                },
                raw_probabilities={"A": 0.9, "B": 0.1, "UNKNOWN": 1e-9},
                abstained=False,
                abstain_reasons=(),
            )
            for index in range(2)
        )
        result = decode_hsmm(emissions, config)
        expected_runner_up = -0.01 + math.log(0.1) + math.log(0.9)
        self.assertEqual(result.states, ("A", "A"))
        self.assertAlmostEqual(result.runner_up_score, expected_runner_up)
        self.assertLess(result.sequence_margin, 3.0)

    def test_selective_model_abstains_on_low_margin(self) -> None:
        labels = tuple(state.value for state in PersistentState)
        feature_order = ("x",)
        coefficients = {label: (0.0,) for label in labels}
        model = SelectiveLinearSoftmax(
            LinearModelSpec(
                labels=labels,
                feature_order=feature_order,
                means=(0.0,),
                scales=(1.0,),
                coefficients=coefficients,
                intercepts={label: 0.0 for label in labels},
            ),
            minimum_probability=0.8,
            minimum_margin=0.2,
        )
        output = model.predict(
            FeatureFrame(
                source_monotonic_us=0, values={"x": 0.0}, quality_ok=True
            )
        )
        self.assertTrue(output.abstained)
        self.assertEqual(
            output.log_probabilities[PersistentState.UNKNOWN.value], 0.0
        )
        self.assertAlmostEqual(
            sum(output.raw_probabilities[label] for label in labels), 1.0
        )

    def test_multiscale_features_are_causal_and_saturation_aware(self) -> None:
        samples = []
        for index in range(120):
            gyro = (35.0, 0.0, 0.0) if index > 100 else (0.0, 2.0, 0.0)
            samples.append(
                MotionSample(
                    sequence=index,
                    source_monotonic_us=index * 20_000,
                    accel_mps2=(0.0, 0.0, 9.80665),
                    gyro_rads=gyro,
                    adxl367_valid=True,
                    bmi270_valid=True,
                    sensor_error_bits=0,
                )
            )
        frame = extract_causal_multiscale_frame(
            samples,
            end_source_monotonic_us=samples[-1].source_monotonic_us,
        )
        self.assertTrue(frame.quality_ok)
        self.assertGreater(frame.values["gyro_clip_fraction_200ms"], 0.0)
        self.assertGreater(
            frame.values["gyro_dominant_axis_ratio_1000ms"], 0.9
        )

    def test_multiscale_features_ignore_future_discontinuity(self) -> None:
        samples = [
            MotionSample(
                sequence=index,
                source_monotonic_us=index * 20_000,
                accel_mps2=(0.0, 0.0, 9.80665),
                gyro_rads=(1.0, -1.0, 0.0),
                adxl367_valid=True,
                bmi270_valid=True,
                sensor_error_bits=0,
            )
            for index in range(121)
        ]
        end_us = samples[-1].source_monotonic_us
        samples.append(
            MotionSample(
                sequence=999,
                source_monotonic_us=end_us + 20_000,
                accel_mps2=(0.0, 0.0, 9.80665),
                gyro_rads=(0.0, 0.0, 0.0),
                adxl367_valid=False,
                bmi270_valid=False,
                sensor_error_bits=1,
            )
        )
        frame = extract_causal_multiscale_frame(
            samples,
            end_source_monotonic_us=end_us,
        )
        self.assertTrue(frame.quality_ok)
        self.assertGreater(
            frame.values["gyro_dominant_axis_ratio_1000ms"], 0.999999
        )

    def test_event_head_is_conditioned_on_state_transition(self) -> None:
        states = (
            "STATIONARY",
            "STATIONARY",
            "ROLLING",
            "ROLLING",
            "CARRIED",
        )
        frames = tuple(
            FeatureFrame(index * 20_000, {}, True)
            for index in range(len(states))
        )
        probabilities = []
        for _ in states:
            probabilities.append(
                {
                    TransientEvent.MOTION_ONSET.value: 0.95,
                    TransientEvent.IMPACT_CANDIDATE.value: 0.95,
                    TransientEvent.PICKUP_TRANSITION.value: 0.95,
                    TransientEvent.ROLLING_PICKUP.value: 0.95,
                    TransientEvent.COLLISION_OR_STEP_CANDIDATE.value: 0.1,
                    TransientEvent.DROP_LANDING_CANDIDATE.value: 0.1,
                }
            )
        events = derive_transition_events(
            states, frames, probabilities, threshold=0.9
        )
        labels = [event.event for event in events]
        self.assertIn(TransientEvent.IMPACT_CANDIDATE.value, labels)
        self.assertIn(TransientEvent.PICKUP_TRANSITION.value, labels)
        self.assertIn(TransientEvent.ROLLING_PICKUP.value, labels)


if __name__ == "__main__":
    unittest.main()
