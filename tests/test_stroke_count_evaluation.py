import unittest

from tools.evaluate_stroke_counts import evaluate


def episode(name, actual, predicted, **changes):
    return dict(episode_id=name, session_id="s1", scenario="test_fixture",
                truth_source="synthetic_fixture", raw_capture="synthetic_fixture",
                operator_reviewed=True, actual_strokes=actual,
                predicted_strokes=predicted, unknown_reason="quality_gap", **changes)


class StrokeCountEvaluationTests(unittest.TestCase):
    def test_over_and_under_counts_do_not_cancel_and_unknown_is_not_zero(self):
        result = evaluate(dict(schema_version=1, detector_id="fixture", episodes=[
            episode("one", 1, 2), episode("two", 2, 1),
            episode("three", 0, None), episode("four", 0, 0)]))
        s = result["overall"]
        self.assertEqual(s["overcount_strokes"], 1)
        self.assertEqual(s["undercount_strokes"], 1)
        self.assertEqual(s["unknown"], 1)
        self.assertEqual(s["coverage"], .75)
        self.assertEqual(s["exact_count_rate_all_episodes"], .25)
        self.assertFalse(result["authority"])

    def test_unreviewed_invalid_counts_and_duplicates_rejected(self):
        for changes in ({"operator_reviewed": False}, {"actual_strokes": True},
                        {"predicted_strokes": -1}, {"truth_source": ""}):
            row = episode("one", 1, 1)
            row.update(changes)
            with self.assertRaises(ValueError):
                evaluate(dict(schema_version=1, detector_id="fixture", episodes=[row]))
        row = episode("same", 1, 1)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            evaluate(dict(schema_version=1, detector_id="fixture", episodes=[row, row]))

    def test_all_unknown_has_no_decided_error_metric(self):
        result = evaluate(dict(schema_version=1, detector_id="fixture",
                               episodes=[episode("one", 1, None)]))
        self.assertIsNone(result["overall"]["mean_absolute_count_error_decided"])
        self.assertEqual(result["overall"]["coverage"], 0)
