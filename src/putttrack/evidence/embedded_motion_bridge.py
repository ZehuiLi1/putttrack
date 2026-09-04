"""Stateful bridge from embedded Ball motion evidence to Edge candidates.

This module deliberately stops at candidate evidence. A playable lab demo may
visualise/count these candidates, but canonical Gameplay score authority remains
with the Edge fusion/game policy and physical Tee/Cup evidence.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from putttrack.tag.motion_evidence import EmbeddedMotionEvidence


@dataclass(frozen=True)
class EmbeddedMotionBridgeDecision:
    ball_id: str
    motion_state: str
    status: str
    candidate_type: str | None
    reason: str
    confidence: float
    tee_arm_epoch: int
    score_authoritative: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class EmbeddedMotionBridge:
    """Translate Ball state transitions into fail-closed one-hole candidates."""

    POLICY_VERSION = "embedded-motion-bridge-v0"

    def __init__(self) -> None:
        self._last_state: dict[str, str] = {}
        self._last_sequence: dict[str, int] = {}

    def evaluate(
        self,
        evidence: EmbeddedMotionEvidence,
        *,
        ball_id: str,
        active_ball_id: str | None,
        tee_ready: bool,
        cup_complete: bool,
    ) -> EmbeddedMotionBridgeDecision:
        previous_sequence = self._last_sequence.get(ball_id)
        previous_state = self._last_state.get(ball_id)

        def result(status: str, candidate: str | None, reason: str) -> EmbeddedMotionBridgeDecision:
            return EmbeddedMotionBridgeDecision(
                ball_id=ball_id,
                motion_state=evidence.motion_state,
                status=status,
                candidate_type=candidate,
                reason=reason,
                confidence=evidence.confidence,
                tee_arm_epoch=evidence.tee_arm_epoch,
            )

        if previous_sequence is not None and evidence.source_sequence <= previous_sequence:
            return result("rejected", None, "duplicate_or_out_of_order_motion_sequence")
        self._last_sequence[ball_id] = evidence.source_sequence
        self._last_state[ball_id] = evidence.motion_state

        if evidence.quality_bits & ((1 << 0) | (1 << 4)):
            return result("rejected", None, "invalid_or_discontinuous_motion_evidence")
        if evidence.motion_state == "UNKNOWN":
            return result("observed", None, "unknown_is_not_promoted")
        if ball_id != active_ball_id:
            return result("observed", None, "motion_for_non_active_ball")
        if cup_complete:
            return result("observed", None, "hole_already_complete")

        if "PICKUP_SUSPECTED" in evidence.events or evidence.motion_state == "CARRIED":
            return result("pending", "pickup.candidate", "independent_policy_required")

        if (
            tee_ready
            and previous_state == "STATIONARY"
            and evidence.motion_state == "ROLLING"
            and evidence.confidence >= 0.80
        ):
            return result(
                "pending",
                "stroke.candidate",
                "stationary_to_rolling_after_tee_ready",
            )

        if evidence.motion_state == "STATIONARY":
            return result("observed", "motion.stationary", "generic_motion_only")
        if evidence.motion_state == "ROLLING":
            return result("observed", "motion.rolling", "generic_motion_only")
        if evidence.motion_state == "SETTLING":
            return result("observed", "motion.settling", "generic_motion_only")
        if evidence.motion_state == "AIRBORNE":
            return result("pending", "drop.candidate", "independent_policy_required")
        return result("observed", None, "generic_motion_only")
