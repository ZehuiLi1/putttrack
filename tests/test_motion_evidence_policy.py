from __future__ import annotations

import unittest

from putttrack.contracts import MotionObservation
from putttrack.evidence import MotionEvidenceContext, NoCsMotionCandidatePolicy


def observation(
    state: str,
    *,
    ball_id: str | None = "ball-1",
    hole_id: str | None = "H01",
) -> MotionObservation:
    return MotionObservation(
        event_id=f"motion-{state}-{ball_id}",
        event_type="ball.motion_observed",
        source_device_id="tag-1",
        source_boot_id="boot-1",
        sequence=12,
        source_monotonic_ns=240_000_000,
        edge_received_ns=250_000_000,
        trace_id="trace-1",
        hole_id=hole_id,
        ball_id=ball_id,
        firmware_version="0.1.5",
        model_version="motion-v0",
        raw_evidence_refs=("runs/window.jsonl",),
        motion_state=state,
        confidence=0.8,
        accel_mps2=(0.0, 0.0, 9.81),
        gyro_rads=(0.0, 0.0, 0.0),
        raw_window_ref="runs/window.jsonl",
    )


class MotionEvidencePolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = MotionEvidenceContext(
            session_id="session-1",
            hole_id="H01",
            assigned_ball_ids=("ball-1", "ball-2"),
            active_ball_id="ball-1",
            active_player_id="player-1",
            active_player_state="armed",
        )
        self.policy = NoCsMotionCandidatePolicy()

    def test_impact_is_pending_and_never_authoritative(self) -> None:
        decision = self.policy.evaluate(observation("IMPACT_CANDIDATE"), self.context)

        self.assertEqual(decision.status, "pending")
        self.assertEqual(decision.candidate_type, "stroke.candidate")
        self.assertFalse(decision.score_authoritative)
        self.assertNotEqual(decision.candidate_type, "stroke.confirmed")

    def test_stationary_is_generic_observation(self) -> None:
        decision = self.policy.evaluate(observation("STATIONARY_CANDIDATE"), self.context)

        self.assertEqual(decision.status, "observed")
        self.assertEqual(decision.candidate_type, "motion.stationary")

    def test_active_motion_remains_generic_and_non_authoritative(self) -> None:
        decision = self.policy.evaluate(
            observation("ACTIVE_MOTION_CANDIDATE"), self.context
        )

        self.assertEqual(decision.status, "observed")
        self.assertEqual(decision.candidate_type, "motion.active")
        self.assertFalse(decision.score_authoritative)

    def test_unclassified_motion_is_rejected_without_score_authority(self) -> None:
        decision = self.policy.evaluate(observation("UNCLASSIFIED"), self.context)

        self.assertEqual(decision.status, "rejected")
        self.assertEqual(decision.reason, "unsupported_motion_state")
        self.assertFalse(decision.score_authoritative)

    def test_foreign_ball_action_is_rejected(self) -> None:
        decision = self.policy.evaluate(
            observation("IMPACT_CANDIDATE", ball_id="foreign"), self.context
        )

        self.assertEqual(decision.status, "rejected")
        self.assertEqual(decision.reason, "ball_is_not_assigned_to_session")

    def test_inactive_assigned_ball_action_is_rejected(self) -> None:
        decision = self.policy.evaluate(
            observation("PICKED_UP", ball_id="ball-2"), self.context
        )

        self.assertEqual(decision.status, "rejected")
        self.assertEqual(decision.reason, "observation_is_not_for_active_ball")


if __name__ == "__main__":
    unittest.main()
