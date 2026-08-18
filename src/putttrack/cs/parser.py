"""Interfaces for converting Nordic/Bbo Channel Sounding serial output to data."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any


_VENDOR_DISTANCE_RE = re.compile(
    r"Distance estimates on antenna path\s+(?P<path>\d+)\s*:\s*"
    r"ifft\s*:\s*(?P<ifft>[-+0-9.eE]+)\s*,\s*"
    r"phase_slope\s*:\s*(?P<phase>[-+0-9.eE]+)\s*,\s*"
    r"rtt\s*:\s*(?P<rtt>[-+0-9.eE]+)",
    re.IGNORECASE,
)


class CsParseError(ValueError):
    """Raised when a line looks like a range record but is malformed."""


@dataclass(frozen=True)
class ParsedCsEstimate:
    antenna_path: int | None
    distance_ifft_m: float | None
    distance_phase_m: float | None
    distance_rtt_m: float | None
    rssi_dbm: float | None = None
    source_monotonic_ns: int | None = None
    source_sequence: int | None = None
    source_boot_id: str | None = None
    source_device_id: str | None = None
    procedure_id: str | None = None
    quality: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if all(
            value is None
            for value in (
                self.distance_ifft_m,
                self.distance_phase_m,
                self.distance_rtt_m,
            )
        ):
            raise CsParseError("at least one distance estimate is required")
        if self.source_sequence is not None and self.source_sequence < 0:
            raise CsParseError("source_sequence must be non-negative")
        if self.source_monotonic_ns is not None and self.source_monotonic_ns < 0:
            raise CsParseError("source_monotonic_ns must be non-negative")
        if self.source_boot_id is not None and not self.source_boot_id.strip():
            raise CsParseError("source_boot_id must be non-empty when supplied")
        if self.source_device_id is not None and not self.source_device_id.strip():
            raise CsParseError("source_device_id must be non-empty when supplied")


class CsSerialParser:
    """Parse structured PuttTrack JSON or the vendor RAS text format."""

    def parse_line(self, line: str) -> ParsedCsEstimate | None:
        stripped = line.strip()
        if not stripped:
            return None
        if stripped.startswith("{"):
            return self._parse_json(stripped)
        match = _VENDOR_DISTANCE_RE.search(stripped)
        if match:
            try:
                return ParsedCsEstimate(
                    antenna_path=int(match.group("path")),
                    distance_ifft_m=float(match.group("ifft")),
                    distance_phase_m=float(match.group("phase")),
                    distance_rtt_m=float(match.group("rtt")),
                    quality={
                        "parser": "bbo_vendor_text_v1",
                        "timestamp_origin": "host_receive_fallback",
                        "boot_id_origin": "capture_run_fallback",
                        "device_id_origin": "capture_cli_fallback",
                    },
                )
            except ValueError as exc:
                raise CsParseError(f"invalid vendor distance values: {stripped}") from exc
        return None

    def _parse_json(self, stripped: str) -> ParsedCsEstimate:
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise CsParseError(f"invalid structured CS JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise CsParseError("structured CS line must be a JSON object")

        def first(*names: str):
            for name in names:
                if name in payload:
                    return payload[name]
            return None

        try:
            path = first("antenna_path", "path")
            sequence = first("source_sequence", "sequence")
            source_time = first("source_monotonic_ns", "timestamp_ns")
            boot_id = first("source_boot_id", "boot_id")
            device_id = first("source_device_id", "device_id")
            quality = dict(payload.get("quality") or {})
            quality.setdefault("parser", "putttrack_structured_json_v1")
            quality.setdefault(
                "timestamp_origin",
                "device" if source_time is not None else "host_receive_fallback",
            )
            quality.setdefault(
                "boot_id_origin",
                "device" if boot_id is not None else "capture_run_fallback",
            )
            quality.setdefault(
                "device_id_origin",
                "device" if device_id is not None else "capture_cli_fallback",
            )
            return ParsedCsEstimate(
                antenna_path=int(path) if path is not None else None,
                distance_ifft_m=(
                    float(first("distance_ifft_m", "ifft_m", "ifft"))
                    if first("distance_ifft_m", "ifft_m", "ifft") is not None
                    else None
                ),
                distance_phase_m=(
                    float(first("distance_phase_m", "phase_slope_m", "phase_slope"))
                    if first("distance_phase_m", "phase_slope_m", "phase_slope") is not None
                    else None
                ),
                distance_rtt_m=(
                    float(first("distance_rtt_m", "rtt_m", "rtt"))
                    if first("distance_rtt_m", "rtt_m", "rtt") is not None
                    else None
                ),
                rssi_dbm=(
                    float(first("rssi_dbm", "rssi"))
                    if first("rssi_dbm", "rssi") is not None
                    else None
                ),
                source_monotonic_ns=int(source_time) if source_time is not None else None,
                source_sequence=int(sequence) if sequence is not None else None,
                source_boot_id=str(boot_id) if boot_id is not None else None,
                source_device_id=str(device_id) if device_id is not None else None,
                procedure_id=(
                    str(payload["procedure_id"])
                    if payload.get("procedure_id") is not None
                    else None
                ),
                quality=quality,
            )
        except (TypeError, ValueError) as exc:
            raise CsParseError(f"invalid structured CS values: {exc}") from exc
