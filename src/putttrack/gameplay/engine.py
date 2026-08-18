from __future__ import annotations

from dataclasses import asdict
from typing import Iterable

from .events import EventType, GameplayEvent, GameplayNotice
from .models import (
    HoleRuntime,
    PlayerHoleStatus,
    SessionState,
    SessionStatus,
)


class GameplayError(RuntimeError):
    """Raised when a confirmed gameplay event violates the game-state contract."""


class GameplayEngine:
    """Deterministic, idempotent gameplay state machine.

    Sensor fusion is intentionally outside this class. Inputs to this engine are
    already-confirmed evidence events (stroke, feature, cup, etc.). This keeps
    the game rules independent from Bluetooth CS, UWB, cameras or any future
    sensing implementation.
    """

    def __init__(self, state: SessionState):
        self.state = state

    def process(self, event: GameplayEvent) -> list[GameplayNotice]:
        if event.event_id in self.state.seen_event_ids:
            return [
                GameplayNotice(
                    kind="duplicate_ignored",
                    text="Duplicate evidence ignored.",
                    metadata={"event_id": event.event_id},
                )
            ]

        if self.state.status == SessionStatus.COMPLETE:
            raise GameplayError("session is already complete")

        if event.hole_id != self.state.current_hole.hole_id:
            raise GameplayError(
                f"event is for {event.hole_id}; current hole is "
                f"{self.state.current_hole.hole_id}"
            )

        notices = self._dispatch(event)
        self.state.seen_event_ids.add(event.event_id)
        return notices

    def process_many(self, events: Iterable[GameplayEvent]) -> list[GameplayNotice]:
        notices: list[GameplayNotice] = []
        for event in events:
            notices.extend(self.process(event))
        return notices

    def _dispatch(self, event: GameplayEvent) -> list[GameplayNotice]:
        if event.event_type == EventType.TEE_PRESENTED:
            return self._tee_presented(event)
        if event.event_type == EventType.TEE_CANCELLED:
            return self._tee_cancelled(event)
        if event.event_type == EventType.STROKE_CONFIRMED:
            return self._stroke_confirmed(event)
        if event.event_type == EventType.FEATURE_CONFIRMED:
            return self._feature_confirmed(event)
        if event.event_type == EventType.CUP_CONFIRMED:
            return self._cup_confirmed(event)
        if event.event_type == EventType.PICKUP_DETECTED:
            return self._pickup_detected(event)
        if event.event_type == EventType.MANUAL_ADJUSTMENT:
            return self._manual_adjustment(event)
        raise GameplayError(f"unsupported event type: {event.event_type}")

    def _player_from_ball(self, ball_id: str | None) -> str:
        if not ball_id:
            raise GameplayError("ball_id is required for this event")
        try:
            return self.state.ball_to_player[ball_id]
        except KeyError as exc:
            raise GameplayError(f"ball {ball_id!r} is not assigned to this session") from exc

    def _active_player_from_event(self, event: GameplayEvent) -> tuple[str, HoleRuntime]:
        player_id = self._player_from_ball(event.ball_id)
        runtime = self.state.current_runtime
        if runtime.active_player_id != player_id:
            if runtime.active_player_id is None:
                raise GameplayError("no player is currently armed on this hole")
            raise GameplayError(
                f"{player_id} is not active; {runtime.active_player_id} is active"
            )
        return player_id, runtime

    def _tee_presented(self, event: GameplayEvent) -> list[GameplayNotice]:
        player_id = self._player_from_ball(event.ball_id)
        runtime = self.state.current_runtime
        player_state = runtime.players[player_id]

        if player_state.status == PlayerHoleStatus.COMPLETE:
            raise GameplayError("player already completed this hole")
        if runtime.active_player_id not in (None, player_id):
            active = self.state.players[runtime.active_player_id].display_name
            raise GameplayError(f"hole is busy with {active}")

        if runtime.active_player_id == player_id:
            return [
                GameplayNotice(
                    kind="already_armed",
                    player_id=player_id,
                    text=f"{self.state.players[player_id].display_name} is already ready.",
                )
            ]

        runtime.active_player_id = player_id
        player_state.status = PlayerHoleStatus.ARMED
        return [
            GameplayNotice(
                kind="player_ready",
                player_id=player_id,
                text=f"{self.state.players[player_id].display_name} — READY",
                metadata={"cue": "green"},
            )
        ]

    def _tee_cancelled(self, event: GameplayEvent) -> list[GameplayNotice]:
        player_id, runtime = self._active_player_from_event(event)
        player_state = runtime.players[player_id]
        if player_state.status != PlayerHoleStatus.ARMED or player_state.strokes != 0:
            raise GameplayError("tee arming can only be cancelled before the first stroke")

        player_state.status = PlayerHoleStatus.NOT_STARTED
        runtime.active_player_id = None
        return [
            GameplayNotice(
                kind="arming_cancelled",
                player_id=player_id,
                text="Ball removed. Ready for another player.",
            )
        ]

    def _stroke_confirmed(self, event: GameplayEvent) -> list[GameplayNotice]:
        player_id, runtime = self._active_player_from_event(event)
        player_state = runtime.players[player_id]
        if player_state.status not in (PlayerHoleStatus.ARMED, PlayerHoleStatus.PLAYING):
            raise GameplayError("player is not in a stroke-eligible state")

        player_state.strokes += 1
        self.state.stats[player_id].total_strokes += 1
        if player_state.started_at_ms is None:
            player_state.started_at_ms = event.timestamp_ms
        player_state.status = PlayerHoleStatus.PLAYING
        self.state.status = SessionStatus.ACTIVE

        return [
            GameplayNotice(
                kind="stroke",
                player_id=player_id,
                text=f"Stroke {player_state.strokes}",
                metadata={"strokes": player_state.strokes},
            )
        ]

    def _feature_confirmed(self, event: GameplayEvent) -> list[GameplayNotice]:
        player_id, runtime = self._active_player_from_event(event)
        player_state = runtime.players[player_id]
        if player_state.status != PlayerHoleStatus.PLAYING:
            raise GameplayError("feature events require active play")
        if not event.feature_id:
            raise GameplayError("feature_id is required")

        try:
            rule = runtime.hole.features[event.feature_id]
        except KeyError as exc:
            raise GameplayError(f"unknown feature {event.feature_id!r}") from exc

        count = player_state.feature_counts.get(rule.feature_id, 0)
        if count >= rule.max_triggers_per_player:
            return [
                GameplayNotice(
                    kind="feature_limit_ignored",
                    player_id=player_id,
                    text=f"{rule.label} already counted.",
                    metadata={"feature_id": rule.feature_id},
                )
            ]

        delta = rule.points_delta
        player_state.feature_counts[rule.feature_id] = count + 1
        player_state.points += delta
        stats = self.state.stats[player_id]
        stats.total_points += delta
        if delta >= 0:
            player_state.bonus_points += delta
            stats.bonus_points += delta
        else:
            penalty = abs(delta)
            player_state.hazard_penalties += penalty
            stats.hazard_penalties += penalty

        return [
            GameplayNotice(
                kind=rule.kind.value,
                player_id=player_id,
                text=f"{rule.label} {delta:+d}",
                points_delta=delta,
                metadata={"feature_id": rule.feature_id},
            )
        ]

    def _pickup_detected(self, event: GameplayEvent) -> list[GameplayNotice]:
        player_id, _ = self._active_player_from_event(event)
        return [
            GameplayNotice(
                kind="pickup_warning",
                player_id=player_id,
                text="Ball movement looks like a pickup. Replace the ball to continue.",
                metadata={"score_changed": False},
            )
        ]

    def _cup_confirmed(self, event: GameplayEvent) -> list[GameplayNotice]:
        player_id, runtime = self._active_player_from_event(event)
        player_state = runtime.players[player_id]
        if player_state.status != PlayerHoleStatus.PLAYING:
            raise GameplayError("cup completion requires active play")
        if player_state.strokes < 1:
            raise GameplayError("cup completion requires at least one confirmed stroke")

        base_points = runtime.hole.completion_points(player_state.strokes)
        player_state.points += base_points
        stats = self.state.stats[player_id]
        stats.total_points += base_points
        stats.holes_completed += 1
        player_state.status = PlayerHoleStatus.COMPLETE
        player_state.completed_at_ms = event.timestamp_ms
        if player_state.started_at_ms is not None:
            stats.active_play_ms += max(0, event.timestamp_ms - player_state.started_at_ms)
        runtime.active_player_id = None

        notices = [
            GameplayNotice(
                kind="player_hole_complete",
                player_id=player_id,
                text=(
                    f"{self.state.players[player_id].display_name}: "
                    f"{player_state.strokes} strokes, {player_state.points} points"
                ),
                points_delta=base_points,
                metadata={
                    "strokes": player_state.strokes,
                    "hole_points": player_state.points,
                    "completion_points": base_points,
                },
            )
        ]

        if runtime.complete:
            notices.extend(self._advance_hole(event.timestamp_ms))
        return notices

    def _manual_adjustment(self, event: GameplayEvent) -> list[GameplayNotice]:
        player_id = self._player_from_ball(event.ball_id)
        if event.points_delta is None:
            raise GameplayError("operator adjustment requires points_delta")
        reason = str(event.metadata.get("reason", "operator adjustment")).strip()
        if not reason:
            raise GameplayError("operator adjustment requires a reason")

        delta = event.points_delta
        self.state.current_runtime.players[player_id].points += delta
        self.state.stats[player_id].total_points += delta
        return [
            GameplayNotice(
                kind="operator_adjustment",
                player_id=player_id,
                text=f"Score adjusted {delta:+d}: {reason}",
                points_delta=delta,
                metadata={"reason": reason, "source": event.source},
            )
        ]

    def _advance_hole(self, timestamp_ms: int) -> list[GameplayNotice]:
        completed = self.state.current_hole
        if self.state.current_hole_index == len(self.state.course) - 1:
            self.state.status = SessionStatus.COMPLETE
            return [
                GameplayNotice(
                    kind="session_complete",
                    text="Round complete.",
                    metadata={
                        "completed_hole": completed.hole_id,
                        "timestamp_ms": timestamp_ms,
                    },
                )
            ]

        self.state.current_hole_index += 1
        next_hole = self.state.current_hole
        return [
            GameplayNotice(
                kind="hole_complete",
                text=f"Hole {completed.number} complete. Next: Hole {next_hole.number}.",
                metadata={
                    "completed_hole": completed.hole_id,
                    "next_hole": next_hole.hole_id,
                },
            )
        ]

    def ranking(self) -> list[dict[str, object]]:
        def sort_key(player_id: str) -> tuple[int, int, int, int, int, str]:
            stats = self.state.stats[player_id]
            return (
                -stats.total_points,
                -stats.bonus_points,
                stats.total_strokes,
                stats.hazard_penalties,
                stats.active_play_ms,
                player_id,
            )

        ranking: list[dict[str, object]] = []
        for rank, player_id in enumerate(sorted(self.state.players, key=sort_key), start=1):
            player = self.state.players[player_id]
            stats = self.state.stats[player_id]
            ranking.append(
                {
                    "rank": rank,
                    "player_id": player_id,
                    "display_name": player.display_name,
                    "ball_id": player.ball_id,
                    "points": stats.total_points,
                    "bonus_points": stats.bonus_points,
                    "strokes": stats.total_strokes,
                    "hazard_penalties": stats.hazard_penalties,
                    "holes_completed": stats.holes_completed,
                    "active_play_ms": stats.active_play_ms,
                }
            )
        return ranking

    def presentation(self) -> dict[str, object]:
        hole = self.state.current_hole
        runtime = self.state.current_runtime
        active_player = (
            self.state.players[runtime.active_player_id]
            if runtime.active_player_id is not None
            else None
        )
        return {
            "session_id": self.state.session_id,
            "session_status": self.state.status.value,
            "hole": {
                "hole_id": hole.hole_id,
                "number": hole.number,
                "title": hole.title,
                "instructions": hole.instructions,
            },
            "active_player": (
                {
                    "player_id": active_player.player_id,
                    "display_name": active_player.display_name,
                    "ball_id": active_player.ball_id,
                }
                if active_player
                else None
            ),
            "player_hole_state": {
                player_id: {
                    "status": state.status.value,
                    "strokes": state.strokes,
                    "points": state.points,
                }
                for player_id, state in runtime.players.items()
            },
            "ranking": self.ranking(),
        }

    def evidence_snapshot(self) -> dict[str, object]:
        """Serializable state intended for diagnostics / round evidence."""
        return {
            "presentation": self.presentation(),
            "stats": {
                player_id: asdict(stats)
                for player_id, stats in self.state.stats.items()
            },
            "seen_event_count": len(self.state.seen_event_ids),
        }
