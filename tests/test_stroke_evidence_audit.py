from __future__ import annotations

import unittest
import json
from pathlib import Path
import tempfile

from tools.audit_stroke_evidence import cluster_bursts, ranges_overlap, read_post_go


class StrokeEvidenceAuditTests(unittest.TestCase):
    def test_candidate_crossings_are_merged_within_configured_gap(self) -> None:
        self.assertEqual(cluster_bursts([]), 0)
        self.assertEqual(cluster_bursts([1.0, 1.1, 1.26, 2.0]), 2)
        self.assertEqual(cluster_bursts([1.0, 1.17]), 2)

    def test_candidate_crossings_must_be_ordered(self) -> None:
        with self.assertRaisesRegex(ValueError, "ordered"):
            cluster_bursts([1.0, 0.5])

    def test_range_overlap_includes_touching_boundaries(self) -> None:
        self.assertTrue(ranges_overlap([1.0, 2.0], [2.0, 3.0]))
        self.assertFalse(ranges_overlap([1.0, 1.9], [2.0, 3.0]))

    def test_capture_without_go_marker_fails_closed(self) -> None:
        motion = {
            "record_type": "tag_motion",
            "protocol_version": 1,
            "sequence": 1,
            "source_monotonic_us": 1_000_000,
            "adxl367_valid": True,
            "bmi270_valid": True,
            "adxl367_accel_micro_ms2": [0, 0, 9_806_650],
            "bmi270_accel_micro_ms2": [0, 0, 9_806_650],
            "bmi270_gyro_micro_rads": [0, 0, 0],
            "sensor_error_bits": 0,
        }
        lines = [motion, {**motion, "sequence": 2, "source_monotonic_us": 1_020_000},
                 {"record_type": "tag_capture_result", "status": "PASS"}]
        with tempfile.TemporaryDirectory() as directory:
            capture = Path(directory) / "capture.jsonl"
            capture.write_text("".join(json.dumps(row) + "\n" for row in lines),
                               encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "exactly one GO marker"):
                read_post_go(capture)
