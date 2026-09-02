from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from putttrack.contracts import MotionObservation, record_to_dict
from putttrack.evidence import (
    MotionCandidateDecision,
    MotionEvidenceContext,
    NoCsMotionCandidatePolicy,
)
from putttrack.gameplay import EventType, GameplayEngine, GameplayError, GameplayEvent
from putttrack.gameplay.models import PlayerHoleStatus, SessionState


@dataclass(frozen=True)
class PresentationEvent:
    sequence: int
    kind: str
    text: str
    timestamp_ms: int
    player_id: str | None = None
    points_delta: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PresentationBroker:
    """Small in-process presentation bus for the local hole-screen prototype."""

    def __init__(self, *, max_events: int = 256) -> None:
        self._condition = threading.Condition()
        self._events: list[PresentationEvent] = []
        self._next_sequence = 1
        self._max_events = max_events

    def publish(
        self,
        kind: str,
        text: str,
        *,
        player_id: str | None = None,
        points_delta: int = 0,
        metadata: dict[str, Any] | None = None,
        timestamp_ms: int | None = None,
    ) -> PresentationEvent:
        with self._condition:
            event = PresentationEvent(
                sequence=self._next_sequence,
                kind=kind,
                text=text,
                timestamp_ms=(
                    timestamp_ms if timestamp_ms is not None else int(time.time() * 1000)
                ),
                player_id=player_id,
                points_delta=points_delta,
                metadata=dict(metadata or {}),
            )
            self._next_sequence += 1
            self._events.append(event)
            if len(self._events) > self._max_events:
                self._events = self._events[-self._max_events :]
            self._condition.notify_all()
            return event

    def after(self, sequence: int, *, timeout: float = 0.0) -> list[PresentationEvent]:
        with self._condition:
            found = [event for event in self._events if event.sequence > sequence]
            if not found and timeout > 0:
                self._condition.wait(timeout)
                found = [event for event in self._events if event.sequence > sequence]
            return found


