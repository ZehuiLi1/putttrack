from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from putttrack.motion.pickup_v0 import (  # noqa: E402
    PickupDecision,
    evaluate_pickup_v0,
    evaluate_capture_path,
    load_json,
    read_capture_jsonl,
)


G = 9.80665


class PickupV0Tests(unittest.TestCase):
    def test_decision_thresholds_have_one_configuration_source(self) -> None:
        detector = json.loads(
            (ROOT / "configs" / "research" / "pickup_detector_v0.json").read_text(
                encoding="utf-8"
            )
        )
        profile = json.loads(
            (
                ROOT
                / "configs"
                / "research"
                / "pickup_detector_v0_eval_profile.json"
            ).read_text(encoding="utf-8")
        )
        self.assertIn("stationary_baseline", detector)
        self.assertNotIn(
            "maximum_accel_norm_stdev_mps2", profile["pre_go_stationary"]
        )
        self.assertNotIn(
            "maximum_gyro_norm_rms_rads", profile["pre_go_stationary"]
        )

    def test_evaluation_profile_pins_frozen_detector_hash(self) -> None:
        detector_path = ROOT / "configs" / "research" / "pickup_detector_v0.json"
        profile_path = (
            ROOT
            / "configs"
            / "research"
            / "pickup_detector_v0_eval_profile.json"
        )
        capture_path = (
            ROOT
            / "experiments"
            / "research_ball_r1_pickup_precision_1c"
            / "raw"
            / "field-pickup-precision-1c-20260904-pickup_carry-r01.jsonl"
        )
        detector = load_json(detector_path)
        detector["vertical_impulse"]["minimum_mps"] = 0.51
        result = evaluate_pickup_v0(
            read_capture_jsonl(capture_path),
            detector,
            load_json(profile_path),
            manifest_label="pickup_carry",
        )
        self.assertEqual(result.decision, PickupDecision.UNKNOWN)
        self.assertEqual(result.reason_codes, ("detector_config_hash_mismatch",))

    def _write_capture(
        self,
        path: Path,
        *,
        mode: str,
        label: str = "pickup_carry",
        sequence_gap: bool = False,
    ) -> None:
        go_us = 2_000_000
        rows = [
            {
                "record_type": "tag_status",
                "episode_label": label,
                "device_id": "fixture-ball",
                "boot_id": "fixture-boot",
                "firmware_version": "fixture",
                "stream_rate_hz": 50,
            },
            {
                "record_type": "tag_episode_marker",
                "marker_kind": "action_start",
                "source_monotonic_us": go_us,
                "episode_label": label,
            },
            {
                "record_type": "tag_episode_window",
                "action_start_source_monotonic_us": go_us,
                "episode_label": label,
            },
        ]
        sequence = 1000
        for index in range(200):
            time_us = 500_000 + index * 20_000
            if sequence_gap and index == 100:
                sequence += 1
            accel = [0.0, 0.0, G]
            gyro = [0.0, 0.0, 0.0]
            action_time = (time_us - go_us) / 1_000_000.0
            if 0.70 <= action_time < 1.10:
                if mode == "pickup":
                    accel = [0.0, 0.0, G + 4.5]
                    phase = index % 4
                    gyro = (
                        [1.4, -1.0, 0.5]
                        if phase < 2
                        else [-1.0, 1.4, -0.5]
                    )
                elif mode == "rolling":
                    accel = [0.0, 0.0, G + 4.5]
                    gyro = [0.0, 15.0, 0.0]
                elif mode == "handling":
                    accel = [0.0, 0.0, G + 0.7]
                    gyro = [1.0 if index % 2 else -1.0, 0.4, 0.0]
                elif mode == "clipped":
                    accel = [0.0, 0.0, G + 4.5]
                    gyro = [35.0, 0.0, 0.0]
            rows.append(
                {
                    "record_type": "tag_motion",
                    "episode_label": label,
                    "protocol_version": 1,
                    "sequence": sequence,
                    "source_monotonic_us": time_us,
                    "adxl367_valid": True,
                    "bmi270_valid": True,
                    "adxl367_accel_micro_ms2": [0, 0, round(G * 1_000_000)],
                    "bmi270_accel_micro_ms2": [
                        round(value * 1_000_000) for value in accel
                    ],
                    "bmi270_gyro_micro_rads": [
                        round(value * 1_000_000) for value in gyro
                    ],
                    "sensor_error_bits": 0,
                }
            )
            sequence += 1
        rows.append(
            {"record_type": "tag_capture_result", "status": "PASS", "issues": []}
        )
        path.write_text(
            "".join(
                json.dumps(row, separators=(",", ":")) + "\n" for row in rows
            ),
            encoding="utf-8",
        )

    def _evaluate(
        self,
        mode: str,
        *,
        label: str = "pickup_carry",
        manifest_label: str | None = None,
        gap: bool = False,
        mutate=None,
    ):
        with tempfile.TemporaryDirectory() as temp:
            capture = Path(temp) / "episode.jsonl"
            self._write_capture(
                capture, mode=mode, label=label, sequence_gap=gap
            )
            if mutate is not None:
                rows = [
                    json.loads(line)
                    for line in capture.read_text(encoding="utf-8").splitlines()
                ]
                mutate(rows)
                capture.write_text(
                    "".join(
                        json.dumps(row, separators=(",", ":")) + "\n"
                        for row in rows
                    ),
                    encoding="utf-8",
                )
            return evaluate_capture_path(
                capture,
                ROOT / "configs" / "research" / "pickup_detector_v0.json",
                ROOT
                / "configs"
                / "research"
                / "pickup_detector_v0_eval_profile.json",
                manifest_label=manifest_label or label,
            )

    def test_stationary_start_pickup_passes_frozen_rule(self) -> None:
        result = self._evaluate("pickup")
        self.assertEqual(result.decision, PickupDecision.PICKUP_SUSPECTED)
        self.assertFalse(result.authority)
        self.assertTrue(all(result.rule_passes.values()))
        self.assertIsNotNone(result.features)
        assert result.features is not None
        self.assertGreater(
            result.features.positive_vertical_impulse_mps or 0.0, 0.5
        )

    def test_single_axis_fast_roll_is_not_pickup(self) -> None:
        result = self._evaluate("rolling", label="putt_gentle")
        self.assertEqual(result.decision, PickupDecision.NOT_PICKUP)
        self.assertFalse(result.rule_passes["axis_consistency"])
        self.assertFalse(all(result.rule_passes.values()))

    def test_no_lift_handling_is_not_pickup(self) -> None:
        result = self._evaluate("handling", label="handling")
        self.assertEqual(result.decision, PickupDecision.NOT_PICKUP)
        self.assertFalse(result.rule_passes["positive_vertical_impulse"])

    def test_clipped_feature_window_fails_closed(self) -> None:
        result = self._evaluate("clipped")
        self.assertEqual(result.decision, PickupDecision.UNKNOWN)
        self.assertIn(
            "bmi270_gyro_clipping_inside_feature_window", result.reason_codes
        )

    def test_sequence_gap_fails_closed(self) -> None:
        result = self._evaluate("pickup", gap=True)
        self.assertEqual(result.decision, PickupDecision.UNKNOWN)
        self.assertIn("sequence_gap_or_reordering", result.reason_codes)

    def test_rolling_pickup_is_explicitly_unsupported(self) -> None:
        result = self._evaluate("pickup", label="rolling_pickup")
        self.assertEqual(result.decision, PickupDecision.UNKNOWN)
        self.assertEqual(
            result.reason_codes, ("unsupported_rolling_start_path",)
        )

    def test_manifest_and_capture_label_mismatch_fails_closed(self) -> None:
        result = self._evaluate(
            "pickup", label="pickup_carry", manifest_label="handling"
        )
        self.assertEqual(result.decision, PickupDecision.UNKNOWN)
        self.assertIn("manifest_capture_label_mismatch", result.reason_codes)

    def test_missing_and_multiple_capture_labels_fail_closed(self) -> None:
        def remove_labels(rows):
            for row in rows:
                row.pop("episode_label", None)

        missing = self._evaluate("pickup", mutate=remove_labels)
        self.assertEqual(missing.decision, PickupDecision.UNKNOWN)
        self.assertIn("missing_episode_label", missing.reason_codes)

        def add_conflicting_label(rows):
            next(
                row for row in rows if row.get("record_type") == "tag_motion"
            )["episode_label"] = "handling"

        multiple = self._evaluate("pickup", mutate=add_conflicting_label)
        self.assertEqual(multiple.decision, PickupDecision.UNKNOWN)
        self.assertIn("multiple_episode_labels", multiple.reason_codes)

    def test_missing_multiple_and_mismatched_go_markers_fail_closed(self) -> None:
        def remove_go(rows):
            rows[:] = [
                row
                for row in rows
                if row.get("record_type")
                not in {"tag_episode_marker", "tag_episode_window"}
            ]

        missing = self._evaluate("pickup", mutate=remove_go)
        self.assertEqual(missing.decision, PickupDecision.UNKNOWN)
        self.assertIn("missing_device_side_go_marker", missing.reason_codes)

        def duplicate_go(rows):
            rows.insert(
                2,
                {
                    "record_type": "tag_episode_marker",
                    "marker_kind": "action_start",
                    "source_monotonic_us": 2_020_000,
                    "episode_label": "pickup_carry",
                },
            )

        multiple = self._evaluate("pickup", mutate=duplicate_go)
        self.assertEqual(multiple.decision, PickupDecision.UNKNOWN)
        self.assertIn("multiple_action_start_markers", multiple.reason_codes)

        def mismatch_go(rows):
            next(
                row
                for row in rows
                if row.get("record_type") == "tag_episode_window"
            )["action_start_source_monotonic_us"] = 2_020_000

        mismatched = self._evaluate("pickup", mutate=mismatch_go)
        self.assertEqual(mismatched.decision, PickupDecision.UNKNOWN)
        self.assertIn("action_start_marker_mismatch", mismatched.reason_codes)

    def test_time_sensor_capture_and_rate_errors_fail_closed(self) -> None:
        def regress_time(rows):
            motions = [row for row in rows if row.get("record_type") == "tag_motion"]
            motions[100]["source_monotonic_us"] = motions[99]["source_monotonic_us"]

        time_result = self._evaluate("pickup", mutate=regress_time)
        self.assertEqual(time_result.decision, PickupDecision.UNKNOWN)
        self.assertIn("source_time_regression", time_result.reason_codes)

        def invalidate_sensor(rows):
            motion = next(
                row for row in rows if row.get("record_type") == "tag_motion"
            )
            motion["bmi270_valid"] = False
            motion["sensor_error_bits"] = 1

        sensor_result = self._evaluate("pickup", mutate=invalidate_sensor)
        self.assertEqual(sensor_result.decision, PickupDecision.UNKNOWN)
        self.assertIn(
            "sensor_invalid_or_error_bits_nonzero", sensor_result.reason_codes
        )

        def fail_capture(rows):
            next(
                row
                for row in rows
                if row.get("record_type") == "tag_capture_result"
            )["status"] = "FAIL"

        capture_result = self._evaluate("pickup", mutate=fail_capture)
        self.assertEqual(capture_result.decision, PickupDecision.UNKNOWN)
        self.assertIn("capture_not_pass", capture_result.reason_codes)

        def remove_capture_result(rows):
            rows[:] = [
                row
                for row in rows
                if row.get("record_type") != "tag_capture_result"
            ]

        missing_capture_result = self._evaluate(
            "pickup", mutate=remove_capture_result
        )
        self.assertEqual(missing_capture_result.decision, PickupDecision.UNKNOWN)
        self.assertIn("capture_not_pass", missing_capture_result.reason_codes)

        def slow_rate(rows):
            motions = [row for row in rows if row.get("record_type") == "tag_motion"]
            first = motions[0]["source_monotonic_us"]
            for index, motion in enumerate(motions):
                motion["source_monotonic_us"] = first + index * 40_000

        rate_result = self._evaluate("pickup", mutate=slow_rate)
        self.assertEqual(rate_result.decision, PickupDecision.UNKNOWN)
        self.assertIn("unexpected_source_rate", rate_result.reason_codes)

    def test_baseline_and_feature_window_errors_fail_closed(self) -> None:
        def shorten_baseline(rows):
            rows[:] = [
                row
                for row in rows
                if row.get("record_type") != "tag_motion"
                or row["source_monotonic_us"] >= 1_500_000
            ]

        short = self._evaluate("pickup", mutate=shorten_baseline)
        self.assertEqual(short.decision, PickupDecision.UNKNOWN)
        self.assertIn("insufficient_pre_go_baseline_samples", short.reason_codes)

        def move_baseline(rows):
            for index, row in enumerate(
                row for row in rows if row.get("record_type") == "tag_motion"
            ):
                if 1_000_000 <= row["source_monotonic_us"] < 2_000_000:
                    row["bmi270_accel_micro_ms2"][2] += (
                        1_000_000 if index % 2 else -1_000_000
                    )

        moving = self._evaluate("pickup", mutate=move_baseline)
        self.assertEqual(moving.decision, PickupDecision.UNKNOWN)
        self.assertIn("pre_go_baseline_not_stationary", moving.reason_codes)

        def truncate_action(rows):
            rows[:] = [
                row
                for row in rows
                if row.get("record_type") != "tag_motion"
                or row["source_monotonic_us"] < 3_000_000
            ]

        truncated = self._evaluate("pickup", mutate=truncate_action)
        self.assertEqual(truncated.decision, PickupDecision.UNKNOWN)
        self.assertIn("insufficient_feature_window", truncated.reason_codes)

    def test_real_repository_captures_preserve_expected_regression_results(self) -> None:
        detector = ROOT / "configs" / "research" / "pickup_detector_v0.json"
        profile = (
            ROOT
            / "configs"
            / "research"
            / "pickup_detector_v0_eval_profile.json"
        )
        cases = (
            (
                ROOT
                / "experiments"
                / "research_ball_r1_pickup_precision_1c"
                / "raw"
                / "field-pickup-precision-1c-20260904-pickup_carry-r01.jsonl",
                "pickup_carry",
                PickupDecision.PICKUP_SUSPECTED,
            ),
            (
                ROOT
                / "experiments"
                / "research_ball_r1_pickup_precision_1a"
                / "raw"
                / "field-pickup-precision-1a-20260904-183730-handling-r01.jsonl",
                "handling",
                PickupDecision.NOT_PICKUP,
            ),
            (
                ROOT
                / "experiments"
                / "research_ball_r1_pickup_precision_1e_rail"
                / "raw"
                / "field-pickup-precision-1e-rail-20260904-putt_rail_collision-r01.jsonl",
                "putt_rail_collision",
                PickupDecision.UNKNOWN,
            ),
        )
        results = []
        for capture, label, expected in cases:
            with self.subTest(label=label):
                result = evaluate_capture_path(
                    capture,
                    detector,
                    profile,
                    manifest_label=label,
                )
                self.assertEqual(result.decision, expected)
                self.assertFalse(result.authority)
                results.append(result)

        assert results[0].features is not None
        self.assertAlmostEqual(
            results[0].features.positive_vertical_impulse_mps or 0.0,
            1.290720761216339,
            places=9,
        )
        self.assertEqual(
            results[2].reason_codes,
            ("bmi270_gyro_clipping_inside_feature_window",),
        )


if __name__ == "__main__":
    unittest.main()
