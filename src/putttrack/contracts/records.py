"""Canonical typed evidence records used across PuttTrack boundaries."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, ClassVar, Mapping, Sequence

from .versioning import CURRENT_SCHEMA_VERSION, validate_schema_version


JsonScalar = str | int | float | bool | None
JsonValue = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]


def _require_non_empty(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")


def _require_non_negative(name: str, value: int) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")


def _finite_or_none(name: str, value: float | None) -> None:
    if value is not None and (not isinstance(value, (int, float)) or not math.isfinite(value)):
        raise ValueError(f"{name} must be finite or None")


def _tuple_of_floats(
    name: str,
    value: Sequence[float] | None,
    *,
    length: int | None = None,
) -> tuple[float, ...] | None:
    if value is None:
        return None
    converted = tuple(float(item) for item in value)
    if length is not None and len(converted) != length:
        raise ValueError(f"{name} must contain {length} values")
    if not all(math.isfinite(item) for item in converted):
        raise ValueError(f"{name} must contain finite values")
    return converted


def _tuple_of_strings(name: str, value: Sequence[str]) -> tuple[str, ...]:
    converted = tuple(value)
    if any(not isinstance(item, str) or not item for item in converted):
        raise ValueError(f"{name} must contain non-empty strings")
    return converted


def _dict_copy(value: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(value or {})


@dataclass(frozen=True, kw_only=True)
class BaseRecord:
    """Common envelope for observations, derived tracks and semantic events."""

    RECORD_TYPE: ClassVar[str] = "base"

    schema_version: str = CURRENT_SCHEMA_VERSION
    event_id: str
    event_type: str
    source_device_id: str
    source_boot_id: str
    sequence: int
    source_monotonic_ns: int
    edge_received_ns: int
    trace_id: str
    correlation_id: str | None = None
    venue_id: str | None = None
    zone_id: str | None = None
    hole_id: str | None = None
    ball_id: str | None = None
    firmware_version: str | None = None
    config_version: str | None = None
    calibration_version: str | None = None
    model_version: str | None = None
    raw_evidence_refs: tuple[str, ...] = ()
    wall_time: str | None = None
    extensions: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_schema_version(self.schema_version)
        for name in (
            "event_id",
            "event_type",
            "source_device_id",
            "source_boot_id",
            "trace_id",
        ):
            _require_non_empty(name, getattr(self, name))
        for name in ("sequence", "source_monotonic_ns", "edge_received_ns"):
            _require_non_negative(name, getattr(self, name))
        for name in (
            "correlation_id",
            "venue_id",
            "zone_id",
            "hole_id",
            "ball_id",
            "firmware_version",
            "config_version",
            "calibration_version",
            "model_version",
        ):
            value = getattr(self, name)
            if value is not None:
                _require_non_empty(name, value)
        refs = _tuple_of_strings("raw_evidence_refs", self.raw_evidence_refs)
        object.__setattr__(self, "raw_evidence_refs", refs)
        object.__setattr__(self, "extensions", _dict_copy(self.extensions))
        if self.wall_time is not None:
            _require_non_empty("wall_time", self.wall_time)
            try:
                datetime.fromisoformat(self.wall_time.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("wall_time must be ISO-8601 when supplied") from exc

    @property
    def record_type(self) -> str:
        return self.RECORD_TYPE


@dataclass(frozen=True, kw_only=True)
class RangeObservation(BaseRecord):
    RECORD_TYPE: ClassVar[str] = "range_observation"

    anchor_id: str
    rf_cell_id: str | None = None
    procedure_id: str | None = None
    antenna_path: int | None = None
    distance_ifft_m: float | None = None
    distance_phase_m: float | None = None
    distance_rtt_m: float | None = None
    rssi_dbm: float | None = None
    quality: dict[str, Any] = field(default_factory=dict)
    anchor_position_m: tuple[float, float, float] | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_non_empty("anchor_id", self.anchor_id)
        for name in ("rf_cell_id", "procedure_id"):
            value = getattr(self, name)
            if value is not None:
                _require_non_empty(name, value)
        if self.antenna_path is not None:
            _require_non_negative("antenna_path", self.antenna_path)
        for name in (
            "distance_ifft_m",
            "distance_phase_m",
            "distance_rtt_m",
            "rssi_dbm",
        ):
            _finite_or_none(name, getattr(self, name))
        if all(
            value is None
            for value in (
                self.distance_ifft_m,
                self.distance_phase_m,
                self.distance_rtt_m,
            )
        ):
            raise ValueError("RangeObservation requires at least one distance estimate")
        object.__setattr__(self, "quality", _dict_copy(self.quality))
        object.__setattr__(
            self,
            "anchor_position_m",
            _tuple_of_floats("anchor_position_m", self.anchor_position_m, length=3),
        )


@dataclass(frozen=True, kw_only=True)
class MotionObservation(BaseRecord):
    RECORD_TYPE: ClassVar[str] = "motion_observation"

    motion_state: str
    confidence: float
    accel_mps2: tuple[float, float, float] | None = None
    gyro_rads: tuple[float, float, float] | None = None
    raw_window_ref: str | None = None
    battery: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_non_empty("motion_state", self.motion_state)
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        object.__setattr__(self, "confidence", float(self.confidence))
        object.__setattr__(
            self,
            "accel_mps2",
            _tuple_of_floats("accel_mps2", self.accel_mps2, length=3),
        )
        object.__setattr__(
            self,
            "gyro_rads",
            _tuple_of_floats("gyro_rads", self.gyro_rads, length=3),
        )
        if self.raw_window_ref is not None:
            _require_non_empty("raw_window_ref", self.raw_window_ref)
        object.__setattr__(self, "battery", _dict_copy(self.battery))


@dataclass(frozen=True, kw_only=True)
class PhysicalSensorObservation(BaseRecord):
    RECORD_TYPE: ClassVar[str] = "physical_sensor_observation"

    sensor_id: str
    sensor_kind: str
    transition: str
    value: JsonValue = None
    health: str = "ok"
    debounce_version: str | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        for name in ("sensor_id", "sensor_kind", "transition", "health"):
            _require_non_empty(name, getattr(self, name))
        if self.debounce_version is not None:
            _require_non_empty("debounce_version", self.debounce_version)


@dataclass(frozen=True, kw_only=True)
class RadioReceptionObservation(BaseRecord):
    """One receiver's report of one connectionless Ball radio emission.

    ``source_device_id``/``source_boot_id``/``sequence`` identify and order the
    receiver. The Ball emission has a separate identity and sequence so several
    receivers can report the same packet without pretending to be the Ball.
    """

    RECORD_TYPE: ClassVar[str] = "radio_reception_observation"

    ball_device_id: str
    ball_boot_id: str
    ball_radio_sequence: int
    payload_digest: str
    rssi_dbm: int
    tx_power_dbm: int
    channel_index: int | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.ball_id is None:
            raise ValueError("ball_id is required")
        _require_non_empty("ball_device_id", self.ball_device_id)
        _require_non_empty("ball_boot_id", self.ball_boot_id)
        _require_non_negative("ball_radio_sequence", self.ball_radio_sequence)
        if (
            not isinstance(self.payload_digest, str)
            or len(self.payload_digest) != 64
            or any(character not in "0123456789abcdef" for character in self.payload_digest)
        ):
            raise ValueError("payload_digest must be a lowercase SHA-256 hexadecimal digest")
        for name in ("rssi_dbm", "tx_power_dbm"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or not -127 <= value <= 20:
                raise ValueError(f"{name} must be an integer between -127 and 20 dBm")
        if self.channel_index is not None and (
            not isinstance(self.channel_index, int)
            or isinstance(self.channel_index, bool)
            or not 0 <= self.channel_index <= 39
        ):
            raise ValueError("channel_index must be an integer between 0 and 39 or None")


@dataclass(frozen=True, kw_only=True)
class TrackUpdate(BaseRecord):
    RECORD_TYPE: ClassVar[str] = "track_update"

    position_m: tuple[float, float]
    velocity_mps: tuple[float, float]
    covariance: tuple[tuple[float, float], tuple[float, float]]
    confidence: float
    track_state: str
    anchors_recent: tuple[str, ...] = ()
    algorithm_version: str

    def __post_init__(self) -> None:
        super().__post_init__()
        position = _tuple_of_floats("position_m", self.position_m, length=2)
        velocity = _tuple_of_floats("velocity_mps", self.velocity_mps, length=2)
        covariance_rows = tuple(
            _tuple_of_floats("covariance row", row, length=2) for row in self.covariance
        )
        if len(covariance_rows) != 2:
            raise ValueError("covariance must be a 2x2 matrix")
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        _require_non_empty("track_state", self.track_state)
        _require_non_empty("algorithm_version", self.algorithm_version)
        object.__setattr__(self, "position_m", position)
        object.__setattr__(self, "velocity_mps", velocity)
        object.__setattr__(self, "covariance", covariance_rows)
        object.__setattr__(self, "confidence", float(self.confidence))
        object.__setattr__(
            self,
            "anchors_recent",
            _tuple_of_strings("anchors_recent", self.anchors_recent),
        )


@dataclass(frozen=True, kw_only=True)
class EvidenceEvent(BaseRecord):
    """Confidence-aware semantic evidence produced before Gameplay authority."""

    RECORD_TYPE: ClassVar[str] = "evidence_event"

    semantic_type: str
    session_id: str
    player_id: str | None = None
    confidence: float
    fusion_policy_version: str
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_non_empty("semantic_type", self.semantic_type)
        _require_non_empty("session_id", self.session_id)
        _require_non_empty("fusion_policy_version", self.fusion_policy_version)
        if self.player_id is not None:
            _require_non_empty("player_id", self.player_id)
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        object.__setattr__(self, "confidence", float(self.confidence))
        object.__setattr__(self, "payload", _dict_copy(self.payload))


@dataclass(frozen=True, kw_only=True)
class GameplayEvent(BaseRecord):
    """Persistable Gameplay command/event contract at the authority boundary.

    This record is deliberately distinct from ``putttrack.gameplay.GameplayEvent``;
    the adapter converts it to the existing domain class without introducing
    any CS-, UWB- or vendor-specific dependency into the Gameplay Engine.
    """

    RECORD_TYPE: ClassVar[str] = "gameplay_event"

    gameplay_type: str
    session_id: str
    player_id: str | None = None
    feature_id: str | None = None
    points_delta: int | None = None
    confidence: float = 1.0
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_non_empty("gameplay_type", self.gameplay_type)
        _require_non_empty("session_id", self.session_id)
        for name in ("player_id", "feature_id"):
            value = getattr(self, name)
            if value is not None:
                _require_non_empty(name, value)
        if self.points_delta is not None and (
            not isinstance(self.points_delta, int) or isinstance(self.points_delta, bool)
        ):
            raise ValueError("points_delta must be an integer or None")
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        object.__setattr__(self, "confidence", float(self.confidence))
        object.__setattr__(self, "payload", _dict_copy(self.payload))


RECORD_CLASSES: tuple[type[BaseRecord], ...] = (
    RangeObservation,
    MotionObservation,
    PhysicalSensorObservation,
    RadioReceptionObservation,
    TrackUpdate,
    EvidenceEvent,
    GameplayEvent,
)
RECORD_CLASS_BY_TYPE: dict[str, type[BaseRecord]] = {
    cls.RECORD_TYPE: cls for cls in RECORD_CLASSES
}
