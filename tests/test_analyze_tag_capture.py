from __future__ import annotations

import unittest

from tools.analyze_tag_capture import expected_states_for_label


class AnalyzeTagCaptureTests(unittest.TestCase):
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
