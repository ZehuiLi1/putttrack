"""Fail-closed aggregation of one Ball packet observed by several receivers."""

from __future__ import annotations

from dataclasses import dataclass
import statistics
from typing import Any, Mapping, Sequence

from putttrack.contracts import RadioReceptionObservation


@dataclass(frozen=True)
class MultiReceiverContext:
    device_to_ball: Mapping[str, str]
    allowed_receiver_ids: tuple[str, ...]
    minimum_receivers: int = 2
    maximum_receive_span_ns: int = 100_000_000

    def __post_init__(self) -> None:
        if self.minimum_receivers < 1:
            raise ValueError("minimum_receivers must be positive")
        if self.maximum_receive_span_ns < 0:
            raise ValueError("maximum_receive_span_ns must not be negative")
        if len(set(self.allowed_receiver_ids)) != len(self.allowed_receiver_ids):
            raise ValueError("allowed_receiver_ids must be unique")
        if any(not item for item in self.allowed_receiver_ids):
            raise ValueError("allowed_receiver_ids must be non-empty")
        if any(not device or not ball for device, ball in self.device_to_ball.items()):
            raise ValueError("device_to_ball keys and values must be non-empty")
        if len(set(self.device_to_ball.values())) != len(self.device_to_ball):
            raise ValueError("each registered Ball must map to one device")


@dataclass(frozen=True)
class MultiReceiverDecision:
    status: str
    reason: str
    ball_id: str | None
    ball_device_id: str | None
    ball_boot_id: str | None
    ball_radio_sequence: int | None
    payload_digest: str | None
    tx_power_dbm: int | None
    receiver_count: int
    receiver_ids: tuple[str, ...]
    strongest_receiver_id: str | None
    strongest_rssi_dbm: int | None
    median_path_loss_db: float | None
    receive_span_ns: int | None
    position_authority: bool = False
    gameplay_authority: bool = False

    @property
    def quorum_met(self) -> bool:
        return self.status == "accepted"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "reason": self.reason,
            "ball_id": self.ball_id,
            "ball_device_id": self.ball_device_id,
            "ball_boot_id": self.ball_boot_id,
            "ball_radio_sequence": self.ball_radio_sequence,
            "payload_digest": self.payload_digest,
            "tx_power_dbm": self.tx_power_dbm,
            "receiver_count": self.receiver_count,
            "receiver_ids": list(self.receiver_ids),
            "strongest_receiver_id": self.strongest_receiver_id,
            "strongest_rssi_dbm": self.strongest_rssi_dbm,
            "median_path_loss_db": self.median_path_loss_db,
            "receive_span_ns": self.receive_span_ns,
            "position_authority": self.position_authority,
            "gameplay_authority": self.gameplay_authority,
        }


def _rejected(reason: str) -> MultiReceiverDecision:
    return MultiReceiverDecision(
        status="rejected",
        reason=reason,
        ball_id=None,
        ball_device_id=None,
        ball_boot_id=None,
        ball_radio_sequence=None,
        payload_digest=None,
        tx_power_dbm=None,
        receiver_count=0,
        receiver_ids=(),
        strongest_receiver_id=None,
        strongest_rssi_dbm=None,
        median_path_loss_db=None,
        receive_span_ns=None,
    )


def aggregate_radio_receptions(
    observations: Sequence[RadioReceptionObservation],
    context: MultiReceiverContext,
) -> MultiReceiverDecision:
    """Aggregate receiver diversity without deriving position or score authority."""

    if not observations:
        return _rejected("no_receiver_observations")

    first = observations[0]
    packet_key = (
        first.ball_device_id,
        first.ball_boot_id,
        first.ball_radio_sequence,
        first.payload_digest,
    )
    expected_ball_id = context.device_to_ball.get(first.ball_device_id)
    if expected_ball_id is None:
        return _rejected("ball_device_is_not_registered")

    allowed = set(context.allowed_receiver_ids)
    by_receiver: dict[str, RadioReceptionObservation] = {}
    for observation in observations:
        if observation.event_type != "radio.packet_observed":
            return _rejected("unsupported_event_type")
        if observation.source_device_id not in allowed:
            return _rejected("receiver_is_not_registered")
        if observation.ball_id != expected_ball_id:
            return _rejected("ball_device_mapping_mismatch")
        if (
            observation.ball_device_id,
            observation.ball_boot_id,
            observation.ball_radio_sequence,
            observation.payload_digest,
        ) != packet_key:
            return _rejected("observations_do_not_describe_one_ball_packet")
        if observation.tx_power_dbm != first.tx_power_dbm:
            return _rejected("reported_tx_power_is_inconsistent")
        prior = by_receiver.get(observation.source_device_id)
        if prior is not None:
            if prior != observation:
                return _rejected("receiver_reported_packet_more_than_once")
            continue
        by_receiver[observation.source_device_id] = observation

    unique = tuple(by_receiver.values())
    receive_times = [item.edge_received_ns for item in unique]
    receive_span_ns = max(receive_times) - min(receive_times)
    if receive_span_ns > context.maximum_receive_span_ns:
        return _rejected("receiver_observations_exceed_aggregation_window")

    strongest = max(unique, key=lambda item: (item.rssi_dbm, item.source_device_id))
    receiver_ids = tuple(sorted(by_receiver))
    receiver_count = len(receiver_ids)
    status = "accepted" if receiver_count >= context.minimum_receivers else "observed"
    reason = (
        "receiver_diversity_quorum_met"
        if status == "accepted"
        else "additional_receiver_required"
    )
    path_losses = [item.tx_power_dbm - item.rssi_dbm for item in unique]
    return MultiReceiverDecision(
        status=status,
        reason=reason,
        ball_id=expected_ball_id,
        ball_device_id=first.ball_device_id,
        ball_boot_id=first.ball_boot_id,
        ball_radio_sequence=first.ball_radio_sequence,
        payload_digest=first.payload_digest,
        tx_power_dbm=first.tx_power_dbm,
        receiver_count=receiver_count,
        receiver_ids=receiver_ids,
        strongest_receiver_id=strongest.source_device_id,
        strongest_rssi_dbm=strongest.rssi_dbm,
        median_path_loss_db=float(statistics.median(path_losses)),
        receive_span_ns=receive_span_ns,
    )
