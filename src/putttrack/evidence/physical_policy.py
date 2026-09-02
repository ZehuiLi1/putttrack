"""Fail-closed tee/cup physical evidence policy for the no-CS vertical slice."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Callable

from putttrack.contracts import (
    EvidenceEvent,
    PhysicalSensorObservation,
    record_to_dict,
)

from .ordering import OrderingTracker


@dataclass(frozen=True)
class PhysicalEvidenceContext:
    session_id: str
    hole_id: str
    assigned_ball_ids: tuple[str, ...]
    active_ball_id: str | None
    active_player_id: str | None
    active_player_state: str | None


@dataclass(frozen=True)
class PhysicalEvidenceDecision:
    observation_event_id: str
    sensor_kind: str
    transition: str
    status: str
    candidate_type: str | None
    semantic_type: str | None
    reason: str
    policy_version: str
    authority_granted: bool = False
    evidence_event: EvidenceEvent | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation_event_id": self.observation_event_id,
            "sensor_kind": self.sensor_kind,
            "transition": self.transition,
            "status": self.status,
            "candidate_type": self.candidate_type,
            "semantic_type": self.semantic_type,
            "reason": self.reason,
            "policy_version": self.policy_version,
            "authority_granted": self.authority_granted,
            "evidence_event": (
                record_to_dict(self.evidence_event)
                if self.evidence_event is not None
                else None
            ),
        }


@dataclass(frozen=True)
class _CupEntryCandidate:
    observation: PhysicalSensorObservation
    ball_id: str
    hole_id: str


DecisionFactory = Callable[..., PhysicalEvidenceDecision]


class NoCsPhysicalEvidencePolicy:
    """Convert narrowly validated tee/cup sequences to semantic evidence.

    Electrical debounce belongs at the sensor node and is identified by the
    required ``debounce_version``. This Edge policy adds ordering, identity,
    game-context and multi-sensor semantic gates. It never confirms a stroke or
    feature and a single cup edge can never complete a hole.
    """

    POLICY_VERSION = "no-cs-physical-v0"
    CUP_CONFIRM_WINDOW_NS = 3_000_000_000

    TEE_KIND = "tee_presence"
    CUP_ENTRY_KIND = "cup_entry"
    CUP_PRESENCE_KIND = "cup_presence"
    _SUPPORTED_KINDS = {TEE_KIND, CUP_ENTRY_KIND, CUP_PRESENCE_KIND}

    def __init__(self) -> None:
        self._ordering = OrderingTracker()
        self._decisions: dict[str, PhysicalEvidenceDecision] = {}
        self._cup_entry: _CupEntryCandidate | None = None

    @staticmethod
    def _normalize(value: str) -> str:
        return value.strip().lower().replace("-", "_").replace(" ", "_")

    @staticmethod
    def _evidence_id(semantic_type: str, *observation_ids: str) -> str:
        digest = hashlib.sha256("|".join(observation_ids).encode("utf-8")).hexdigest()
        return f"physical-{semantic_type.replace('.', '-')}-{digest[:24]}"

    def _decision(
        self,
        observation: PhysicalSensorObservation,
        *,
        sensor_kind: str,
        transition: str,
        status: str,
        candidate_type: str | None,
        semantic_type: str | None,
        reason: str,
        evidence_event: EvidenceEvent | None = None,
    ) -> PhysicalEvidenceDecision:
        decision = PhysicalEvidenceDecision(
            observation_event_id=observation.event_id,
            sensor_kind=sensor_kind,
            transition=transition,
            status=status,
            candidate_type=candidate_type,
            semantic_type=semantic_type,
            reason=reason,
            policy_version=self.POLICY_VERSION,
            authority_granted=evidence_event is not None,
            evidence_event=evidence_event,
        )
        self._decisions[observation.event_id] = decision
        return decision

    @staticmethod
    def _common_evidence(
        observation: PhysicalSensorObservation,
        context: PhysicalEvidenceContext,
        *,
        event_id: str,
        semantic_type: str,
        ball_id: str,
        player_id: str | None,
        raw_evidence_refs: tuple[str, ...],
        metadata: dict[str, Any],
    ) -> EvidenceEvent:
        return EvidenceEvent(
            event_id=event_id,
            event_type=semantic_type,
            semantic_type=semantic_type,
            source_device_id=observation.source_device_id,
            source_boot_id=observation.source_boot_id,
            sequence=observation.sequence,
            source_monotonic_ns=observation.source_monotonic_ns,
            edge_received_ns=observation.edge_received_ns,
            trace_id=observation.trace_id,
            correlation_id=observation.correlation_id,
            venue_id=observation.venue_id,
            zone_id=observation.zone_id,
            hole_id=context.hole_id,
            ball_id=ball_id,
            firmware_version=observation.firmware_version,
            config_version=observation.config_version,
            raw_evidence_refs=raw_evidence_refs,
            wall_time=observation.wall_time,
            session_id=context.session_id,
            player_id=player_id,
            confidence=1.0,
            fusion_policy_version=NoCsPhysicalEvidencePolicy.POLICY_VERSION,
            payload={"metadata": metadata},
        )

    @staticmethod
    def _value_matches_transition(
        observation: PhysicalSensorObservation,
        transition: str,
    ) -> bool:
        if observation.value is None:
            return True
        if transition in {"occupied", "entered"}:
            return observation.value is True
        if transition == "vacant":
            return observation.value is False
        return True

    def evaluate(
        self,
        observation: PhysicalSensorObservation,
        context: PhysicalEvidenceContext,
    ) -> PhysicalEvidenceDecision:
        previous = self._decisions.get(observation.event_id)
        if previous is not None:
            return previous

        sensor_kind = self._normalize(observation.sensor_kind)
        transition = self._normalize(observation.transition)

        def decide(
            status: str,
            candidate_type: str | None,
            reason: str,
            *,
            semantic_type: str | None = None,
            evidence_event: EvidenceEvent | None = None,
        ) -> PhysicalEvidenceDecision:
            if status == "rejected" and sensor_kind in {
                self.CUP_ENTRY_KIND,
                self.CUP_PRESENCE_KIND,
            }:
                self._cup_entry = None
            return self._decision(
                observation,
                sensor_kind=sensor_kind,
                transition=transition,
                status=status,
                candidate_type=candidate_type,
                semantic_type=semantic_type,
                reason=reason,
                evidence_event=evidence_event,
            )

        if observation.event_type != "sensor.edge_observed":
            return decide("rejected", None, "unsupported_event_type")
        if observation.hole_id is None:
            return decide("rejected", None, "hole_id_is_required")
        if observation.hole_id != context.hole_id:
            return decide("rejected", None, "observation_hole_is_not_current")
        if sensor_kind not in self._SUPPORTED_KINDS:
            return decide("rejected", None, "unsupported_sensor_kind")
        if self._normalize(observation.health) != "ok":
            return decide("rejected", None, "sensor_health_is_not_ok")
        if observation.debounce_version is None:
            return decide("rejected", None, "debounce_version_is_required")
        if not self._value_matches_transition(observation, transition):
            return decide("rejected", None, "transition_value_mismatch")

        ordering = self._ordering.observe(observation)
        if ordering.duplicate_sequence:
            return decide("rejected", None, "duplicate_source_sequence")
        if ordering.out_of_order:
            return decide("rejected", None, "out_of_order_source_sequence")
        if ordering.clock_regression:
            return decide("rejected", None, "source_clock_regression")
        if ordering.sequence_gap is not None:
            return decide("rejected", None, "source_sequence_gap")

        if sensor_kind == self.TEE_KIND:
            return self._evaluate_tee(observation, context, transition, decide)
        return self._evaluate_cup(observation, context, sensor_kind, transition, decide)

    def _evaluate_tee(
        self,
        observation: PhysicalSensorObservation,
        context: PhysicalEvidenceContext,
        transition: str,
        decide: DecisionFactory,
    ) -> PhysicalEvidenceDecision:
        if transition == "vacant":
            return decide(
                "observed",
                "tee.vacant",
                "tee_vacancy_is_not_authoritative_cancellation",
            )
        if transition != "occupied":
            return decide("rejected", None, "unsupported_tee_transition")
        if observation.ball_id is None:
            return decide("rejected", "tee.presentation_candidate", "ball_id_is_required")
        if observation.ball_id not in context.assigned_ball_ids:
            return decide(
                "rejected",
                "tee.presentation_candidate",
                "ball_is_not_assigned_to_session",
            )
        if context.active_ball_id == observation.ball_id:
            return decide(
                "observed",
                "tee.presentation_candidate",
                "ball_is_already_active",
            )
        if context.active_ball_id is not None:
            return decide(
                "rejected",
                "tee.presentation_candidate",
                "hole_is_busy_with_another_ball",
            )

        semantic_type = "tee.presented"
        evidence = self._common_evidence(
            observation,
            context,
            event_id=self._evidence_id(semantic_type, observation.event_id),
            semantic_type=semantic_type,
            ball_id=observation.ball_id,
            player_id=None,
            raw_evidence_refs=(observation.event_id,),
            metadata={
                "sensor_id": observation.sensor_id,
                "sensor_kind": self.TEE_KIND,
                "transition": transition,
                "debounce_version": observation.debounce_version,
            },
        )
        return decide(
            "accepted",
            "tee.presentation_candidate",
            "assigned_ball_and_debounced_tee_presence",
            semantic_type=semantic_type,
            evidence_event=evidence,
        )

    def _evaluate_cup(
        self,
        observation: PhysicalSensorObservation,
        context: PhysicalEvidenceContext,
        sensor_kind: str,
        transition: str,
        decide: DecisionFactory,
    ) -> PhysicalEvidenceDecision:
        if transition == "vacant":
            self._cup_entry = None
            return decide("observed", "cup.vacant", "cup_candidate_cleared")
        if context.active_ball_id is None:
            return decide("rejected", "cup.entry_candidate", "no_active_ball_context")
        if context.active_player_state != "playing":
            return decide(
                "rejected",
                "cup.entry_candidate",
                "active_ball_is_not_playing",
            )
        if observation.ball_id is not None and observation.ball_id != context.active_ball_id:
            return decide(
                "rejected",
                "cup.entry_candidate",
                "observation_is_not_for_active_ball",
            )

        if sensor_kind == self.CUP_ENTRY_KIND:
            if transition != "entered":
                return decide("rejected", None, "unsupported_cup_entry_transition")
            self._cup_entry = _CupEntryCandidate(
                observation=observation,
                ball_id=context.active_ball_id,
                hole_id=context.hole_id,
            )
            return decide(
                "pending",
                "cup.entry_candidate",
                "cup_presence_confirmation_required",
            )

        if transition != "occupied":
            return decide("rejected", None, "unsupported_cup_presence_transition")
        candidate = self._cup_entry
        if candidate is None:
            return decide(
                "pending",
                "cup.entry_candidate",
                "cup_entry_edge_required",
            )
        if candidate.ball_id != context.active_ball_id:
            self._cup_entry = None
            return decide(
                "rejected",
                "cup.entry_candidate",
                "active_ball_changed_during_cup_sequence",
            )
        if candidate.hole_id != context.hole_id:
            self._cup_entry = None
            return decide(
                "rejected",
                "cup.entry_candidate",
                "active_hole_changed_during_cup_sequence",
            )
        if (
            candidate.observation.source_device_id == observation.source_device_id
            and candidate.observation.source_boot_id != observation.source_boot_id
        ):
            self._cup_entry = None
            return decide(
                "rejected",
                "cup.entry_candidate",
                "source_rebooted_during_cup_sequence",
            )
        elapsed_ns = observation.edge_received_ns - candidate.observation.edge_received_ns
        if elapsed_ns < 0:
            self._cup_entry = None
            return decide(
                "rejected",
                "cup.entry_candidate",
                "cup_observation_receive_time_regressed",
            )
        if elapsed_ns > self.CUP_CONFIRM_WINDOW_NS:
            self._cup_entry = None
            return decide(
                "rejected",
                "cup.entry_candidate",
                "cup_confirmation_window_expired",
            )

        semantic_type = "cup.confirmed"
        entry = candidate.observation
        evidence = self._common_evidence(
            observation,
            context,
            event_id=self._evidence_id(
                semantic_type,
                entry.event_id,
                observation.event_id,
            ),
            semantic_type=semantic_type,
            ball_id=context.active_ball_id,
            player_id=context.active_player_id,
            raw_evidence_refs=(entry.event_id, observation.event_id),
            metadata={
                "entry_sensor_id": entry.sensor_id,
                "presence_sensor_id": observation.sensor_id,
                "entry_debounce_version": entry.debounce_version,
                "presence_debounce_version": observation.debounce_version,
                "confirmation_elapsed_ms": elapsed_ns // 1_000_000,
            },
        )
        self._cup_entry = None
        return decide(
            "accepted",
            "cup.entry_candidate",
            "entry_then_occupied_with_active_play_context",
            semantic_type=semantic_type,
            evidence_event=evidence,
        )
