"""Strict decoder for the non-authoritative MCU shadow event journal."""

from __future__ import annotations
import struct
from typing import Any

EVENT = struct.Struct("<6I2Q2i4I")
NAMES = {
    1: "STROKE_LIKE_CANDIDATE",
    2: "PICKUP_SUSPECTED",
    3: "MOTION_TRANSIENT_UNRESOLVED",
    4: "ONSET_UNRESOLVED",
    5: "QUALITY_BREAK",
    6: "STROKE_PENDING_NOT_COUNTED",
}
FIELDS = (
    "id",
    "type",
    "reason",
    "quality",
    "onset_seq",
    "end_seq",
    "onset_us",
    "decision_us",
    "impulse_milli",
    "gyro_mean_milli",
    "direction_milli",
    "axial_milli",
    "impact_milli",
    "clip_permille",
)


def decode_snapshot(
    payload: dict[str, Any],
    *,
    device_id: str,
    config_sha256: str,
    boot_id: str | None = None,
    generation: int | None = None,
    previous_latest: int | None = None,
    require_active: bool = True,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("snapshot must be an object")
    for key, value in {
        "algorithm_id": "stroke_pickup_shadow_v1",
        "config_sha256": config_sha256,
        "firmware_version": "0.1.19",
        "device_id": device_id.lower(),
    }.items():
        if payload.get(key) != value:
            raise ValueError("identity mismatch: " + key)
    if (
        payload.get("authority") is not False
        or payload.get("candidate_only") is not True
    ):
        raise ValueError("authority violation")
    if not isinstance(payload.get("boot_id"), str) or len(payload["boot_id"]) != 16:
        raise ValueError("invalid boot")
    bytes.fromhex(payload["boot_id"])
    if boot_id is not None and payload["boot_id"] != boot_id:
        raise ValueError("boot changed")
    keys = (
        "stream_hz",
        "generation",
        "sensor_recovery_generation",
        "source_seq",
        "source_us",
        "state",
        "stroke_candidates",
        "pickup_candidates",
        "ambiguous_contacts",
        "unknown_onsets",
        "quality_breaks",
        "quality_flags",
        "first_event_id",
        "latest_event_id",
        "overwritten_events",
        "event_size",
        "event_count",
    )
    for key in keys:
        value = payload.get(key)
        if type(value) is not int or not 0 <= value < (
            2**64 if key == "source_us" else 2**32
        ):
            raise ValueError("invalid integer: " + key)
    for key in ("armed", "held_hint", "count_incomplete"):
        if type(payload.get(key)) is not bool:
            raise ValueError("invalid boolean: " + key)
    if payload["state"] not in range(5):
        raise ValueError("unknown state")
    if payload["stream_hz"] not in ((50,) if require_active else (0, 50)):
        raise ValueError("unsupported rate")
    if generation is not None and payload["generation"] != generation:
        raise ValueError("generation changed")
    n = payload["event_count"]
    latest = payload["latest_event_id"]
    first = payload["first_event_id"]
    if n > 16 or payload["event_size"] != EVENT.size:
        raise ValueError("invalid event layout")
    if (n == 0 and (latest != 0 or first != 0)) or (
        n > 0 and (latest < n or first != latest - n + 1)
    ):
        raise ValueError("inconsistent event range")
    if payload["overwritten_events"] != max(0, latest - 16):
        raise ValueError("inconsistent overwrite counter")
    if previous_latest is not None and latest < previous_latest:
        raise ValueError("counter regressed")
    encoded = payload.get("events_hex")
    if not isinstance(encoded, str) or len(encoded) != n * 128:
        raise ValueError("invalid encoded length")
    raw = bytes.fromhex(encoded)
    events = []
    for index in range(n):
        e = dict(zip(FIELDS, EVENT.unpack_from(raw, index * EVENT.size)))
        if e["id"] != first + index or e["type"] not in NAMES:
            raise ValueError("invalid event identity/type")
        if not e["onset_us"] <= e["decision_us"] <= payload["source_us"]:
            raise ValueError("invalid event time")
        if max(e["direction_milli"], e["axial_milli"], e["clip_permille"]) > 1000:
            raise ValueError("invalid bounded statistic")
        e["name"] = NAMES[e["type"]]
        e["authority"] = False
        e["event_key"] = (
            f"{payload['device_id']}:{payload['boot_id']}:{payload['generation']}:{e['id']}"
        )
        events.append(e)
    loss = (
        first > 1 if previous_latest is None else n > 0 and first > previous_latest + 1
    )
    return {
        **payload,
        "events": events,
        "journal_loss": loss,
        "score_authoritative": False,
    }


def summarize_episode(
    snapshot: dict[str, Any], *, go_us: int, end_us: int
) -> dict[str, Any]:
    if type(go_us) is not int or type(end_us) is not int or go_us > end_us:
        raise ValueError("invalid episode bounds")
    events = [
        e
        for e in snapshot["events"]
        if go_us <= e["onset_us"] <= end_us and e["decision_us"] <= end_us
    ]
    pending = {e["onset_seq"] for e in events if e["type"] == 6}
    resolved = {e["onset_seq"] for e in events if e["type"] in (1, 2, 4)}
    unresolved = sum(e["type"] in (3, 4, 5) for e in events) + len(pending - resolved)
    loss = snapshot["journal_loss"]
    return {
        "authority": False,
        "candidate_only": True,
        "stroke_candidate_count": sum(e["type"] == 1 for e in events),
        "pickup_suspected_count": sum(e["type"] == 2 for e in events),
        "unresolved_events": unresolved,
        "pending_without_final": len(pending - resolved),
        "journal_loss": loss,
        "count_status": (
            "INCOMPLETE_LOG"
            if loss
            else ("UNRESOLVED" if unresolved else "CANDIDATES_ONLY")
        ),
        "confirmed_stroke_count": None,
        "cheating_confirmed": False,
        "events": events,
    }
