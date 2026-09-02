"""Identity lock and continuity checks for one Tag capture session."""

from __future__ import annotations

import hmac
from dataclasses import asdict, dataclass
from typing import Any

from .telemetry import MotionRecord, StatusRecord, TelemetryProtocolError


class TagIdentityError(TelemetryProtocolError):
    """Raised before capture when the connected Tag is not the requested Tag."""


def normalize_device_id(value: str) -> str:
    normalized = value.strip().lower()
    try:
        decoded = bytes.fromhex(normalized)
    except ValueError as exc:
        raise TagIdentityError("expected device ID must be hexadecimal") from exc
    if not 1 <= len(decoded) <= 16:
        raise TagIdentityError("expected device ID must contain 1..16 bytes")
    return decoded.hex()


def _sequence_delta(current: int, previous: int) -> int | None:
    """Return forward uint32 distance, or None for a backwards regression."""

    delta = (current - previous) & 0xFFFFFFFF
    if delta >= 0x80000000:
        return None
    return delta


@dataclass(frozen=True)
class TagCaptureReport:
    device_id: str
    boot_id: str
    firmware_version: str
    motion_records: int
    first_motion_sequence: int | None
    last_motion_sequence: int | None
    sequence_gaps: int
    sensor_error_delta: int
    notify_drop_delta: int
    adxl367_clip_delta: int
    bmi270_accel_clip_delta: int
    bmi270_gyro_clip_delta: int
    advertising_error_delta: int
    power_management_error_delta: int
    issues: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.issues

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": "PASS" if self.passed else "FAIL",
            **asdict(self),
        }


class TagCaptureSession:
    """Validate that one capture stays on one healthy device/boot/time domain."""

    _DELTA_COUNTERS = {
        "sensor_error_delta": "sensor_error_count",
        "notify_drop_delta": "notify_drop_count",
        "adxl367_clip_delta": "adxl367_clip_count",
        "bmi270_accel_clip_delta": "bmi270_accel_clip_count",
        "bmi270_gyro_clip_delta": "bmi270_gyro_clip_count",
        "advertising_error_delta": "advertising_start_error_count",
        "power_management_error_delta": "power_management_error_count",
    }
    _FAIL_ON_INCREASE = {
        "sensor_error_count",
        "notify_drop_count",
        "advertising_start_error_count",
        "power_management_error_count",
    }

    def __init__(self, *, expected_device_id: str | None = None) -> None:
        self.expected_device_id = (
            normalize_device_id(expected_device_id)
            if expected_device_id is not None
            else None
        )
        self._initial: StatusRecord | None = None
        self._last_motion: MotionRecord | None = None
        self._motion_records = 0
        self._first_motion_sequence: int | None = None
        self._sequence_gaps = 0
        self._issues: set[str] = set()
        self._finalized = False

    def start(self, status: StatusRecord) -> None:
        if self._initial is not None:
            raise TelemetryProtocolError("Tag capture session was already started")
        if self.expected_device_id is not None and not hmac.compare_digest(
            status.device_id,
            self.expected_device_id,
        ):
            raise TagIdentityError(
                f"connected Tag is {status.device_id}; expected {self.expected_device_id}"
            )
        self._initial = status
        if not status.adxl367_ready:
            self._issues.add("initial_adxl367_not_ready")
        if not status.bmi270_ready:
            self._issues.add("initial_bmi270_not_ready")
        if status.sensor_error_count:
            self._issues.add("initial_sensor_errors_nonzero")

    def observe_motion(self, motion: MotionRecord) -> None:
        if self._initial is None:
            raise TelemetryProtocolError("Tag capture session has not started")
        if self._finalized:
            raise TelemetryProtocolError("Tag capture session is already finalized")

        if self._first_motion_sequence is None:
            self._first_motion_sequence = motion.sequence
        prior = self._last_motion
        if prior is not None:
            delta = _sequence_delta(motion.sequence, prior.sequence)
            if delta is None:
                self._issues.add("motion_sequence_regression")
            elif delta == 0:
                self._issues.add("duplicate_motion_sequence")
            elif delta > 1:
                self._sequence_gaps += delta - 1
                self._issues.add("motion_sequence_gap")
            if motion.source_monotonic_us <= prior.source_monotonic_us:
                self._issues.add("motion_clock_not_increasing")
        if not motion.adxl367_valid:
            self._issues.add("motion_adxl367_invalid")
        if not motion.bmi270_valid:
            self._issues.add("motion_bmi270_invalid")
        if motion.sensor_error_bits:
            self._issues.add("motion_sensor_error_bits_nonzero")

        self._last_motion = motion
        self._motion_records += 1

    def record_malformed_motion(self) -> None:
        if self._initial is None:
            raise TelemetryProtocolError("Tag capture session has not started")
        if self._finalized:
            raise TelemetryProtocolError("Tag capture session is already finalized")
        self._issues.add("malformed_motion_packet")

    def finalize(self, status: StatusRecord) -> TagCaptureReport:
        if self._initial is None:
            raise TelemetryProtocolError("Tag capture session has not started")
        if self._finalized:
            raise TelemetryProtocolError("Tag capture session is already finalized")
        self._finalized = True
        initial = self._initial

        if not hmac.compare_digest(status.device_id, initial.device_id):
            self._issues.add("device_id_changed")
        if not hmac.compare_digest(status.boot_id, initial.boot_id):
            self._issues.add("boot_id_changed")
        if status.firmware_version != initial.firmware_version:
            self._issues.add("firmware_version_changed")
        if status.uptime_ms < initial.uptime_ms:
            self._issues.add("status_uptime_regression")
        if _sequence_delta(status.sequence, initial.sequence) is None:
            self._issues.add("status_sequence_regression")
        if self._last_motion is not None and _sequence_delta(
            status.sequence,
            self._last_motion.sequence,
        ) is None:
            self._issues.add("final_status_precedes_last_motion")
        if not status.adxl367_ready:
            self._issues.add("final_adxl367_not_ready")
        if not status.bmi270_ready:
            self._issues.add("final_bmi270_not_ready")

        deltas: dict[str, int] = {}
        for report_name, status_name in self._DELTA_COUNTERS.items():
            first = int(getattr(initial, status_name))
            last = int(getattr(status, status_name))
            deltas[report_name] = last - first
            if last < first:
                self._issues.add(f"{status_name}_regressed")
            elif last > first and status_name in self._FAIL_ON_INCREASE:
                self._issues.add(f"{status_name}_increased")

        return TagCaptureReport(
            device_id=initial.device_id,
            boot_id=initial.boot_id,
            firmware_version=initial.firmware_version,
            motion_records=self._motion_records,
            first_motion_sequence=self._first_motion_sequence,
            last_motion_sequence=(
                self._last_motion.sequence if self._last_motion is not None else None
            ),
            sequence_gaps=self._sequence_gaps,
            issues=tuple(sorted(self._issues)),
            **deltas,
        )
