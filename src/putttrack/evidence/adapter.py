"""Sensor-independent semantic evidence to Gameplay authority adapter."""

from __future__ import annotations

from typing import Any

from putttrack.contracts import EvidenceEvent, GameplayEvent as ContractGameplayEvent
from putttrack.gameplay import EventType, GameplayEvent as DomainGameplayEvent


class EvidenceAdapterError(ValueError):
    """Raised when confirmed evidence is incomplete for Gameplay authority."""


_EVENT_TYPE_BY_NAME = {item.value: item for item in EventType}


def _required(value: str | None, name: str) -> str:
    if value is None or not value:
        raise EvidenceAdapterError(f"{name} is required for Gameplay adaptation")
    return value


class EvidenceToGameplayAdapter:
    """Convert semantic evidence into transport-independent Gameplay commands."""

    def from_evidence(self, evidence: EvidenceEvent) -> DomainGameplayEvent:
        try:
            event_type = _EVENT_TYPE_BY_NAME[evidence.semantic_type]
        except KeyError as exc:
            raise EvidenceAdapterError(
                f"semantic event {evidence.semantic_type!r} is not a Gameplay event"
            ) from exc
        hole_id = _required(evidence.hole_id, "hole_id")
        ball_id = _required(evidence.ball_id, "ball_id")
        payload = dict(evidence.payload)
        metadata: dict[str, Any] = {
            **payload.pop("metadata", {}),
            "trace_id": evidence.trace_id,
            "correlation_id": evidence.correlation_id,
            "confidence": evidence.confidence,
            "fusion_policy_version": evidence.fusion_policy_version,
            "raw_evidence_refs": list(evidence.raw_evidence_refs),
            "source_boot_id": evidence.source_boot_id,
            "source_sequence": evidence.sequence,
            "source_monotonic_ns": evidence.source_monotonic_ns,
            **payload,
        }
        return DomainGameplayEvent(
            event_id=evidence.event_id,
            event_type=event_type,
            timestamp_ms=evidence.edge_received_ns // 1_000_000,
            hole_id=hole_id,
            ball_id=ball_id,
            feature_id=evidence.payload.get("feature_id"),
            points_delta=evidence.payload.get("points_delta"),
            source=evidence.source_device_id,
            confidence=evidence.confidence,
            metadata=metadata,
        )

    def from_contract_gameplay(
        self, event: ContractGameplayEvent
    ) -> DomainGameplayEvent:
        try:
            event_type = _EVENT_TYPE_BY_NAME[event.gameplay_type]
        except KeyError as exc:
            raise EvidenceAdapterError(
                f"gameplay_type {event.gameplay_type!r} is unsupported"
            ) from exc
        return DomainGameplayEvent(
            event_id=event.event_id,
            event_type=event_type,
            timestamp_ms=event.edge_received_ns // 1_000_000,
            hole_id=_required(event.hole_id, "hole_id"),
            ball_id=_required(event.ball_id, "ball_id"),
            feature_id=event.feature_id,
            points_delta=event.points_delta,
            source=event.source_device_id,
            confidence=event.confidence,
            metadata={
                **event.payload,
                "trace_id": event.trace_id,
                "raw_evidence_refs": list(event.raw_evidence_refs),
            },
        )
