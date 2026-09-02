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
from .session import (
    TagCaptureReport,
    TagCaptureSession,
    TagIdentityError,
    normalize_device_id,
)

__all__ = [
    "MOTION_CHARACTERISTIC_UUID",
    "PROTOCOL_VERSION",
    "SERVICE_UUID",
    "STATUS_CHARACTERISTIC_UUID",
    "FrozenHistoryMetadata",
    "MotionRecord",
    "StatusRecord",
    "TagCaptureReport",
    "TagCaptureSession",
    "TagIdentityError",
    "TelemetryProtocolError",
    "frozen_history_from_smp",
    "frozen_history_metadata_from_smp",
    "motion_from_smp",
    "motion_window_from_smp",
    "parse_motion",
    "parse_status",
    "status_from_smp",
    "normalize_device_id",
]
