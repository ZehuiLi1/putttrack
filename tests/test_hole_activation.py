from __future__ import annotations

import unittest

from putttrack.venue import (
    ActivationError,
    ActivationStatus,
    ActivationTiming,
    AuthoritativeHoleEnd,
    BallPowerDirective,
    HoleActivationAuthority,
    ReaderBinding,
    VerifiedBallAuthorization,
    activation_authority_from_dict,
)


DEVICE_1 = "0011223344556677"
DEVICE_2 = "8899aabbccddeeff"


class TokenFactory:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self) -> str:
        self.value += 1
        return f"touch-{self.value}"


def proof(device_id: str = DEVICE_1, *, verified: bool = True):
    return VerifiedBallAuthorization(
        controller_id="edge-controller-1",
        device_id=device_id,
        request_id="auth-request-1",
        verified=verified,
    )


def authority(*, timing: ActivationTiming | None = None) -> HoleActivationAuthority:
    result = HoleActivationAuthority(
        readers=(
            ReaderBinding("tee-reader-01", "H01"),
            ReaderBinding("tee-reader-02", "H02"),
        ),
        device_to_ball={DEVICE_1: "ball-01", DEVICE_2: "ball-02"},
        timing=timing,
        token_factory=TokenFactory(),
    )
    result.register_session("session-1", ("ball-01", "ball-02"))
    result.expect_ball(hole_id="H01", session_id="session-1", ball_id="ball-01")
    return result


