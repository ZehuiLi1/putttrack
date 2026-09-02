"""PuttTrack smart-ball telemetry protocol."""

from .telemetry import (
    MOTION_CHARACTERISTIC_UUID,
    PROTOCOL_VERSION,
    SERVICE_UUID,
    STATUS_CHARACTERISTIC_UUID,
    FrozenHistoryMetadata,
    MotionRecord,
    StatusRecord,
    TelemetryProtocolError,
    frozen_history_from_smp,
    frozen_history_metadata_from_smp,
    motion_from_smp,
    motion_window_from_smp,
    parse_motion,
    parse_status,
    status_from_smp,
)

__all__ = [
    "MOTION_CHARACTERISTIC_UUID",
    "PROTOCOL_VERSION",
    "SERVICE_UUID",
    "STATUS_CHARACTERISTIC_UUID",
    "FrozenHistoryMetadata",
    "MotionRecord",
    "StatusRecord",
    "TelemetryProtocolError",
    "frozen_history_from_smp",
    "frozen_history_metadata_from_smp",
    "motion_from_smp",
    "motion_window_from_smp",
    "parse_motion",
    "parse_status",
    "status_from_smp",
]
