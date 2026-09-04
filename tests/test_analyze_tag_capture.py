from __future__ import annotations

import unittest

from putttrack.tag import MotionRecord
from tools.analyze_tag_capture import expected_states_for_label, split_armed_records


def sample(sequence: int) -> MotionRecord:
    return MotionRecord(
        protocol_version=1,
        sequence=sequence,
        source_monotonic_us=sequence * 20_000,
        adxl367_valid=True,
        bmi270_valid=True,
        adxl367_accel_micro_ms2=(0, 0, 9_806_650),
        bmi270_accel_micro_ms2=(0, 0, 9_806_650),
        bmi270_gyro_micro_rads=(0, 0, 0),
        sensor_error_bits=0,
    )


class AnalyzeTagCaptureTests(unittest.TestCase):
    def test_manual_pickup_profiles_require_measured_motion(self) -> None:
        for label in ("pickup_carry", "pickup_drop", "rolling_pickup"):
            with self.subTest(label=label):
                self.assertEqual(
                    expected_states_for_label(label),
                    ("ACTIVE_MOTION_CANDIDATE",),
                )

    def test_all_field_action_profiles_require_measured_motion(self) -> None:
        for label in (
            "putt_gentle",
            "putt_normal",
            "putt_firm",
            "hand_roll",
            "putt_rail_collision",
            "track_step_drop",
        ):
            with self.subTest(label=label):
                self.assertEqual(
                    expected_states_for_label(label),
                    ("ACTIVE_MOTION_CANDIDATE",),
                )

    def test_armed_records_use_pre_go_baseline_and_post_go_episode(self) -> None:
        records = [sample(sequence) for sequence in range(100, 301)]

        baseline, episode = split_armed_records(records, 4_000_000)

        self.assertEqual(baseline[0].source_monotonic_us, 2_800_000)
        self.assertEqual(baseline[-1].source_monotonic_us, 3_980_000)
        self.assertEqual(episode[0].source_monotonic_us, 4_000_000)

    def test_legacy_capture_without_marker_uses_complete_window(self) -> None:
        records = [sample(sequence) for sequence in range(100, 110)]

        baseline, episode = split_armed_records(records, None)

        self.assertEqual(baseline, [])
        self.assertEqual(episode, records)

    def test_nonzero_roller_command_requires_measured_motion(self) -> None:
        self.assertEqual(
            expected_states_for_label("roller_30rpm"),
            ("ACTIVE_MOTION_CANDIDATE",),
        )
        self.assertEqual(
            expected_states_for_label("roller_60rpm_diagnostic"),
            ("ACTIVE_MOTION_CANDIDATE",),
        )
        self.assertEqual(
            expected_states_for_label("roller_-120rpm_reverse"),
            ("ACTIVE_MOTION_CANDIDATE",),
        )

    def test_zero_rpm_roller_label_requires_stationary_measurement(self) -> None:
        self.assertEqual(
            expected_states_for_label("roller_0rpm_baseline"),
            ("STATIONARY_CANDIDATE",),
        )

    def test_unknown_label_remains_unchecked(self) -> None:
        self.assertIsNone(expected_states_for_label("custom_experiment"))


if __name__ == "__main__":
    unittest.main()