class HoleActivationTests(unittest.TestCase):
    def test_fixed_reader_mapping_loads_from_simple_config(self) -> None:
        policy = activation_authority_from_dict(
            {
                "readers": [
                    {"reader_id": "tee-reader-01", "hole_id": "H01"},
                    {"reader_id": "tee-reader-02", "hole_id": "H02"},
                ],
                "timing": {"pending_timeout_ms": 5_000},
            },
            device_to_ball={DEVICE_1: "ball-01"},
            token_factory=TokenFactory(),
        )
        self.assertEqual(policy.timing.pending_timeout_ms, 5_000)
        self.assertEqual(policy.timing.active_idle_after_ms, 30_000)

        with self.assertRaisesRegex(ActivationError, "unknown activation"):
            activation_authority_from_dict(
                {
                    "readers": [
                        {"reader_id": "tee-reader-01", "hole_id": "H01"}
                    ],
                    "password": "players-must-never-configure-this",
                },
                device_to_ball={DEVICE_1: "ball-01"},
            )

    def test_nfc_is_pending_until_matching_device_credential_is_verified(self) -> None:
        policy = authority()
        pending = policy.observe_nfc_touch(
            reader_id="tee-reader-01", device_id=DEVICE_1, now_ms=100
        )

        self.assertEqual(pending.status, ActivationStatus.PENDING)
        self.assertEqual(pending.reason, "credential_verification_required")
        self.assertEqual(policy.active_count, 0)
        self.assertEqual(
            pending.power_directive, BallPowerDirective.ACTIVATION_PENDING
        )

        unverified = policy.authorize_activation(
            token=pending.pending.token,
            authorization=proof(verified=False),
            now_ms=200,
        )
        self.assertEqual(unverified.status, ActivationStatus.REJECTED)
        self.assertEqual(unverified.reason, "ball_credential_not_verified")

        cloned_id = policy.authorize_activation(
            token=pending.pending.token,
            authorization=proof(DEVICE_2),
            now_ms=300,
        )
        self.assertEqual(cloned_id.status, ActivationStatus.REJECTED)
        self.assertEqual(
            cloned_id.reason, "verified_device_does_not_match_nfc_touch"
        )

        active = policy.authorize_activation(
            token=pending.pending.token,
            authorization=proof(),
            now_ms=400,
        )
        self.assertEqual(active.status, ActivationStatus.ACTIVE)
        self.assertEqual(active.lease.epoch, 1)
        self.assertEqual(active.lease.hole_id, "H01")
        self.assertEqual(policy.active_count, 1)

    def test_wrong_ball_unknown_reader_and_unexpected_hole_fail_closed(self) -> None:
        policy = authority()
        unknown_reader = policy.observe_nfc_touch(
            reader_id="foreign-reader", device_id=DEVICE_1, now_ms=0
        )
        wrong_ball = policy.observe_nfc_touch(
            reader_id="tee-reader-01", device_id=DEVICE_2, now_ms=0
        )
        no_turn = policy.observe_nfc_touch(
            reader_id="tee-reader-02", device_id=DEVICE_2, now_ms=0
        )

        self.assertEqual(unknown_reader.reason, "reader_not_registered")
        self.assertEqual(wrong_ball.reason, "ball_is_not_eligible_for_hole")
        self.assertEqual(no_turn.reason, "hole_has_no_eligible_turn")
        self.assertEqual(policy.active_count, 0)

    def test_any_unfinished_assigned_ball_may_take_the_free_hole(self) -> None:
        policy = authority()
        policy.allow_balls(
            hole_id="H01",
            session_id="session-1",
            ball_ids=("ball-01", "ball-02"),
        )
        pending = policy.observe_nfc_touch(
            reader_id="tee-reader-01", device_id=DEVICE_2, now_ms=0
        )
        active = policy.authorize_activation(
            token=pending.pending.token,
            authorization=proof(DEVICE_2),
            now_ms=1,
        )
        self.assertEqual(active.status, ActivationStatus.ACTIVE)
        self.assertEqual(active.lease.ball_id, "ball-02")

        other = policy.observe_nfc_touch(
            reader_id="tee-reader-01", device_id=DEVICE_1, now_ms=2
        )
        self.assertEqual(other.status, ActivationStatus.REJECTED)
        self.assertEqual(other.reason, "hole_already_has_active_ball")

    def test_hole_may_accept_eligible_balls_from_different_sessions(self) -> None:
        policy = HoleActivationAuthority(
            readers=(ReaderBinding("tee-reader-01", "H01"),),
            device_to_ball={DEVICE_1: "ball-01", DEVICE_2: "ball-02"},
            token_factory=TokenFactory(),
        )
        policy.register_session("session-red", ("ball-01",))
        policy.register_session("session-blue", ("ball-02",))
        policy.allow_active_balls(hole_id="H01", ball_ids=("ball-01", "ball-02"))

        pending = policy.observe_nfc_touch(
            reader_id="tee-reader-01", device_id=DEVICE_2, now_ms=0
        )
        active = policy.authorize_activation(
            token=pending.pending.token,
            authorization=proof(DEVICE_2),
            now_ms=1,
        )
        self.assertEqual(active.status, ActivationStatus.ACTIVE)
        self.assertEqual(active.lease.session_id, "session-blue")
        self.assertEqual(active.lease.ball_id, "ball-02")

    def test_one_ball_per_hole_and_one_hole_per_ball(self) -> None:
        policy = authority()
        pending = policy.observe_nfc_touch(
            reader_id="tee-reader-01", device_id=DEVICE_1, now_ms=0
        )
        active = policy.authorize_activation(
            token=pending.pending.token, authorization=proof(), now_ms=1
        )
        with self.assertRaisesRegex(ValueError, "release its active Ball"):
            policy.expect_ball(
                hole_id="H01", session_id="session-1", ball_id="ball-02"
            )

        policy.expect_ball(
            hole_id="H02", session_id="session-1", ball_id="ball-01"
        )
        cross_hole = policy.observe_nfc_touch(
            reader_id="tee-reader-02", device_id=DEVICE_1, now_ms=2
        )
        self.assertEqual(cross_hole.reason, "ball_is_active_on_another_hole")
        self.assertEqual(policy.active_count, 1)
        self.assertEqual(active.lease.hole_id, "H01")

    def test_explicit_end_enters_system_off_and_epoch_blocks_replay(self) -> None:
        policy = authority()
        pending = policy.observe_nfc_touch(
            reader_id="tee-reader-01", device_id=DEVICE_1, now_ms=0
        )
        first = policy.authorize_activation(
            token=pending.pending.token, authorization=proof(), now_ms=1
        )
        released = policy.end_activation(
            ball_id="ball-01",
            hole_id="H01",
            epoch=first.lease.epoch,
            authorization=proof(),
            now_ms=2,
            reason="cup_confirmed",
        )
        self.assertEqual(released.status, ActivationStatus.RELEASED)
        self.assertEqual(released.power_directive, BallPowerDirective.SYSTEM_OFF)

        consumed = policy.authorize_activation(
            token=pending.pending.token, authorization=proof(), now_ms=3
        )
        self.assertEqual(consumed.status, ActivationStatus.REJECTED)
        self.assertEqual(consumed.reason, "activation_token_already_consumed")

        second_pending = policy.observe_nfc_touch(
            reader_id="tee-reader-01", device_id=DEVICE_1, now_ms=4
        )
        second = policy.authorize_activation(
            token=second_pending.pending.token, authorization=proof(), now_ms=5
        )
        self.assertEqual(second.lease.epoch, 2)
        replay = policy.end_activation(
            ball_id="ball-01",
            hole_id="H01",
            epoch=first.lease.epoch,
            authorization=proof(),
            now_ms=6,
            reason="replayed_old_end",
        )
        self.assertEqual(replay.status, ActivationStatus.REJECTED)
        self.assertEqual(replay.reason, "active_lease_not_found_or_stale_epoch")
        self.assertEqual(policy.active_count, 1)

    def test_active_idle_is_not_system_off_during_normal_play(self) -> None:
        timing = ActivationTiming(
            pending_timeout_ms=1_000,
            active_idle_after_ms=10_000,
            authority_offline_ms=120_000,
            inactive_system_off_ms=1_800_000,
            maximum_activation_ms=14_400_000,
        )
        policy = authority(timing=timing)
        pending = policy.observe_nfc_touch(
            reader_id="tee-reader-01", device_id=DEVICE_1, now_ms=0
        )
        active = policy.authorize_activation(
            token=pending.pending.token, authorization=proof(), now_ms=1
        )
        self.assertEqual(
            policy.power_directive("ball-01", now_ms=10_001),
            BallPowerDirective.ACTIVE_IDLE,
        )

        heartbeat = policy.heartbeat(
            ball_id="ball-01",
            hole_id="H01",
            epoch=active.lease.epoch,
            authorization=proof(),
            now_ms=1_800_001,
        )
        self.assertEqual(heartbeat.status, ActivationStatus.ACTIVE)
        self.assertEqual(policy.sweep(now_ms=1_800_002), ())

        expired = policy.sweep(now_ms=1_920_001)
        self.assertEqual(len(expired), 1)
        self.assertEqual(expired[0].reason, "inactive_and_authority_offline")
        self.assertEqual(
            policy.power_directive("ball-01", now_ms=1_920_001),
            BallPowerDirective.SYSTEM_OFF,
        )

    def test_only_matching_authoritative_cup_event_ends_the_turn(self) -> None:
        policy = authority()
        pending = policy.observe_nfc_touch(
            reader_id="tee-reader-01", device_id=DEVICE_1, now_ms=0
        )
        active = policy.authorize_activation(
            token=pending.pending.token, authorization=proof(), now_ms=1
        )
        wrong_ball = policy.end_from_authoritative_event(
            event=AuthoritativeHoleEnd(
                event_id="cup-wrong",
                semantic_type="cup.confirmed",
                session_id="session-1",
                hole_id="H01",
                ball_id="ball-02",
                epoch=active.lease.epoch,
            ),
            now_ms=2,
        )
        self.assertEqual(wrong_ball.status, ActivationStatus.REJECTED)
        self.assertEqual(policy.active_count, 1)

        candidate = policy.end_from_authoritative_event(
            event=AuthoritativeHoleEnd(
                event_id="motion-only",
                semantic_type="motion.active",
                session_id="session-1",
                hole_id="H01",
                ball_id="ball-01",
                epoch=active.lease.epoch,
            ),
            now_ms=3,
        )
        self.assertEqual(candidate.reason, "semantic_event_cannot_end_activation")
        self.assertEqual(policy.active_count, 1)

        completed = policy.end_from_authoritative_event(
            event=AuthoritativeHoleEnd(
                event_id="cup-correct",
                semantic_type="cup.confirmed",
                session_id="session-1",
                hole_id="H01",
                ball_id="ball-01",
                epoch=active.lease.epoch,
            ),
            now_ms=4,
        )
        self.assertEqual(completed.status, ActivationStatus.RELEASED)
        self.assertEqual(completed.power_directive, BallPowerDirective.SYSTEM_OFF)
        self.assertEqual(policy.active_count, 0)

    def test_pending_touch_times_out_to_system_off(self) -> None:
        policy = authority(
            timing=ActivationTiming(
                pending_timeout_ms=1_000,
                active_idle_after_ms=10_000,
                authority_offline_ms=120_000,
                inactive_system_off_ms=1_800_000,
                maximum_activation_ms=14_400_000,
            )
        )
        pending = policy.observe_nfc_touch(
            reader_id="tee-reader-01", device_id=DEVICE_1, now_ms=10
        )
        expired = policy.sweep(now_ms=1_010)

        self.assertEqual(len(expired), 1)
        self.assertEqual(expired[0].reason, "pending_timeout")
        self.assertEqual(expired[0].pending.token, pending.pending.token)
        self.assertEqual(
            policy.power_directive("ball-01", now_ms=1_010),
            BallPowerDirective.SYSTEM_OFF,
        )

    def test_18_holes_bound_500_registered_balls_to_18_active_leases(self) -> None:
        devices = {f"{index:016x}": f"ball-{index:03d}" for index in range(1, 501)}
        policy = HoleActivationAuthority(
            readers=tuple(
                ReaderBinding(f"tee-reader-{index:02d}", f"H{index:02d}")
                for index in range(1, 19)
            ),
            device_to_ball=devices,
            token_factory=TokenFactory(),
        )
        active_balls = tuple(f"ball-{index:03d}" for index in range(1, 19))
        policy.register_session("venue-load", active_balls)

        for index in range(1, 19):
            hole_id = f"H{index:02d}"
            ball_id = f"ball-{index:03d}"
            device_id = f"{index:016x}"
            policy.expect_ball(
                hole_id=hole_id, session_id="venue-load", ball_id=ball_id
            )
            pending = policy.observe_nfc_touch(
                reader_id=f"tee-reader-{index:02d}",
                device_id=device_id,
                now_ms=index,
            )
            decision = policy.authorize_activation(
                token=pending.pending.token,
                authorization=proof(device_id),
                now_ms=100 + index,
            )
            self.assertEqual(decision.status, ActivationStatus.ACTIVE)

        self.assertEqual(policy.active_count, 18)
        self.assertEqual(len(policy.active_leases), 18)


if __name__ == "__main__":
    unittest.main()
