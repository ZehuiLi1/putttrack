"""Fail-closed NFC-gated Ball activation and per-hole lease policy.

NFC establishes proximity only.  This module deliberately does not implement
Bluetooth pairing or cryptography: callers may authorize a pending touch only
after a separate production credential verifier has authenticated the physical
Ball and controller.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import secrets
from typing import Any, Callable, Iterable, Mapping

from putttrack.tag import TagIdentityError, normalize_device_id


class ActivationError(ValueError):
    """Raised for malformed policy configuration or invalid authority changes."""


class ActivationStatus(str, Enum):
    REJECTED = "rejected"
    PENDING = "pending"
    ACTIVE = "active"
    RELEASED = "released"


class BallPowerDirective(str, Enum):
    SYSTEM_OFF = "system_off"
    ACTIVATION_PENDING = "activation_pending"
    ACTIVE = "active"
    ACTIVE_IDLE = "active_idle"


@dataclass(frozen=True)
class ReaderBinding:
    reader_id: str
    hole_id: str
    enabled: bool = True

    def __post_init__(self) -> None:
        _non_empty(self.reader_id, "reader_id")
        _non_empty(self.hole_id, "hole_id")


@dataclass(frozen=True)
class VerifiedBallAuthorization:
    """Result supplied by a credential verifier outside this policy module.

    ``verified=True`` must never be inferred from NFC identity, BLE address or
    Just Works link encryption alone.
    """

    controller_id: str
    device_id: str
    request_id: str
    verified: bool

    def __post_init__(self) -> None:
        _non_empty(self.controller_id, "controller_id")
        _non_empty(self.request_id, "request_id")
        object.__setattr__(self, "device_id", _device_id(self.device_id))


@dataclass(frozen=True)
class AuthoritativeHoleEnd:
    """Trusted internal Edge event allowed to release a matching lease."""

    event_id: str
    semantic_type: str
    session_id: str
    hole_id: str
    ball_id: str
    epoch: int

    def __post_init__(self) -> None:
        for field in ("event_id", "semantic_type", "session_id", "hole_id", "ball_id"):
            _non_empty(getattr(self, field), field)
        if isinstance(self.epoch, bool) or not isinstance(self.epoch, int) or self.epoch <= 0:
            raise ActivationError("epoch must be a positive integer")


@dataclass(frozen=True)
class PendingActivation:
    token: str
    reader_id: str
    hole_id: str
    session_id: str
    ball_id: str
    device_id: str
    created_at_ms: int
    expires_at_ms: int


@dataclass(frozen=True)
class HoleActivationLease:
    session_id: str
    hole_id: str
    ball_id: str
    device_id: str
    epoch: int
    activated_at_ms: int
    hard_expires_at_ms: int
    last_motion_at_ms: int
    last_authority_contact_at_ms: int
    controller_id: str


@dataclass(frozen=True)
class ActivationDecision:
    status: ActivationStatus
    reason: str
    power_directive: BallPowerDirective
    pending: PendingActivation | None = None
    lease: HoleActivationLease | None = None


@dataclass(frozen=True)
class ActivationTiming:
    pending_timeout_ms: int = 10_000
    active_idle_after_ms: int = 30_000
    authority_offline_ms: int = 120_000
    inactive_system_off_ms: int = 1_800_000
    maximum_activation_ms: int = 14_400_000

    def __post_init__(self) -> None:
        for name in (
            "pending_timeout_ms",
            "active_idle_after_ms",
            "authority_offline_ms",
            "inactive_system_off_ms",
            "maximum_activation_ms",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ActivationError(f"{name} must be a positive integer")
        if self.maximum_activation_ms <= self.active_idle_after_ms:
            raise ActivationError(
                "maximum_activation_ms must exceed active_idle_after_ms"
            )


def _non_empty(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ActivationError(f"{field} must be non-empty")
    return value.strip()


def _timestamp(value: int, field: str = "now_ms") -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ActivationError(f"{field} must be a non-negative integer")
    return value


def _device_id(value: str) -> str:
    try:
        return normalize_device_id(value)
    except TagIdentityError as exc:
        raise ActivationError(str(exc)) from exc


class HoleActivationAuthority:
    """Venue Edge authority for one active Ball per ordinary hole.

    The state is intentionally small enough to persist transactionally in a
    production Edge database.  This in-memory form is the deterministic policy
    reference used by the vertical slice and fault tests.
    """

    def __init__(
        self,
        *,
        readers: Iterable[ReaderBinding],
        device_to_ball: Mapping[str, str],
        timing: ActivationTiming | None = None,
        token_factory: Callable[[], str] | None = None,
    ) -> None:
        reader_items = tuple(readers)
        if not reader_items:
            raise ActivationError("at least one reader binding is required")
        if len({item.reader_id for item in reader_items}) != len(reader_items):
            raise ActivationError("reader IDs must be unique")
        if len({item.hole_id for item in reader_items}) != len(reader_items):
            raise ActivationError("each ordinary hole must have one activation reader")
        self._readers = {item.reader_id: item for item in reader_items}

        normalized_inventory: dict[str, str] = {}
        for raw_device_id, raw_ball_id in device_to_ball.items():
            device_id = _device_id(raw_device_id)
            ball_id = _non_empty(raw_ball_id, "ball_id")
            if device_id in normalized_inventory:
                raise ActivationError("device IDs must be unique")
            normalized_inventory[device_id] = ball_id
        if not normalized_inventory:
            raise ActivationError("at least one Ball device is required")
        if len(set(normalized_inventory.values())) != len(normalized_inventory):
            raise ActivationError("each Ball must map to one device")
        self._device_to_ball = normalized_inventory

        self.timing = timing or ActivationTiming()
        self._token_factory = token_factory or (lambda: secrets.token_hex(16))
        self._session_balls: dict[str, frozenset[str]] = {}
        self._ball_session: dict[str, str] = {}
        self._eligible_by_hole: dict[str, frozenset[str]] = {}
        self._pending_by_token: dict[str, PendingActivation] = {}
        self._pending_token_by_ball: dict[str, str] = {}
        self._active_by_hole: dict[str, HoleActivationLease] = {}
        self._active_by_ball: dict[str, HoleActivationLease] = {}
        self._epoch_by_hole: dict[str, int] = {}
        self._completed_tokens: dict[str, HoleActivationLease] = {}

    @property
    def active_count(self) -> int:
        return len(self._active_by_hole)

    @property
    def active_leases(self) -> tuple[HoleActivationLease, ...]:
        return tuple(self._active_by_hole[key] for key in sorted(self._active_by_hole))

    def register_session(self, session_id: str, ball_ids: Iterable[str]) -> None:
        session_id = _non_empty(session_id, "session_id")
        normalized = tuple(_non_empty(item, "ball_id") for item in ball_ids)
        if not normalized or len(set(normalized)) != len(normalized):
            raise ActivationError("session Ball IDs must be non-empty and unique")
        inventory_balls = set(self._device_to_ball.values())
        if any(item not in inventory_balls for item in normalized):
            raise ActivationError("session contains an unregistered Ball")
        if session_id in self._session_balls:
            if self._session_balls[session_id] == frozenset(normalized):
                return
            raise ActivationError("session is already registered with different Balls")
        for ball_id in normalized:
            owner = self._ball_session.get(ball_id)
            if owner is not None and owner != session_id:
                raise ActivationError("Ball is already assigned to another session")
        self._session_balls[session_id] = frozenset(normalized)
        for ball_id in normalized:
            self._ball_session[ball_id] = session_id

    def expect_ball(self, *, hole_id: str, session_id: str, ball_id: str) -> None:
        """Convenience wrapper for a hole with exactly one eligible Ball."""

        self.allow_balls(
            hole_id=hole_id, session_id=session_id, ball_ids=(ball_id,)
        )

    def allow_balls(
        self, *, hole_id: str, session_id: str, ball_ids: Iterable[str]
    ) -> None:
        """Convenience wrapper for eligible Balls from one session."""

        session_id = _non_empty(session_id, "session_id")
        normalized = tuple(_non_empty(item, "ball_id") for item in ball_ids)
        if not normalized or len(set(normalized)) != len(normalized):
            raise ActivationError("eligible Ball IDs must be non-empty and unique")
        assigned = self._session_balls.get(session_id, frozenset())
        if any(ball_id not in assigned for ball_id in normalized):
            raise ActivationError("eligible Ball is not assigned to the session")
        self.allow_active_balls(hole_id=hole_id, ball_ids=normalized)

    def allow_active_balls(self, *, hole_id: str, ball_ids: Iterable[str]) -> None:
        """Publish eligible open-session Balls, including different sessions."""

        hole_id = _non_empty(hole_id, "hole_id")
        normalized = tuple(_non_empty(item, "ball_id") for item in ball_ids)
        if not normalized or len(set(normalized)) != len(normalized):
            raise ActivationError("eligible Ball IDs must be non-empty and unique")
        if hole_id not in {item.hole_id for item in self._readers.values()}:
            raise ActivationError("hole has no activation reader")
        if any(ball_id not in self._ball_session for ball_id in normalized):
            raise ActivationError("eligible Ball has no active session assignment")
        active = self._active_by_hole.get(hole_id)
        if active is not None and active.ball_id not in normalized:
            raise ActivationError("hole must release its active Ball before the next turn")
        self._eligible_by_hole[hole_id] = frozenset(normalized)

    def observe_nfc_touch(
        self, *, reader_id: str, device_id: str, now_ms: int
    ) -> ActivationDecision:
        """Create an untrusted, time-bounded activation request from NFC."""

        reader_id = _non_empty(reader_id, "reader_id")
        device_id = _device_id(device_id)
        now_ms = _timestamp(now_ms)
        reader = self._readers.get(reader_id)
        if reader is None:
            return self._rejected("reader_not_registered")
        if not reader.enabled:
            return self._rejected("reader_disabled")
        ball_id = self._device_to_ball.get(device_id)
        if ball_id is None:
            return self._rejected("device_not_registered")
        eligibility = self._eligible_by_hole.get(reader.hole_id)
        if eligibility is None:
            return self._rejected("hole_has_no_eligible_turn")
        if ball_id not in eligibility:
            return self._rejected("ball_is_not_eligible_for_hole")
        session_id = self._ball_session[ball_id]
        active_hole = self._active_by_hole.get(reader.hole_id)
        if active_hole is not None:
            if active_hole.ball_id == ball_id and active_hole.session_id == session_id:
                return ActivationDecision(
                    ActivationStatus.ACTIVE,
                    "already_active",
                    self.power_directive(ball_id, now_ms=now_ms),
                    lease=active_hole,
                )
            return self._rejected("hole_already_has_active_ball")
        active_ball = self._active_by_ball.get(ball_id)
        if active_ball is not None:
            return self._rejected("ball_is_active_on_another_hole")

        prior_token = self._pending_token_by_ball.get(ball_id)
        if prior_token is not None:
            prior = self._pending_by_token.get(prior_token)
            if prior is not None and now_ms < prior.expires_at_ms:
                return ActivationDecision(
                    ActivationStatus.PENDING,
                    "activation_already_pending",
                    BallPowerDirective.ACTIVATION_PENDING,
                    pending=prior,
                )
            self._remove_pending(prior_token)

        token = _non_empty(self._token_factory(), "activation token")
        if token in self._pending_by_token or token in self._completed_tokens:
            raise ActivationError("activation token factory returned a duplicate")
        pending = PendingActivation(
            token=token,
            reader_id=reader.reader_id,
            hole_id=reader.hole_id,
            session_id=session_id,
            ball_id=ball_id,
            device_id=device_id,
            created_at_ms=now_ms,
            expires_at_ms=now_ms + self.timing.pending_timeout_ms,
        )
        self._pending_by_token[token] = pending
        self._pending_token_by_ball[ball_id] = token
        return ActivationDecision(
            ActivationStatus.PENDING,
            "credential_verification_required",
            BallPowerDirective.ACTIVATION_PENDING,
            pending=pending,
        )

    def authorize_activation(
        self,
        *,
        token: str,
        authorization: VerifiedBallAuthorization,
        now_ms: int,
    ) -> ActivationDecision:
        """Issue a hole lease only after a separate credential verifier passes."""

        token = _non_empty(token, "activation token")
        now_ms = _timestamp(now_ms)
        completed = self._completed_tokens.get(token)
        if completed is not None:
            active = self._active_by_ball.get(completed.ball_id)
            if active != completed:
                return self._rejected("activation_token_already_consumed")
            return ActivationDecision(
                ActivationStatus.ACTIVE,
                "activation_already_authorized",
                self.power_directive(completed.ball_id, now_ms=now_ms),
                lease=completed,
            )
        pending = self._pending_by_token.get(token)
        if pending is None:
            return self._rejected("activation_request_not_found")
        if now_ms >= pending.expires_at_ms:
            self._remove_pending(token)
            return self._rejected("activation_request_expired")
        if not authorization.verified:
            return self._rejected("ball_credential_not_verified")
        if authorization.device_id != pending.device_id:
            return self._rejected("verified_device_does_not_match_nfc_touch")
        eligibility = self._eligible_by_hole.get(pending.hole_id)
        if (
            eligibility is None
            or pending.ball_id not in eligibility
            or self._ball_session.get(pending.ball_id) != pending.session_id
        ):
            self._remove_pending(token)
            return self._rejected("eligible_turn_changed")
        if pending.hole_id in self._active_by_hole:
            return self._rejected("hole_already_has_active_ball")
        if pending.ball_id in self._active_by_ball:
            return self._rejected("ball_is_active_on_another_hole")

        epoch = self._epoch_by_hole.get(pending.hole_id, 0) + 1
        self._epoch_by_hole[pending.hole_id] = epoch
        lease = HoleActivationLease(
            session_id=pending.session_id,
            hole_id=pending.hole_id,
            ball_id=pending.ball_id,
            device_id=pending.device_id,
            epoch=epoch,
            activated_at_ms=now_ms,
            hard_expires_at_ms=now_ms + self.timing.maximum_activation_ms,
            last_motion_at_ms=now_ms,
            last_authority_contact_at_ms=now_ms,
            controller_id=authorization.controller_id,
        )
        self._active_by_hole[lease.hole_id] = lease
        self._active_by_ball[lease.ball_id] = lease
        self._completed_tokens[token] = lease
        self._remove_pending(token)
        return ActivationDecision(
            ActivationStatus.ACTIVE,
            "activation_authorized",
            BallPowerDirective.ACTIVE,
            lease=lease,
        )

    def note_motion(
        self,
        *,
        ball_id: str,
        hole_id: str,
        epoch: int,
        authorization: VerifiedBallAuthorization,
        now_ms: int,
    ) -> ActivationDecision:
        return self._refresh_lease(
            ball_id=ball_id,
            hole_id=hole_id,
            epoch=epoch,
            authorization=authorization,
            now_ms=now_ms,
            motion=True,
        )

    def heartbeat(
        self,
        *,
        ball_id: str,
        hole_id: str,
        epoch: int,
        authorization: VerifiedBallAuthorization,
        now_ms: int,
    ) -> ActivationDecision:
        return self._refresh_lease(
            ball_id=ball_id,
            hole_id=hole_id,
            epoch=epoch,
            authorization=authorization,
            now_ms=now_ms,
            motion=False,
        )

    def end_activation(
        self,
        *,
        ball_id: str,
        hole_id: str,
        epoch: int,
        authorization: VerifiedBallAuthorization,
        now_ms: int,
        reason: str,
    ) -> ActivationDecision:
        now_ms = _timestamp(now_ms)
        reason = _non_empty(reason, "reason")
        lease = self._matching_lease(ball_id=ball_id, hole_id=hole_id, epoch=epoch)
        if lease is None:
            return self._rejected("active_lease_not_found_or_stale_epoch")
        proof_error = self._authorization_error(authorization, lease)
        if proof_error is not None:
            return self._rejected(proof_error)
        self._release(lease)
        return ActivationDecision(
            ActivationStatus.RELEASED,
            f"explicit_end:{reason}",
            BallPowerDirective.SYSTEM_OFF,
            lease=lease,
        )

    def end_from_authoritative_event(
        self, *, event: AuthoritativeHoleEnd, now_ms: int
    ) -> ActivationDecision:
        """Release only when a trusted semantic event matches the exact lease."""

        _timestamp(now_ms)
        allowed = {
            "cup.confirmed",
            "operator.end",
            "round.complete",
            "session.abandoned",
        }
        if event.semantic_type not in allowed:
            return self._rejected("semantic_event_cannot_end_activation")
        lease = self._matching_lease(
            ball_id=event.ball_id, hole_id=event.hole_id, epoch=event.epoch
        )
        if lease is None or lease.session_id != event.session_id:
            return self._rejected("semantic_end_does_not_match_active_lease")
        self._release(lease)
        return ActivationDecision(
            ActivationStatus.RELEASED,
            f"authoritative_end:{event.semantic_type}",
            BallPowerDirective.SYSTEM_OFF,
            lease=lease,
        )

    def sweep(self, *, now_ms: int) -> tuple[ActivationDecision, ...]:
        """Expire pending touches and fail-safe stale/hard-limit leases."""

        now_ms = _timestamp(now_ms)
        decisions: list[ActivationDecision] = []
        for token, pending in tuple(self._pending_by_token.items()):
            if now_ms >= pending.expires_at_ms:
                self._remove_pending(token)
                decisions.append(
                    ActivationDecision(
                        ActivationStatus.RELEASED,
                        "pending_timeout",
                        BallPowerDirective.SYSTEM_OFF,
                        pending=pending,
                    )
                )
        for lease in tuple(self._active_by_hole.values()):
            hard_expired = now_ms >= lease.hard_expires_at_ms
            inactive = (
                now_ms - lease.last_motion_at_ms
                >= self.timing.inactive_system_off_ms
            )
            authority_offline = (
                now_ms - lease.last_authority_contact_at_ms
                >= self.timing.authority_offline_ms
            )
            if hard_expired or (inactive and authority_offline):
                self._release(lease)
                decisions.append(
                    ActivationDecision(
                        ActivationStatus.RELEASED,
                        (
                            "maximum_activation_timeout"
                            if hard_expired
                            else "inactive_and_authority_offline"
                        ),
                        BallPowerDirective.SYSTEM_OFF,
                        lease=lease,
                    )
                )
        return tuple(decisions)

    def power_directive(self, ball_id: str, *, now_ms: int) -> BallPowerDirective:
        ball_id = _non_empty(ball_id, "ball_id")
        now_ms = _timestamp(now_ms)
        lease = self._active_by_ball.get(ball_id)
        if lease is not None:
            if now_ms - lease.last_motion_at_ms >= self.timing.active_idle_after_ms:
                return BallPowerDirective.ACTIVE_IDLE
            return BallPowerDirective.ACTIVE
        token = self._pending_token_by_ball.get(ball_id)
        pending = self._pending_by_token.get(token or "")
        if pending is not None and now_ms < pending.expires_at_ms:
            return BallPowerDirective.ACTIVATION_PENDING
        return BallPowerDirective.SYSTEM_OFF

    def _refresh_lease(
        self,
        *,
        ball_id: str,
        hole_id: str,
        epoch: int,
        authorization: VerifiedBallAuthorization,
        now_ms: int,
        motion: bool,
    ) -> ActivationDecision:
        now_ms = _timestamp(now_ms)
        lease = self._matching_lease(ball_id=ball_id, hole_id=hole_id, epoch=epoch)
        if lease is None:
            return self._rejected("active_lease_not_found_or_stale_epoch")
        proof_error = self._authorization_error(authorization, lease)
        if proof_error is not None:
            return self._rejected(proof_error)
        refreshed = HoleActivationLease(
            session_id=lease.session_id,
            hole_id=lease.hole_id,
            ball_id=lease.ball_id,
            device_id=lease.device_id,
            epoch=lease.epoch,
            activated_at_ms=lease.activated_at_ms,
            hard_expires_at_ms=lease.hard_expires_at_ms,
            last_motion_at_ms=now_ms if motion else lease.last_motion_at_ms,
            last_authority_contact_at_ms=now_ms,
            controller_id=authorization.controller_id,
        )
        self._active_by_hole[refreshed.hole_id] = refreshed
        self._active_by_ball[refreshed.ball_id] = refreshed
        return ActivationDecision(
            ActivationStatus.ACTIVE,
            "authenticated_motion" if motion else "authenticated_heartbeat",
            self.power_directive(refreshed.ball_id, now_ms=now_ms),
            lease=refreshed,
        )

    def _matching_lease(
        self, *, ball_id: str, hole_id: str, epoch: int
    ) -> HoleActivationLease | None:
        ball_id = _non_empty(ball_id, "ball_id")
        hole_id = _non_empty(hole_id, "hole_id")
        if isinstance(epoch, bool) or not isinstance(epoch, int) or epoch <= 0:
            raise ActivationError("epoch must be a positive integer")
        lease = self._active_by_ball.get(ball_id)
        if lease is None or lease.hole_id != hole_id or lease.epoch != epoch:
            return None
        return lease

    @staticmethod
    def _authorization_error(
        authorization: VerifiedBallAuthorization, lease: HoleActivationLease
    ) -> str | None:
        if not authorization.verified:
            return "ball_credential_not_verified"
        if authorization.device_id != lease.device_id:
            return "verified_device_does_not_match_active_lease"
        return None

    @staticmethod
    def _rejected(reason: str) -> ActivationDecision:
        return ActivationDecision(
            ActivationStatus.REJECTED,
            reason,
            BallPowerDirective.SYSTEM_OFF,
        )

    def _remove_pending(self, token: str) -> None:
        pending = self._pending_by_token.pop(token, None)
        if pending is not None and self._pending_token_by_ball.get(pending.ball_id) == token:
            self._pending_token_by_ball.pop(pending.ball_id, None)

    def _release(self, lease: HoleActivationLease) -> None:
        if self._active_by_hole.get(lease.hole_id) == lease:
            self._active_by_hole.pop(lease.hole_id, None)
        if self._active_by_ball.get(lease.ball_id) == lease:
            self._active_by_ball.pop(lease.ball_id, None)


def activation_authority_from_dict(
    data: Mapping[str, Any],
    *,
    device_to_ball: Mapping[str, str],
    token_factory: Callable[[], str] | None = None,
) -> HoleActivationAuthority:
    """Load the fixed installation mapping; no player-facing secrets exist here."""

    if not isinstance(data, Mapping):
        raise ActivationError("activation config must be an object")
    unknown = set(data) - {"readers", "timing"}
    if unknown:
        raise ActivationError(f"unknown activation config fields: {sorted(unknown)!r}")

    raw_readers = data.get("readers")
    if not isinstance(raw_readers, list) or not raw_readers:
        raise ActivationError("readers must be a non-empty list")
    readers: list[ReaderBinding] = []
    for raw in raw_readers:
        if not isinstance(raw, Mapping):
            raise ActivationError("each reader binding must be an object")
        reader_unknown = set(raw) - {"reader_id", "hole_id", "enabled"}
        if reader_unknown:
            raise ActivationError(
                f"unknown reader binding fields: {sorted(reader_unknown)!r}"
            )
        enabled = raw.get("enabled", True)
        if not isinstance(enabled, bool):
            raise ActivationError("reader enabled must be boolean")
        readers.append(
            ReaderBinding(
                reader_id=raw.get("reader_id"),
                hole_id=raw.get("hole_id"),
                enabled=enabled,
            )
        )

    raw_timing = data.get("timing", {})
    if not isinstance(raw_timing, Mapping):
        raise ActivationError("timing must be an object")
    timing_fields = {
        "pending_timeout_ms",
        "active_idle_after_ms",
        "authority_offline_ms",
        "inactive_system_off_ms",
        "maximum_activation_ms",
    }
    timing_unknown = set(raw_timing) - timing_fields
    if timing_unknown:
        raise ActivationError(
            f"unknown activation timing fields: {sorted(timing_unknown)!r}"
        )
    defaults = ActivationTiming()
    timing = ActivationTiming(
        **{
            field: raw_timing.get(field, getattr(defaults, field))
            for field in timing_fields
        }
    )
    return HoleActivationAuthority(
        readers=readers,
        device_to_ball=device_to_ball,
        timing=timing,
        token_factory=token_factory,
    )
