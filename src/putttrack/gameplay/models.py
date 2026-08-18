from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SessionStatus(str, Enum):
    READY = "ready"
    ACTIVE = "active"
    COMPLETE = "complete"
    PAUSED = "paused"


class PlayerHoleStatus(str, Enum):
    NOT_STARTED = "not_started"
    ARMED = "armed"
    PLAYING = "playing"
    COMPLETE = "complete"


class FeatureKind(str, Enum):
    BONUS = "bonus"
    HAZARD = "hazard"
    ROUTE = "route"
    COMBO = "combo"


@dataclass(frozen=True)
class Player:
    player_id: str
    display_name: str
    ball_id: str
    team_id: str | None = None


@dataclass(frozen=True)
class FeatureRule:
    feature_id: str
    label: str
    points_delta: int
    kind: FeatureKind = FeatureKind.BONUS
    max_triggers_per_player: int = 1

    def __post_init__(self) -> None:
        if self.max_triggers_per_player < 1:
            raise ValueError("max_triggers_per_player must be >= 1")


@dataclass(frozen=True)
class HoleDefinition:
    hole_id: str
    number: int
    title: str
    score_curve: dict[int, int]
    features: dict[str, FeatureRule] = field(default_factory=dict)
    instructions: str = ""

    def completion_points(self, strokes: int) -> int:
        if strokes < 1:
            raise ValueError("strokes must be >= 1")
        if not self.score_curve:
            return 0
        if strokes in self.score_curve:
            return self.score_curve[strokes]
        largest = max(self.score_curve)
        if strokes > largest:
            return self.score_curve[largest]
        # Supports sparse curves by choosing the first configured threshold above
        # the stroke count.
        for threshold in sorted(self.score_curve):
            if strokes <= threshold:
                return self.score_curve[threshold]
        return self.score_curve[largest]


@dataclass
class PlayerStats:
    player_id: str
    total_points: int = 0
    total_strokes: int = 0
    bonus_points: int = 0
    hazard_penalties: int = 0
    active_play_ms: int = 0
    holes_completed: int = 0


@dataclass
class PlayerHoleState:
    player_id: str
    status: PlayerHoleStatus = PlayerHoleStatus.NOT_STARTED
    strokes: int = 0
    points: int = 0
    bonus_points: int = 0
    hazard_penalties: int = 0
    feature_counts: dict[str, int] = field(default_factory=dict)
    started_at_ms: int | None = None
    completed_at_ms: int | None = None


@dataclass
class HoleRuntime:
    hole: HoleDefinition
    players: dict[str, PlayerHoleState]
    active_player_id: str | None = None

    @property
    def complete(self) -> bool:
        return all(
            player.status == PlayerHoleStatus.COMPLETE
            for player in self.players.values()
        )


@dataclass
class SessionState:
    session_id: str
    players: dict[str, Player]
    course: list[HoleDefinition]
    status: SessionStatus = SessionStatus.READY
    current_hole_index: int = 0
    stats: dict[str, PlayerStats] = field(default_factory=dict)
    holes: dict[str, HoleRuntime] = field(default_factory=dict)
    seen_event_ids: set[str] = field(default_factory=set)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.players:
            raise ValueError("session must have at least one player")
        if not self.course:
            raise ValueError("session must have at least one hole")
        if len({p.ball_id for p in self.players.values()}) != len(self.players):
            raise ValueError("each player must have a unique ball_id")
        if not self.stats:
            self.stats = {
                player_id: PlayerStats(player_id=player_id)
                for player_id in self.players
            }
        if not self.holes:
            self.holes = {
                hole.hole_id: HoleRuntime(
                    hole=hole,
                    players={
                        player_id: PlayerHoleState(player_id=player_id)
                        for player_id in self.players
                    },
                )
                for hole in self.course
            }

    @property
    def current_hole(self) -> HoleDefinition:
        return self.course[self.current_hole_index]

    @property
    def current_runtime(self) -> HoleRuntime:
        return self.holes[self.current_hole.hole_id]

    @property
    def ball_to_player(self) -> dict[str, str]:
        return {player.ball_id: player_id for player_id, player in self.players.items()}
