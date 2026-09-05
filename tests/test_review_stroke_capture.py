from __future__ import annotations

import argparse
from pathlib import Path
import tempfile
import unittest

from tools.review_stroke_capture import build_review, parse_contact_times


class StrokeCaptureReviewTests(unittest.TestCase):
    def args(self, capture: Path, **changes) -> argparse.Namespace:
        values = dict(capture=capture, actual_strokes=2, contact_times="1.2,4.8",
                      episode_id=None, session_id="s1", scenario="stroke_two_after_stop",
                      truth_source="video_review", notes="reviewed")
        values.update(changes)
        return argparse.Namespace(**values)

    def test_review_hashes_raw_capture_and_records_event_times(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            capture = Path(directory) / "capture.jsonl"
            capture.write_text('{"record_type":"tag_motion"}\n', encoding="utf-8")
            result = build_review(self.args(capture))
        self.assertEqual(result["actual_strokes"], 2)
        self.assertEqual(result["contact_times_from_go_s"], [1.2, 4.8])
        self.assertEqual(result["episode_id"], "capture")
        self.assertEqual(len(result["raw_capture_sha256"]), 64)
        self.assertFalse(result["authority"])

    def test_zero_stroke_control_requires_no_contact_times(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            capture = Path(directory) / "control.jsonl"
            capture.write_text("{}\n", encoding="utf-8")
            result = build_review(self.args(capture, actual_strokes=0, contact_times=""))
        self.assertEqual(result["contact_times_from_go_s"], [])

    def test_count_and_times_must_agree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            capture = Path(directory) / "capture.jsonl"
            capture.write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "count"):
                build_review(self.args(capture, actual_strokes=1))
            with self.assertRaises(ValueError):
                build_review(self.args(capture, actual_strokes=True,
                                       contact_times="1.0"))
        for value in ("2,1", "1,1", "nan"):
            with self.assertRaises(ValueError):
                parse_contact_times(value)
