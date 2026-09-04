from __future__ import annotations

import json
from pathlib import Path
import unittest

import numpy as np
import pandas as pd

from tools.imu_state_discovery import (
    Capture,
    Episode,
    classify_semantic_quality,
    integrate_trapezoid,
    load_v0_config,
    loo_predictions,
    model_catalog,
    v0_predict,
)


ROOT = Path(__file__).resolve().parents[1]


def supported_row(**overrides: object) -> pd.Series:
    values: dict[str, object] = {
        "label": "pickup_carry",
        "go_marker_present": 1,
        "valid_fraction": 1.0,
        "sequence_gaps": 0,
        "time_or_sequence_regressions": 0,
        "baseline_acc_norm_std": 0.05,
        "baseline_gyro_rms": 0.02,
        "onset_present": 1,
        "gyro_clip_in_first_1s": 0,
        "vertical_impulse_pos_0p6": 0.7,
        "onset_1s_gyro_mean": 2.0,
        "onset_1s_axis_consistency": 0.4,
    }
    values.update(overrides)
    return pd.Series(values)


class ImuStateDiscoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_v0_config(ROOT)

    def test_frozen_config_remains_non_authoritative(self) -> None:
        self.assertIs(self.config["authority"], False)
        self.assertIn("stationary_baseline", self.config)

    def test_numpy_two_compatible_trapezoid_integral(self) -> None:
        self.assertAlmostEqual(
            integrate_trapezoid(np.asarray([0.0, 1.0, 2.0]), np.asarray([0.0, 1.0, 2.0])),
            2.0,
        )

    def test_supported_pickup_uses_frozen_thresholds(self) -> None:
        self.assertEqual(v0_predict(supported_row(), self.config), ("PICKUP", "frozen_v0_rule"))

    def test_rail_and_step_negatives_are_scorable(self) -> None:
        for label in ("putt_rail_collision", "track_step_drop"):
            with self.subTest(label=label):
                prediction, reason = v0_predict(
                    supported_row(label=label, vertical_impulse_pos_0p6=0.1), self.config
                )
                self.assertEqual((prediction, reason), ("NOT_PICKUP", "frozen_v0_rule"))

    def test_rolling_pickup_fails_closed_as_unsupported(self) -> None:
        prediction, reason = v0_predict(supported_row(label="rolling_pickup"), self.config)
        self.assertEqual(prediction, "UNKNOWN")
        self.assertEqual(reason, "unsupported_rolling_start_pickup")

    def test_bad_baseline_without_onset_does_not_become_negative(self) -> None:
        prediction, reason = v0_predict(
            supported_row(label="handling", onset_present=0, baseline_acc_norm_std=0.5),
            self.config,
        )
        self.assertEqual(prediction, "UNKNOWN")
        self.assertIn("pre_go_not_stationary", reason)

    def test_binary_leave_one_out_keeps_numeric_target_type(self) -> None:
        features = pd.DataFrame({"feature": [0.0, 0.1, 0.9, 1.0]})
        target = pd.Series([0, 0, 1, 1])
        predictions, summary = loo_predictions(
            features,
            target,
            {"logistic": model_catalog(1, binary=True)["logistic"]},
            ["a", "b", "c", "d"],
        )
        self.assertEqual(len(predictions), 4)
        self.assertEqual(int(summary.iloc[0]["n"]), 4)

    def test_dataset_note_about_one_obstacle_does_not_exclude_every_episode(self) -> None:
        episode = Episode(
            key="e",
            source="manifest::test",
            dataset_id="d",
            capture_path="experiments/test/raw/putt-r01.jsonl",
            label="putt_gentle",
            session="s",
            operator="A",
            device_id="device",
            boot_id="boot",
            firmware_version="fw",
            core_revision="core",
            shell_revision="shell",
            surface="felt",
            orientation="varied",
            strength="light-planned",
            notes="Episode r05 hit an obstacle; this is r01.",
            quality_declared="manifest_operator_label",
            raw_text="",
            sha256="sha",
        )
        capture = Capture(
            t=np.asarray([0.0, 0.02]),
            seq=np.asarray([1, 2]),
            acc=np.zeros((2, 3)),
            gyro=np.zeros((2, 3)),
            adxl=np.zeros((2, 3)),
            valid=np.ones(2, dtype=bool),
            error_bits=np.zeros(2, dtype=int),
            go_us=0,
            status={},
            final_status={},
            malformed_lines=0,
            capture_pass=True,
            embedded_labels=("putt_gentle",),
        )
        quality, reasons = classify_semantic_quality(episode, capture, has_onset=True)
        self.assertEqual(quality, "CLEAN_OPERATOR_LABEL")
        self.assertEqual(reasons, [])

    def test_config_is_valid_json(self) -> None:
        path = ROOT / "configs" / "research" / "pickup_detector_v0.json"
        self.assertIsInstance(json.loads(path.read_text(encoding="utf-8")), dict)


if __name__ == "__main__":
    unittest.main()
