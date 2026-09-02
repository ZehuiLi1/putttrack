"""Fail-closed routing for generic Ball motion observations in the no-CS MVP."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from putttrack.contracts import MotionObservation


@dataclass(frozen=True)
class MotionEvidenceContext:
    session_id: str
    hole_id: str
    assigned_ball_ids: tuple[str, ...]
    active_ball_id: str | None
    active_player_id: str | None
    active_player_state: str | None


@dataclass(frozen=True)
class MotionCandidateDecision:
    observation_event_id: str
    motion_state: str
    status: str
    candidate_type: str | None
    reason: str
    policy_version: str
    score_authoritative: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class NoCsMotionCandidatePolicy:
    """Route motion to candidates while refusing direct score authority.

    This V0 policy intentionally cannot emit ``stroke.confirmed``,
    ``feature.confirmed`` or ``cup.confirmed``. Those require independent
    physical/context evidence and a later fusion policy.
    """

    POLICY_VERSION = "no-cs-motion-candidate-v0"

    _STATE_ROUTES = {
        "STATIONARY": ("observed", "motion.stationary"),
        "STATIONARY_CANDIDATE": ("observed", "motion.stationary"),
        "ACTIVE_MOTION": ("observed", "motion.active"),
        "ACTIVE_MOTION_CANDIDATE": ("observed", "motion.active"),
        "IMPACT": ("pending", "stroke.candidate"),
        "IMPACT_CANDIDATE": ("pending", "stroke.candidate"),
        "ROLLING": ("observed", "motion.rolling"),
        "ACTIVE_ROLLING": ("observed", "motion.rolling"),
        "SETTLING": ("observed", "motion.settling"),
        "PICKED_UP": ("pending", "pickup.candidate"),
        "CARRIED": ("pending", "pickup.candidate"),
        "PICKUP_CARRY": ("pending", "pickup.candidate"),
        "PICKED_UP_CARRIED": ("pending", "pickup.candidate"),
        "FREE_FALL": ("pending", "drop.candidate"),
        "FREE_FALL_CANDIDATE": ("pending", "drop.candidate"),
        "DROP": ("pending", "drop.candidate"),
        "DROP_CANDIDATE": ("pending", "drop.candidate"),
    }

    @staticmethod
    def _normalize_state(value: str) -> str:
        return value.strip().upper().replace("/", "_").replace("-", "_").replace(" ", "_")

    def evaluate(
        self,
        observation: MotionObservation,
        context: MotionEvidenceContext,
    ) -> MotionCandidateDecision:
        state = self._normalize_state(observation.motion_state)

        def decision(
            status: str,
            candidate_type: str | None,
            reason: str,
        ) -> MotionCandidateDecision:
            return MotionCandidateDecision(
                observation_event_id=observation.event_id,
                motion_state=state,
                status=status,
                candidate_type=candidate_type,
                reason=reason,
                policy_version=self.POLICY_VERSION,
            )

        if observation.hole_id is not None and observation.hole_id != context.hole_id:
            return decision("rejected", None, "observation_hole_is_not_current")
        if observation.ball_id is None:
            return decision("rejected", None, "ball_id_is_required")
        if observation.ball_id not in context.assigned_ball_ids:
            return decision("rejected", None, "ball_is_not_assigned_to_session")
        try:
            status, candidate_type = self._STATE_ROUTES[state]
        except KeyError:
            return decision("rejected", None, "unsupported_motion_state")

        action_candidate = status == "pending"
        if action_candidate and context.active_ball_id is None:
            return decision("rejected", candidate_type, "no_active_ball_context")
        if action_candidate and observation.ball_id != context.active_ball_id:
            return decision("rejected", candidate_type, "observation_is_not_for_active_ball")
        if action_candidate:
            return decision("pending", candidate_type, "independent_evidence_required")
        return decision("observed", candidate_type, "generic_motion_only")
