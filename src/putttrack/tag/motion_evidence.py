"""Parser for the research embedded-motion BLE evidence packet."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import struct
from typing import Any

MOTION_EVIDENCE_SERVICE_UUID = "8f3a1100-6e7d-4b9a-a6e8-3f3f7d2c0001"
MOTION_EVIDENCE_CHARACTERISTIC_UUID = "8f3a1101-6e7d-4b9a-a6e8-3f3f7d2c0001"
MOTION_EVIDENCE_PACKET_SIZE = 28
MOTION_EVIDENCE_PROTOCOL_VERSION = 1

STATE_NAMES = {
    0: "UNKNOWN",
    1: "STATIONARY",
    2: "ROLLING",
    3: "SETTLING",
    4: "CARRIED",
    5: "AIRBORNE",
}

EVENT_BITS = {
    0: "MOTION_ONSET",
    1: "PICKUP_SUSPECTED",
    2: "ROLLING_START",
    3: "SETTLED",
    4: "DROP_LANDING_CANDIDATE",
    5: "TEE_ARM_MARKER",
}

QUALITY_BITS = {
    0: "SENSOR_INVALID",
    1: "GYRO_CLIPPED",
    2: "BASELINE_UNREADY",
    3: "PICKUP_WINDOW_CLIPPED",
    4: "SEQUENCE_OR_TIME_GAP",
}


class MotionEvidenceProtocolError(ValueError):
    pass


def _decode_bits(value: int, names: dict[int, str]) -> tuple[str, ...]:
    return tuple(name for bit, name in names.items() if value & (1 << bit))


@dataclass(frozen=True)
class EmbeddedMotionEvidence:
    protocol_version: int
    state_code: int
    motion_state: str
    event_bits: int
    events: tuple[str, ...]
    source_sequence: int
    source_time_us: int
    confidence: float
    quality_bits: int
    quality: tuple[str, ...]
    model_hash32: int
    tee_arm_epoch: int

    @property
    def authority(self) -> bool:
        return False

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["authority"] = False
        return result


def parse_motion_evidence(data: bytes | bytearray | memoryview) -> EmbeddedMotionEvidence:
    packet = bytes(data)
    if len(packet) != MOTION_EVIDENCE_PACKET_SIZE:
        raise MotionEvidenceProtocolError(
            f"motion evidence packet must be {MOTION_EVIDENCE_PACKET_SIZE} bytes, got {len(packet)}"
        )
    version = packet[0]
    if version != MOTION_EVIDENCE_PROTOCOL_VERSION:
        raise MotionEvidenceProtocolError(
            f"unsupported motion evidence protocol {version}"
        )
    state_code = packet[1]
    if state_code not in STATE_NAMES:
        raise MotionEvidenceProtocolError(f"unknown motion state code {state_code}")
    event_bits, sequence, source_time_us, confidence_permille, quality_bits, model_hash32, tee_epoch = struct.unpack_from(
        "<HIQHHII", packet, 2
    )
    if confidence_permille > 1000:
        raise MotionEvidenceProtocolError("confidence_permille exceeds 1000")
    return EmbeddedMotionEvidence(
        protocol_version=version,
        state_code=state_code,
        motion_state=STATE_NAMES[state_code],
        event_bits=event_bits,
        events=_decode_bits(event_bits, EVENT_BITS),
        source_sequence=sequence,
        source_time_us=source_time_us,
        confidence=confidence_permille / 1000.0,
        quality_bits=quality_bits,
        quality=_decode_bits(quality_bits, QUALITY_BITS),
        model_hash32=model_hash32,
        tee_arm_epoch=tee_epoch,
    )
