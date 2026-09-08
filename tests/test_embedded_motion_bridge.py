from __future__ import annotations

import unittest

from putttrack.evidence.embedded_motion_bridge import EmbeddedMotionBridge
from putttrack.tag.motion_evidence import EmbeddedMotionEvidence


def evidence(seq: int, state: str, *, events: tuple[str, ...] = (), confidence: float = 0.95, quality_bits: int = 0) -> EmbeddedMotionEvidence:
    code = {"UNKNOWN": 0, "STATIONARY": 1, "ROLLING": 2, "SETTLING": 3, "CARRIED": 4, "AIRBORNE": 5}[state]
    return EmbeddedMotionEvidence(
        protocol_version=1,
        state_code=code,
        motion_state=state,
        event_bits=0,
        events=events,
        source_sequence=seq,
        source_time_us=seq * 20_000,
        confidence=confidence,
        quality_bits=quality_bits,
        quality=(),
        model_hash32=0x62C82C1A,
        tee_arm_epoch=1,
    )


class EmbeddedMotionBridgeTests(unittest.TestCase):
    def test_stationary_to_rolling_is_candidate_only(self) -> None:
        bridge = EmbeddedMotionBridge()
        bridge.evaluate(
            evidence(1, "STATIONARY"),
            ball_id="ball-1",
            active_ball_id="ball-1",
            tee_ready=True,
            cup_complete=False,
        )
        decision = bridge.evaluate(
            evidence(2, "ROLLING"),
            ball_id="ball-1",
            active_ball_id="ball-1",
            tee_ready=True,
            cup_complete=False,
        )
        self.assertEqual(decision.candidate_type, "stroke.candidate")
        self.assertEqual(decision.status, "pending")
        self.assertFalse(decision.score_authoritative)

    def test_pickup_never_becomes_stroke(self) -> None:
        bridge = EmbeddedMotionBridge()
        bridge.evaluate(
            evidence(1, "STATIONARY"),
            ball_id="ball-1",
            active_ball_id="ball-1",
            tee_ready=True,
            cup_complete=False,
        )
        decision = bridge.evaluate(
            evidence(2, "CARRIED", events=("PICKUP_SUSPECTED",)),
            ball_id="ball-1",
            active_ball_id="ball-1",
            tee_ready=True,
            cup_complete=False,
        )
        self.assertEqual(decision.candidate_type, "pickup.candidate")
        self.assertFalse(decision.score_authoritative)

    def test_unknown_fails_closed(self) -> None:
        bridge = EmbeddedMotionBridge()
        decision = bridge.evaluate(
            evidence(1, "UNKNOWN"),
            ball_id="ball-1",
            active_ball_id="ball-1",
            tee_ready=True,
            cup_complete=False,
        )
        self.assertIsNone(decision.candidate_type)
        self.assertEqual(decision.reason, "unknown_is_not_promoted")


if __name__ == "__main__":
    unittest.main()
