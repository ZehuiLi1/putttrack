"""Research-only RF profiles; deployment is gated by FTO and RF measurements."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class BallRadioState(str, Enum):
    SHIPPING = "shipping"
    IDLE = "idle"
    TEE_NEAR = "tee_near"
    ACTIVE = "active"
    SERVICE = "service"


@dataclass(frozen=True)
class RadioProfile:
    enabled: bool
    tx_power_dbm: int | None
    advertising_interval_min_ms: int | None
    advertising_interval_max_ms: int | None
    event_repetitions: int
    event_repeat_window_ms: int
    rationale: str
    research_only: bool = True


_RESEARCH_PROFILES = {
    BallRadioState.SHIPPING: RadioProfile(
        enabled=False,
        tx_power_dbm=None,
        advertising_interval_min_ms=None,
        advertising_interval_max_ms=None,
        event_repetitions=0,
        event_repeat_window_ms=0,
        rationale="radio_off_until_explicit_service_or_assignment_wake",
    ),
    BallRadioState.IDLE: RadioProfile(
        enabled=True,
        tx_power_dbm=-10,
        advertising_interval_min_ms=2_000,
        advertising_interval_max_ms=2_500,
        event_repetitions=1,
        event_repeat_window_ms=0,
        rationale="slow_low_power_discovery_while_motion_sentinel_remains_armed",
    ),
    BallRadioState.TEE_NEAR: RadioProfile(
        enabled=True,
        tx_power_dbm=-10,
        advertising_interval_min_ms=100,
        advertising_interval_max_ms=150,
        event_repetitions=2,
        event_repeat_window_ms=80,
        rationale="fast_low_power_traffic_only_after_independent_near_tee_confirmation",
    ),
    BallRadioState.ACTIVE: RadioProfile(
        enabled=True,
        tx_power_dbm=0,
        advertising_interval_min_ms=100,
        advertising_interval_max_ms=150,
        event_repetitions=3,
        event_repeat_window_ms=120,
        rationale="bounded_research_coverage_during_measured_motion",
    ),
    BallRadioState.SERVICE: RadioProfile(
        enabled=True,
        tx_power_dbm=0,
        advertising_interval_min_ms=100,
        advertising_interval_max_ms=150,
        event_repetitions=1,
        event_repeat_window_ms=0,
        rationale="reliable_commissioning_diagnostics_and_signed_ota",
    ),
}


def research_radio_profile(state: BallRadioState | str) -> RadioProfile:
    """Return a bounded proposal, never an authorization to change live RF."""

    try:
        normalized = state if isinstance(state, BallRadioState) else BallRadioState(state)
    except ValueError as exc:
        raise ValueError(f"unsupported Ball radio state {state!r}") from exc
    return _RESEARCH_PROFILES[normalized]
