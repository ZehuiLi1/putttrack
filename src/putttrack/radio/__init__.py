"""Connectionless multi-receiver research primitives for no-CS PuttTrack."""

from .airtime import deterministic_repetition_offsets_ms
from .multi_receiver import (
    MultiReceiverContext,
    MultiReceiverDecision,
    aggregate_radio_receptions,
)
from .power_policy import (
    BallRadioState,
    RadioProfile,
    research_radio_profile,
)

__all__ = [
    "BallRadioState",
    "MultiReceiverContext",
    "MultiReceiverDecision",
    "RadioProfile",
    "aggregate_radio_receptions",
    "deterministic_repetition_offsets_ms",
    "research_radio_profile",
]