class RoundAuditLog:
    """Append-only operational audit for the one-hole vertical slice.

    Canonical RF/evidence observations continue to use the Evidence Foundation
    JSONL contracts. This audit is a separate local operational trail of the
    Gameplay transition, notices and resulting authoritative snapshot.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def append(self, payload: dict[str, Any]) -> None:
        line = (
            json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            + "\n"
        ).encode("utf-8")
        with self._lock:
            fd = os.open(self.path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o640)
            try:
                written = os.write(fd, line)
                if written != len(line):
                    raise OSError("short audit append")
                os.fsync(fd)
            finally:
                os.close(fd)


class LocalRoundRuntime:
    """Glue between semantic Gameplay authority and a local presentation surface."""

    def __init__(
        self,
        state: SessionState,
        *,
        audit_path: str | Path | None = None,
        broker: PresentationBroker | None = None,
        motion_policy: NoCsMotionCandidatePolicy | None = None,
    ) -> None:
        self.engine = GameplayEngine(state)
        self.broker = broker or PresentationBroker()
        self.audit = RoundAuditLog(audit_path) if audit_path else None
        self.motion_policy = motion_policy or NoCsMotionCandidatePolicy()
        self._motion_decisions: dict[str, MotionCandidateDecision] = {}
        self._lock = threading.RLock()

    @property
    def state(self) -> SessionState:
        return self.engine.state

    def _ball_label(self, ball_id: str) -> str:
        labels = self.state.metadata.get("ball_labels", {})
        if isinstance(labels, dict):
            return str(labels.get(ball_id, ball_id))
        return ball_id

    def presentation(self) -> dict[str, Any]:
        with self._lock:
            base = self.engine.presentation()
            runtime = self.state.current_runtime
            cue = {"state": "AVAILABLE", "tone": "neutral", "icon": "○"}
            if runtime.active_player_id is not None:
                player_state = runtime.players[runtime.active_player_id]
                if player_state.status == PlayerHoleStatus.ARMED:
                    cue = {"state": "READY", "tone": "green", "icon": "✓"}
                elif player_state.status == PlayerHoleStatus.PLAYING:
                    cue = {"state": "PLAYING", "tone": "blue", "icon": "●"}
            base["cue"] = cue
            base["ball_labels"] = dict(self.state.metadata.get("ball_labels", {}))
            return base

    def _append_audit(self, event: GameplayEvent, notices: list[Any]) -> None:
        if self.audit is None:
            return
        self.audit.append(
            {
                "kind": "gameplay_transition",
                "event": {
                    "event_id": event.event_id,
                    "event_type": event.event_type.value,
                    "timestamp_ms": event.timestamp_ms,
                    "hole_id": event.hole_id,
                    "ball_id": event.ball_id,
                    "feature_id": event.feature_id,
                    "points_delta": event.points_delta,
                    "source": event.source,
                    "confidence": event.confidence,
                    "metadata": event.metadata,
                },
                "notices": [
                    {
                        "kind": notice.kind,
                        "text": notice.text,
                        "player_id": notice.player_id,
                        "points_delta": notice.points_delta,
                        "metadata": notice.metadata,
                    }
                    for notice in notices
                ],
                "snapshot": self.engine.evidence_snapshot(),
            }
        )

    def process_gameplay(self, event: GameplayEvent) -> list[Any]:
        with self._lock:
            notices = self.engine.process(event)
            self._append_audit(event, notices)
            for notice in notices:
                self.broker.publish(
                    notice.kind,
                    notice.text,
                    player_id=notice.player_id,
                    points_delta=notice.points_delta,
                    metadata=notice.metadata,
                    timestamp_ms=event.timestamp_ms,
                )
            return notices

    def process_evidence(self, evidence: Any) -> list[Any]:
        """Use the canonical sensor-independent Evidence Foundation adapter."""
        from putttrack.evidence import EvidenceToGameplayAdapter

        return self.process_gameplay(EvidenceToGameplayAdapter().from_evidence(evidence))

    def process_motion_observation(
        self,
        observation: MotionObservation,
    ) -> MotionCandidateDecision:
        """Route generic motion without allowing it to mutate score directly."""

        with self._lock:
            previous = self._motion_decisions.get(observation.event_id)
            if previous is not None:
                return previous

            runtime = self.state.current_runtime
            active_player_id = runtime.active_player_id
            active_ball_id = (
                self.state.players[active_player_id].ball_id
                if active_player_id is not None
                else None
            )
            active_state = (
                runtime.players[active_player_id].status.value
                if active_player_id is not None
                else None
            )
            decision = self.motion_policy.evaluate(
                observation,
                MotionEvidenceContext(
                    session_id=self.state.session_id,
                    hole_id=self.state.current_hole.hole_id,
                    assigned_ball_ids=tuple(sorted(self.state.ball_to_player)),
                    active_ball_id=active_ball_id,
                    active_player_id=active_player_id,
                    active_player_state=active_state,
                ),
            )
            self._motion_decisions[observation.event_id] = decision

            if self.audit is not None:
                self.audit.append(
                    {
                        "kind": "motion_candidate_decision",
                        "observation": record_to_dict(observation),
                        "decision": decision.to_dict(),
                        "snapshot": self.engine.evidence_snapshot(),
                    }
                )

            if decision.status == "pending":
                self.broker.publish(
                    "evidence_pending",
                    "Motion candidate is waiting for independent evidence.",
                    player_id=active_player_id,
                    metadata={
                        **decision.to_dict(),
                        "ball_id": observation.ball_id,
                        "confidence": observation.confidence,
                    },
                    timestamp_ms=observation.edge_received_ns // 1_000_000,
                )
            elif decision.status == "rejected":
                self.broker.publish(
                    "motion_rejected",
                    "Motion observation was not eligible for this active hole.",
                    metadata={
                        **decision.to_dict(),
                        "ball_id": observation.ball_id,
                    },
                    timestamp_ms=observation.edge_received_ns // 1_000_000,
                )
            return decision

    def present_ball(
        self,
        ball_id: str,
        *,
        event_id: str,
        timestamp_ms: int,
    ) -> list[Any]:
        """Prototype DETECTED/CHECKING -> authoritative READY transition.

        The amber presentation cue is non-authoritative. ``tee.presented`` is
        still the only Gameplay mutation, so a future physical tee/fusion layer
        can replace this simulator path without changing Gameplay Engine logic.
        """
        with self._lock:
            player_id = self.state.ball_to_player.get(ball_id)
            if player_id is None:
                self.broker.publish(
                    "wrong_ball",
                    f"Ball {ball_id} is not assigned to this group.",
                    metadata={"cue": "orange", "ball_id": ball_id},
                    timestamp_ms=timestamp_ms,
                )
                raise GameplayError(
                    f"ball {ball_id!r} is not assigned to this session"
                )
            player = self.state.players[player_id]
            self.broker.publish(
                "ball_detected",
                f"{player.display_name} detected — checking",
                player_id=player_id,
                metadata={
                    "cue": "amber",
                    "ball_id": ball_id,
                    "ball_label": self._ball_label(ball_id),
                },
                timestamp_ms=timestamp_ms,
            )

        return self.process_gameplay(
            GameplayEvent(
                event_id=event_id,
                event_type=EventType.TEE_PRESENTED,
                timestamp_ms=timestamp_ms,
                hole_id=self.state.current_hole.hole_id,
                ball_id=ball_id,
                source="simulated-tee",
            )
        )
