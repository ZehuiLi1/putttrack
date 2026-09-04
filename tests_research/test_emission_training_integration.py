from __future__ import annotations

import json
import unittest

import numpy as np

from putttrack.motion.recognizer_v1 import (
    DurationSpec,
    FeatureFrame,
    HSMMConfig,
    LinearModelSpec,
    SelectiveLinearSoftmax,
    recognize_sequence,
)
from tools.train_grouped_logistic_emissions import (
    build_pipeline,
    export_linear_spec,
)


class EmissionTrainingIntegrationTests(unittest.TestCase):
    def test_sklearn_export_round_trips_into_hsmm_recognizer(self) -> None:
        features = ("gyro", "accel")
        x = np.asarray(
            [
                [0.05, 0.02],
                [0.10, 0.04],
                [0.15, 0.03],
                [0.20, 0.05],
                [2.00, 1.80],
                [2.10, 1.90],
                [2.20, 2.00],
                [2.30, 2.10],
            ],
            dtype=float,
        )
        y = np.asarray(
            ["STATIONARY"] * 4 + ["ROLLING"] * 4,
            dtype=object,
        )
        pipeline = build_pipeline(1.0)
        pipeline.fit(x, y)

        exported = export_linear_spec(pipeline, features)
        # Exercise the real artifact boundary, not a shared in-memory mapping.
        restored = json.loads(json.dumps(exported, sort_keys=True))
        model = SelectiveLinearSoftmax(
            LinearModelSpec.from_mapping(restored),
            minimum_probability=0.0,
            minimum_margin=0.0,
        )

        sklearn_probabilities = pipeline.predict_proba(x)
        sklearn_labels = tuple(str(value) for value in pipeline.classes_)
        frames = tuple(
            FeatureFrame(
                source_monotonic_us=index * 50_000,
                values=dict(zip(features, row)),
                quality_ok=True,
            )
            for index, row in enumerate(x)
        )
        emissions = tuple(model.predict(frame) for frame in frames)
        for expected, actual in zip(sklearn_probabilities, emissions):
            for label, probability in zip(sklearn_labels, expected):
                self.assertAlmostEqual(
                    actual.raw_probabilities[label], float(probability), places=12
                )

        states = ("STATIONARY", "ROLLING", "UNKNOWN")
        hsmm = HSMMConfig(
            states=states,
            start_log_probabilities={
                "STATIONARY": 0.0,
                "ROLLING": -4.0,
                "UNKNOWN": -4.0,
            },
            transition_log_probabilities={
                state: {target: 0.0 for target in states} for state in states
            },
            durations={state: DurationSpec(1, 8, 2) for state in states},
        )
        result = recognize_sequence(
            frames,
            model,
            hsmm,
            event_probabilities=tuple({} for _ in frames),
        )
        self.assertEqual(len(result.state_path), len(frames))
        self.assertEqual(result.state_path[:4], ("STATIONARY",) * 4)
        self.assertEqual(result.state_path[4:], ("ROLLING",) * 4)
        self.assertFalse(result.authority)


if __name__ == "__main__":
    unittest.main()
