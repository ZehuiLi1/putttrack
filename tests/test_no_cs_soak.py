from __future__ import annotations

import unittest

from putttrack.venue.soak import run_no_cs_hole_soak


class NoCsSoakTests(unittest.TestCase):
    def test_small_soak_passes_expected_invariants(self) -> None:
        report = run_no_cs_hole_soak(rounds=5, players_per_round=3, seed=17)
        self.assertTrue(report.passed)
        self.assertEqual(report.rounds_completed, 5)
        self.assertEqual(report.status_counts["accepted"], 30)
        self.assertEqual(report.status_counts["pending"], 30)
        self.assertEqual(report.status_counts["rejected"], 45)
        self.assertEqual(sum(report.fault_counts.values()), 75)

    def test_seeded_soak_is_deterministic(self) -> None:
        first = run_no_cs_hole_soak(rounds=4, players_per_round=4, seed=23)
        second = run_no_cs_hole_soak(rounds=4, players_per_round=4, seed=23)
        self.assertEqual(first.authoritative_digest, second.authoritative_digest)
        self.assertEqual(first.status_counts, second.status_counts)
        self.assertEqual(first.fault_counts, second.fault_counts)

    def test_invalid_size_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            run_no_cs_hole_soak(rounds=0)
        with self.assertRaises(ValueError):
            run_no_cs_hole_soak(players_per_round=33)


if __name__ == "__main__":
    unittest.main()
