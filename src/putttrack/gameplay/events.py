from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EventType(str, Enum):
    TEE_PRESENTED = "tee.presented"
    TEE_CANCELLED = "tee.cancelled"
    STROKE_CONFIRMED = "stroke.confirmed"
    FEATURE_CONFIRMED = "feature.confirmed"
    CUP_CONFIRMED = "cup.confirmed"
    PICKUP_DETECTED = "pickup.detected"
    MANUAL_ADJUSTMENT = "operator.adjustment"


@dataclass(frozen=True)
class GameplayEvent:
    event_id: str
    event_type: EventType
    timestamp_ms: int
    hole_id: str
    ball_id: str | None = None
    feature_id: str | None = None
    points_delta: int | None = None
    source: str = "unknown"
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.event_id:
            raise ValueError("event_id is required")
        if self.timestamp_ms < 0:
            raise ValueError("timestamp_ms must be >= 0")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")


@dataclass(frozen=True)
class GameplayNotice:
    kind: str
    text: str
    player_id: str | None = None
    points_delta: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
