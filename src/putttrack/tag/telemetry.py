"""Strict parser for the nRF54L15 Tag binary GATT protocol."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import struct
from typing import Any, Mapping

PROTOCOL_VERSION = 1
STATUS_PACKET_SIZE = 64
MOTION_PACKET_SIZE = 56

SERVICE_UUID = "8f3a1000-6e7d-4b9a-a6e8-3f3f7d2c0001"
STATUS_CHARACTERISTIC_UUID = "8f3a1001-6e7d-4b9a-a6e8-3f3f7d2c0001"
MOTION_CHARACTERISTIC_UUID = "8f3a1002-6e7d-4b9a-a6e8-3f3f7d2c0001"


class TelemetryProtocolError(ValueError):
    """Raised when a Tag packet is truncated, incompatible or malformed."""


@dataclass(frozen=True)
class StatusRecord:
    protocol_version: int
    sequence: int
    uptime_ms: int
    reset_cause: int
    sensor_error_count: int
    notify_drop_count: int
    adxl367_ready: bool
    bmi270_ready: bool
    notify_active: bool
    device_id: str
    boot_id: str
    firmware_version: str
    stream_rate_hz: int | None = None
    adxl367_odr_hz: int | None = None
    adxl367_range_g: int | None = None
    bmi270_accel_odr_hz: int | None = None
    bmi270_accel_range_g: int | None = None
    bmi270_gyro_odr_hz: int | None = None
    bmi270_gyro_range_dps: int | None = None
    adxl367_clip_count: int = 0
    bmi270_accel_clip_count: int = 0
    bmi270_gyro_clip_count: int = 0
    power_policy: str | None = None
    runtime_state: str | None = None
    power_transition_count: int = 0
    idle_timeout_ms: int | None = None
    wake_poll_ms: int | None = None
    advertising_interval_min_ms: int | None = None
    advertising_interval_max_ms: int | None = None
    advertising_start_error_count: int = 0
    power_management_error_count: int = 0
    bmi270_spi_suspended: bool = False
    idle_wake_interrupt_enabled: bool = False
    adxl367_wakeup_mode_enabled: bool = False
    battery_supported: bool | None = None
    nfc_enabled: bool | None = None
    nfc_setup_error: int | None = None
    nfc_field_on_count: int = 0
    nfc_field_off_count: int = 0
    nfc_field_present: bool = False
    nfc_service_window_active: bool = False
    nfc_service_window_ms: int | None = None
    nfc_service_window_open_count: int = 0
    nfc_service_window_suppressed_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MotionRecord:
    protocol_version: int
    sequence: int
    source_monotonic_us: int
    adxl367_valid: bool
    bmi270_valid: bool
    adxl367_accel_micro_ms2: tuple[int, int, int]
    bmi270_accel_micro_ms2: tuple[int, int, int]
    bmi270_gyro_micro_rads: tuple[int, int, int]
    sensor_error_bits: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FrozenHistoryMetadata:
    protocol_version: int
    capture_id: int
    sample_size: int
    sample_count: int
    chunk_size: int
    chunk_count: int
    start_sequence: int
    end_sequence: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _validate_header(packet: bytes, expected_size: int, label: str) -> None:
    if len(packet) != expected_size:
        raise TelemetryProtocolError(
            f"{label} packet must be {expected_size} bytes, got {len(packet)}"
        )
    version, _, declared_size = struct.unpack_from("<BBH", packet)
    if version != PROTOCOL_VERSION:
        raise TelemetryProtocolError(
            f"unsupported {label} protocol version {version}; expected {PROTOCOL_VERSION}"
        )
    if declared_size != expected_size:
        raise TelemetryProtocolError(
            f"{label} declared size {declared_size} does not match {expected_size}"
        )


def parse_status(data: bytes | bytearray | memoryview) -> StatusRecord:
    packet = bytes(data)
    _validate_header(packet, STATUS_PACKET_SIZE, "status")
    (
        version,
        flags,
        _,
        sequence,
        uptime_ms,
        reset_cause,
        sensor_error_count,
        notify_drop_count,
        device_id_len,
        boot_id_len,
        firmware_len,
        _,
    ) = struct.unpack_from("<BBHIQIII4B", packet)

    if not 1 <= device_id_len <= 16:
        raise TelemetryProtocolError(f"invalid device ID length {device_id_len}")
    if boot_id_len != 8:
        raise TelemetryProtocolError(f"invalid boot ID length {boot_id_len}")
    if not 1 <= firmware_len <= 8:
        raise TelemetryProtocolError(f"invalid firmware length {firmware_len}")

    try:
        firmware_version = packet[56 : 56 + firmware_len].decode("ascii")
    except UnicodeDecodeError as exc:
        raise TelemetryProtocolError("firmware version is not ASCII") from exc

    power_policy = None
    if flags & 0x20:
        power_policy = "research"
    elif flags & 0x40:
        power_policy = "idle"
    elif flags & 0x10:
        power_policy = "auto"

    return StatusRecord(
        protocol_version=version,
        sequence=sequence,
        uptime_ms=uptime_ms,
        reset_cause=reset_cause,
        sensor_error_count=sensor_error_count,
        notify_drop_count=notify_drop_count,
        adxl367_ready=bool(flags & 0x01),
        bmi270_ready=bool(flags & 0x02),
        notify_active=bool(flags & 0x04),
        device_id=packet[32 : 32 + device_id_len].hex(),
        boot_id=packet[48 : 48 + boot_id_len].hex(),
        firmware_version=firmware_version,
        power_policy=power_policy,
        runtime_state=("active" if flags & 0x08 else "idle") if power_policy else None,
    )


def parse_motion(data: bytes | bytearray | memoryview) -> MotionRecord:
    packet = bytes(data)
    _validate_header(packet, MOTION_PACKET_SIZE, "motion")
    unpacked = struct.unpack("<BBHIQ9iI", packet)
    version, flags, _, sequence, source_monotonic_us = unpacked[:5]
    values = unpacked[5:14]
    sensor_error_bits = unpacked[14]

    return MotionRecord(
        protocol_version=version,
        sequence=sequence,
        source_monotonic_us=source_monotonic_us,
        adxl367_valid=bool(flags & 0x01),
        bmi270_valid=bool(flags & 0x02),
        adxl367_accel_micro_ms2=tuple(values[0:3]),
        bmi270_accel_micro_ms2=tuple(values[3:6]),
        bmi270_gyro_micro_rads=tuple(values[6:9]),
        sensor_error_bits=sensor_error_bits,
    )


def _required_int(payload: Mapping[str, Any], name: str) -> int:
    value = payload.get(name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise TelemetryProtocolError(f"SMP field {name!r} must be an integer")
    return value


def _required_non_negative_int(payload: Mapping[str, Any], name: str) -> int:
    value = _required_int(payload, name)
    if value < 0:
        raise TelemetryProtocolError(f"SMP field {name!r} must be non-negative")
    return value


def _required_bool(payload: Mapping[str, Any], name: str) -> bool:
    value = payload.get(name)
    if not isinstance(value, bool):
        raise TelemetryProtocolError(f"SMP field {name!r} must be a boolean")
    return value


def _required_text(payload: Mapping[str, Any], name: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not value:
        raise TelemetryProtocolError(f"SMP field {name!r} must be non-empty text")
    return value


def _optional_int(payload: Mapping[str, Any], name: str) -> int | None:
    value = payload.get(name)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise TelemetryProtocolError(f"SMP field {name!r} must be an integer")
    return value


def _optional_non_negative_int(payload: Mapping[str, Any], name: str) -> int | None:
    value = _optional_int(payload, name)
    if value is not None and value < 0:
        raise TelemetryProtocolError(f"SMP field {name!r} must be non-negative")
    return value


def _optional_bool(payload: Mapping[str, Any], name: str) -> bool | None:
    value = payload.get(name)
    if value is None:
        return None
    if not isinstance(value, bool):
        raise TelemetryProtocolError(f"SMP field {name!r} must be a boolean")
    return value


def _optional_text(payload: Mapping[str, Any], name: str) -> str | None:
    value = payload.get(name)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise TelemetryProtocolError(f"SMP field {name!r} must be non-empty text")
    return value


def status_from_smp(payload: Mapping[str, Any]) -> StatusRecord:
    """Normalize the custom mcumgr status response into the GATT record model."""

    version = _required_int(payload, "proto")
    if version != PROTOCOL_VERSION:
        raise TelemetryProtocolError(
            f"unsupported SMP status protocol version {version}; expected {PROTOCOL_VERSION}"
        )
    device_id = _required_text(payload, "device_id")
    boot_id = _required_text(payload, "boot_id")
    try:
        device_id_bytes = bytes.fromhex(device_id)
        boot_id_bytes = bytes.fromhex(boot_id)
    except ValueError as exc:
        raise TelemetryProtocolError("SMP device_id and boot_id must be hexadecimal") from exc
    if not 1 <= len(device_id_bytes) <= 16:
        raise TelemetryProtocolError("SMP device_id must contain 1..16 bytes")
    if len(boot_id_bytes) != 8:
        raise TelemetryProtocolError("SMP boot_id must contain exactly 8 bytes")

    firmware_version = _required_text(payload, "fw")
    if len(firmware_version) > 8 or not firmware_version.isascii():
        raise TelemetryProtocolError("SMP firmware version must be 1..8 ASCII characters")

    power_policy = _optional_text(payload, "power_policy")
    runtime_state = _optional_text(payload, "runtime_state")
    if power_policy not in (None, "auto", "research", "idle"):
        raise TelemetryProtocolError(f"unsupported power_policy {power_policy!r}")
    if runtime_state not in (None, "active", "idle"):
        raise TelemetryProtocolError(f"unsupported runtime_state {runtime_state!r}")

    return StatusRecord(
        protocol_version=version,
        sequence=_required_non_negative_int(payload, "seq"),
        uptime_ms=_required_non_negative_int(payload, "uptime_ms"),
        reset_cause=_required_non_negative_int(payload, "reset"),
        sensor_error_count=_required_non_negative_int(payload, "sensor_errors"),
        notify_drop_count=_required_non_negative_int(payload, "notify_drops"),
        adxl367_ready=_required_bool(payload, "adxl_ready"),
        bmi270_ready=_required_bool(payload, "bmi_ready"),
        notify_active=False,
        device_id=device_id.lower(),
        boot_id=boot_id.lower(),
        firmware_version=firmware_version,
        stream_rate_hz=_optional_non_negative_int(payload, "stream_hz"),
        adxl367_odr_hz=_optional_non_negative_int(payload, "adxl_odr_hz"),
        adxl367_range_g=_optional_non_negative_int(payload, "adxl_range_g"),
        bmi270_accel_odr_hz=_optional_non_negative_int(payload, "bmi_accel_odr_hz"),
        bmi270_accel_range_g=_optional_non_negative_int(payload, "bmi_accel_range_g"),
        bmi270_gyro_odr_hz=_optional_non_negative_int(payload, "bmi_gyro_odr_hz"),
        bmi270_gyro_range_dps=_optional_non_negative_int(payload, "bmi_gyro_range_dps"),
        adxl367_clip_count=_optional_non_negative_int(payload, "adxl_clips") or 0,
        bmi270_accel_clip_count=(
            _optional_non_negative_int(payload, "bmi_accel_clips") or 0
        ),
        bmi270_gyro_clip_count=(
            _optional_non_negative_int(payload, "bmi_gyro_clips") or 0
        ),
        power_policy=power_policy,
        runtime_state=runtime_state,
        power_transition_count=(
            _optional_non_negative_int(payload, "power_transitions") or 0
        ),
        idle_timeout_ms=_optional_non_negative_int(payload, "idle_timeout_ms"),
        wake_poll_ms=_optional_non_negative_int(payload, "wake_poll_ms"),
        advertising_interval_min_ms=_optional_non_negative_int(
            payload, "adv_interval_min_ms"
        ),
        advertising_interval_max_ms=_optional_non_negative_int(
            payload, "adv_interval_max_ms"
        ),
        advertising_start_error_count=(
            _optional_non_negative_int(payload, "adv_start_errors") or 0
        ),
        power_management_error_count=(
            _optional_non_negative_int(payload, "pm_errors") or 0
        ),
        bmi270_spi_suspended=_optional_bool(payload, "bmi_spi_suspended") or False,
        idle_wake_interrupt_enabled=_optional_bool(payload, "wake_interrupt") or False,
        adxl367_wakeup_mode_enabled=_optional_bool(payload, "adxl_wakeup_mode") or False,
        battery_supported=_optional_bool(payload, "battery_supported"),
        nfc_enabled=_optional_bool(payload, "nfc_enabled"),
        nfc_setup_error=_optional_int(payload, "nfc_setup_error"),
        nfc_field_on_count=_optional_non_negative_int(payload, "nfc_field_on") or 0,
        nfc_field_off_count=_optional_non_negative_int(payload, "nfc_field_off") or 0,
        nfc_field_present=_optional_bool(payload, "nfc_field_present") or False,
        nfc_service_window_active=(
            _optional_bool(payload, "nfc_service_window") or False
        ),
        nfc_service_window_ms=_optional_non_negative_int(
            payload, "nfc_service_window_ms"
        ),
        nfc_service_window_open_count=(
            _optional_non_negative_int(payload, "nfc_service_window_opens") or 0
        ),
        nfc_service_window_suppressed_count=(
            _optional_non_negative_int(payload, "nfc_service_window_suppressed")
            or 0
        ),
    )


def motion_from_smp(payload: Mapping[str, Any]) -> MotionRecord:
    """Normalize the custom mcumgr motion snapshot into the GATT record model."""

    version = _required_int(payload, "proto")
    if version != PROTOCOL_VERSION:
        raise TelemetryProtocolError(
            f"unsupported SMP motion protocol version {version}; expected {PROTOCOL_VERSION}"
        )
    return MotionRecord(
        protocol_version=version,
        sequence=_required_non_negative_int(payload, "seq"),
        source_monotonic_us=_required_non_negative_int(payload, "t_us"),
        adxl367_valid=_required_bool(payload, "adxl_valid"),
        bmi270_valid=_required_bool(payload, "bmi_valid"),
        adxl367_accel_micro_ms2=tuple(
            _required_int(payload, name) for name in ("adxl_ax", "adxl_ay", "adxl_az")
        ),
        bmi270_accel_micro_ms2=tuple(
            _required_int(payload, name) for name in ("bmi_ax", "bmi_ay", "bmi_az")
        ),
        bmi270_gyro_micro_rads=tuple(
            _required_int(payload, name) for name in ("bmi_gx", "bmi_gy", "bmi_gz")
        ),
        sensor_error_bits=_required_non_negative_int(payload, "errors"),
    )


def motion_window_from_smp(payload: Mapping[str, Any]) -> tuple[MotionRecord, ...]:
    """Decode a contiguous binary motion window returned by mcumgr command 2."""

    version = _required_int(payload, "proto")
    if version != PROTOCOL_VERSION:
        raise TelemetryProtocolError(
            f"unsupported SMP window protocol version {version}; expected {PROTOCOL_VERSION}"
        )
    sample_size = _required_int(payload, "sample_size")
    count = _required_int(payload, "count")
    start_sequence = _required_int(payload, "start_seq")
    end_sequence = _required_int(payload, "end_seq")
    if sample_size != MOTION_PACKET_SIZE:
        raise TelemetryProtocolError(
            f"SMP window sample size {sample_size} does not match {MOTION_PACKET_SIZE}"
        )
    if count < 0 or count > 64:
        raise TelemetryProtocolError(f"SMP window count {count} is outside 0..64")
    data_hex = payload.get("data_hex")
    if not isinstance(data_hex, str):
        raise TelemetryProtocolError("SMP field 'data_hex' must be text")
    try:
        raw = bytes.fromhex(data_hex)
    except ValueError as exc:
        raise TelemetryProtocolError("SMP window data_hex is not hexadecimal") from exc
    expected_bytes = count * sample_size
    if len(raw) != expected_bytes:
        raise TelemetryProtocolError(
            f"SMP window contains {len(raw)} bytes; expected {expected_bytes}"
        )

    records = tuple(
        parse_motion(raw[offset : offset + sample_size])
        for offset in range(0, len(raw), sample_size)
    )
    if records:
        if records[0].sequence != start_sequence or records[-1].sequence != end_sequence:
            raise TelemetryProtocolError("SMP window sequence metadata does not match its records")
        if any(
            current.sequence != previous.sequence + 1
            for previous, current in zip(records, records[1:])
        ):
            raise TelemetryProtocolError("SMP window records are not contiguous")
    elif start_sequence != 0 or end_sequence != 0:
        raise TelemetryProtocolError("empty SMP window must have zero sequence bounds")
    return records


def frozen_history_metadata_from_smp(
    payload: Mapping[str, Any],
) -> FrozenHistoryMetadata:
    """Validate metadata returned when the Tag freezes its history ring."""

    version = _required_int(payload, "proto")
    if version != PROTOCOL_VERSION:
        raise TelemetryProtocolError(
            f"unsupported frozen-history protocol version {version}; "
            f"expected {PROTOCOL_VERSION}"
        )
    metadata = FrozenHistoryMetadata(
        protocol_version=version,
        capture_id=_required_int(payload, "capture_id"),
        sample_size=_required_int(payload, "sample_size"),
        sample_count=_required_int(payload, "count"),
        chunk_size=_required_int(payload, "chunk_size"),
        chunk_count=_required_int(payload, "chunk_count"),
        start_sequence=_required_int(payload, "start_seq"),
        end_sequence=_required_int(payload, "end_seq"),
    )
    if metadata.capture_id <= 0:
        raise TelemetryProtocolError("frozen-history capture_id must be positive")
    if metadata.sample_size != MOTION_PACKET_SIZE:
        raise TelemetryProtocolError("frozen-history sample size is incompatible")
    if metadata.chunk_size != 64:
        raise TelemetryProtocolError("frozen-history chunk size must be 64")
    if metadata.sample_count < 0 or metadata.sample_count > 1024:
        raise TelemetryProtocolError("frozen-history count is outside 0..1024")
    expected_chunks = (metadata.sample_count + metadata.chunk_size - 1) // metadata.chunk_size
    if metadata.chunk_count != expected_chunks:
        raise TelemetryProtocolError("frozen-history chunk count is inconsistent")
    if metadata.sample_count == 0:
        if metadata.start_sequence != 0 or metadata.end_sequence != 0:
            raise TelemetryProtocolError("empty frozen history must have zero sequence bounds")
    elif metadata.end_sequence - metadata.start_sequence + 1 != metadata.sample_count:
        raise TelemetryProtocolError("frozen-history sequence bounds are not contiguous")
    return metadata


def frozen_history_from_smp(
    metadata: FrozenHistoryMetadata,
    chunks: list[Mapping[str, Any]],
) -> tuple[MotionRecord, ...]:
    """Reassemble and validate every chunk from one frozen Tag history."""

    if len(chunks) != metadata.chunk_count:
        raise TelemetryProtocolError(
            f"frozen history needs {metadata.chunk_count} chunks, got {len(chunks)}"
        )
    records: list[MotionRecord] = []
    for expected_index, payload in enumerate(chunks):
        if _required_int(payload, "capture_id") != metadata.capture_id:
            raise TelemetryProtocolError("frozen-history capture ID changed during retrieval")
        if _required_int(payload, "chunk_index") != expected_index:
            raise TelemetryProtocolError("frozen-history chunk index is out of order")
        records.extend(motion_window_from_smp(payload))
    if len(records) != metadata.sample_count:
        raise TelemetryProtocolError("frozen-history reassembled sample count is inconsistent")
    if records:
        if (
            records[0].sequence != metadata.start_sequence
            or records[-1].sequence != metadata.end_sequence
        ):
            raise TelemetryProtocolError("frozen-history bounds do not match reassembled records")
        if any(
            current.sequence != previous.sequence + 1
            for previous, current in zip(records, records[1:])
        ):
            raise TelemetryProtocolError("frozen-history records are not contiguous")
    return tuple(records)
