from __future__ import annotations

import unittest

from putttrack.contracts import PhysicalSensorObservation
from putttrack.evidence import NoCsPhysicalEvidencePolicy, PhysicalEvidenceContext


def observation(
    event_id: str,
    *,
    sensor_kind: str,
    transition: str,
    source_device_id: str,
    source_boot_id: str = "boot-1",
    sequence: int = 1,
    source_monotonic_ns: int = 1_000_000_000,
    edge_received_ns: int = 1_010_000_000,
    ball_id: str | None = None,
    sensor_id: str | None = None,
    health: str = "ok",
    debounce_version: str | None = "debounce-v1",
    value=None,
    hole_id: str = "H01",
) -> PhysicalSensorObservation:
    return PhysicalSensorObservation(
        event_id=event_id,
        event_type="sensor.edge_observed",
        source_device_id=source_device_id,
        source_boot_id=source_boot_id,
        sequence=sequence,
        source_monotonic_ns=source_monotonic_ns,
        edge_received_ns=edge_received_ns,
        trace_id=f"trace-{event_id}",
        hole_id=hole_id,
        ball_id=ball_id,
        firmware_version="node-v0",
        sensor_id=sensor_id or f"sensor-{source_device_id}",
        sensor_kind=sensor_kind,
        transition=transition,
        value=value,
        health=health,
        debounce_version=debounce_version,
    )


def context(
    *,
    active_ball_id: str | None = None,
    active_player_id: str | None = None,
    active_player_state: str | None = None,
) -> PhysicalEvidenceContext:
    return PhysicalEvidenceContext(
        session_id="session-1",
        hole_id="H01",
        assigned_ball_ids=("b1", "b2"),
        active_ball_id=active_ball_id,
        active_player_id=active_player_id,
        active_player_state=active_player_state,
    )


class PhysicalEvidencePolicyTests(unittest.TestCase):
    def test_assigned_debounced_tee_presence_grants_authority(self) -> None:
        policy = NoCsPhysicalEvidencePolicy()
        edge = observation(
            "tee-1",
            sensor_kind="tee_presence",
            transition="occupied",
            source_device_id="tee-node",
            ball_id="b1",
            value=True,
        )

        decision = policy.evaluate(edge, context())

        self.assertEqual(decision.status, "accepted")
        self.assertTrue(decision.authority_granted)
        self.assertEqual(decision.semantic_type, "tee.presented")
        self.assertEqual(decision.evidence_event.ball_id, "b1")
        self.assertEqual(decision.evidence_event.raw_evidence_refs, ("tee-1",))
        self.assertIs(policy.evaluate(edge, context()), decision)

    def test_tee_requires_assignment_identity_health_and_debounce(self) -> None:
        cases = (
            ({"ball_id": None}, "ball_id_is_required"),
            ({"ball_id": "foreign"}, "ball_is_not_assigned_to_session"),
            ({"ball_id": "b1", "health": "fault"}, "sensor_health_is_not_ok"),
            (
                {"ball_id": "b1", "debounce_version": None},
                "debounce_version_is_required",
            ),
            (
                {"ball_id": "b1", "value": False},
                "transition_value_mismatch",
            ),
        )
        for index, (overrides, reason) in enumerate(cases):
            with self.subTest(reason=reason):
                edge = observation(
                    f"tee-invalid-{index}",
                    sensor_kind="tee_presence",
                    transition="occupied",
                    source_device_id=f"tee-node-{index}",
                    **overrides,
                )
                decision = NoCsPhysicalEvidencePolicy().evaluate(edge, context())
                self.assertEqual(decision.status, "rejected")
                self.assertEqual(decision.reason, reason)
                self.assertFalse(decision.authority_granted)

    def test_tee_cannot_replace_an_active_ball(self) -> None:
        edge = observation(
            "tee-busy",
            sensor_kind="tee_presence",
            transition="occupied",
            source_device_id="tee-node",
            ball_id="b2",
        )
        decision = NoCsPhysicalEvidencePolicy().evaluate(
            edge,
            context(
                active_ball_id="b1",
                active_player_id="p1",
                active_player_state="armed",
            ),
        )
        self.assertEqual(decision.status, "rejected")
        self.assertEqual(decision.reason, "hole_is_busy_with_another_ball")

    def test_cup_needs_entry_then_presence_within_window(self) -> None:
        policy = NoCsPhysicalEvidencePolicy()
        active = context(
            active_ball_id="b1",
            active_player_id="p1",
            active_player_state="playing",
        )
        entry = observation(
            "cup-entry-1",
            sensor_kind="cup_entry",
            transition="entered",
            source_device_id="cup-entry-node",
            ball_id="b1",
            edge_received_ns=2_000_000_000,
        )
        presence = observation(
            "cup-presence-1",
            sensor_kind="cup_presence",
            transition="occupied",
            source_device_id="cup-presence-node",
            ball_id="b1",
            edge_received_ns=2_600_000_000,
        )

        self.assertEqual(policy.evaluate(entry, active).status, "pending")
        decision = policy.evaluate(presence, active)

        self.assertEqual(decision.status, "accepted")
        self.assertEqual(decision.semantic_type, "cup.confirmed")
        self.assertEqual(
            decision.evidence_event.raw_evidence_refs,
            ("cup-entry-1", "cup-presence-1"),
        )

    def test_single_cup_presence_never_grants_authority(self) -> None:
        edge = observation(
            "cup-presence-only",
            sensor_kind="cup_presence",
            transition="occupied",
            source_device_id="cup-presence-node",
            ball_id="b1",
        )
        decision = NoCsPhysicalEvidencePolicy().evaluate(
            edge,
            context(
                active_ball_id="b1",
                active_player_id="p1",
                active_player_state="playing",
            ),
        )
        self.assertEqual(decision.status, "pending")
        self.assertEqual(decision.reason, "cup_entry_edge_required")
        self.assertFalse(decision.authority_granted)

    def test_cup_presence_requires_current_ball_identity(self) -> None:
        edge = observation(
            "cup-presence-without-id",
            sensor_kind="cup_presence",
            transition="occupied",
            source_device_id="cup-pn532-node",
        )
        decision = NoCsPhysicalEvidencePolicy().evaluate(
            edge,
            context(
                active_ball_id="b1",
                active_player_id="p1",
                active_player_state="playing",
            ),
        )
        self.assertEqual(decision.status, "rejected")
        self.assertEqual(decision.reason, "cup_presence_ball_id_is_required")

    def test_one_controller_may_report_two_independent_cup_sensors(self) -> None:
        policy = NoCsPhysicalEvidencePolicy()
        active = context(
            active_ball_id="b1",
            active_player_id="p1",
            active_player_state="playing",
        )
        entry = observation(
            "cup-combined-entry",
            sensor_kind="cup_entry",
            transition="entered",
            source_device_id="cup-controller",
            sensor_id="cup-optical-entry",
            sequence=1,
            edge_received_ns=2_000_000_000,
        )
        identity = observation(
            "cup-combined-nfc",
            sensor_kind="cup_presence",
            transition="occupied",
            source_device_id="cup-controller",
            sensor_id="cup-pn532-identity",
            sequence=2,
            source_monotonic_ns=1_100_000_000,
            edge_received_ns=2_500_000_000,
            ball_id="b1",
        )
        self.assertEqual(policy.evaluate(entry, active).status, "pending")
        decision = policy.evaluate(identity, active)
        self.assertEqual(decision.status, "accepted")
        self.assertEqual(decision.semantic_type, "cup.confirmed")

    def test_one_sensor_cannot_self_confirm_cup_completion(self) -> None:
        policy = NoCsPhysicalEvidencePolicy()
        active = context(
            active_ball_id="b1",
            active_player_id="p1",
            active_player_state="playing",
        )
        entry = observation(
            "cup-one-sensor-entry",
            sensor_kind="cup_entry",
            transition="entered",
            source_device_id="cup-controller",
            sensor_id="cup-shared-sensor",
            sequence=1,
            edge_received_ns=2_000_000_000,
        )
        identity = observation(
            "cup-one-sensor-presence",
            sensor_kind="cup_presence",
            transition="occupied",
            source_device_id="cup-controller",
            sensor_id="cup-shared-sensor",
            sequence=2,
            source_monotonic_ns=1_100_000_000,
            edge_received_ns=2_500_000_000,
            ball_id="b1",
        )
        policy.evaluate(entry, active)
        decision = policy.evaluate(identity, active)
        self.assertEqual(decision.status, "rejected")
        self.assertEqual(
            decision.reason, "cup_confirmation_requires_independent_sensor"
        )

    def test_cup_rejects_wrong_context_and_expired_pair(self) -> None:
        active = context(
            active_ball_id="b1",
            active_player_id="p1",
            active_player_state="playing",
        )
        wrong_ball = observation(
            "cup-wrong-ball",
            sensor_kind="cup_entry",
            transition="entered",
            source_device_id="cup-entry-wrong",
            ball_id="b2",
        )
        self.assertEqual(
            NoCsPhysicalEvidencePolicy().evaluate(wrong_ball, active).reason,
            "observation_is_not_for_active_ball",
        )

        policy = NoCsPhysicalEvidencePolicy()
        entry = observation(
            "cup-entry-old",
            sensor_kind="cup_entry",
            transition="entered",
            source_device_id="cup-entry-node",
            edge_received_ns=1_000_000_000,
        )
        presence = observation(
            "cup-presence-late",
            sensor_kind="cup_presence",
            transition="occupied",
            source_device_id="cup-presence-node",
            edge_received_ns=5_000_000_001,
            ball_id="b1",
        )
        policy.evaluate(entry, active)
        decision = policy.evaluate(presence, active)
        self.assertEqual(decision.status, "rejected")
        self.assertEqual(decision.reason, "cup_confirmation_window_expired")

    def test_same_node_reboot_cannot_complete_a_half_sequence(self) -> None:
        policy = NoCsPhysicalEvidencePolicy()
        active = context(
            active_ball_id="b1",
            active_player_id="p1",
            active_player_state="playing",
        )
        entry = observation(
            "cup-before-reboot",
            sensor_kind="cup_entry",
            transition="entered",
            source_device_id="combined-cup-node",
            source_boot_id="boot-1",
            sequence=5,
            edge_received_ns=2_000_000_000,
        )
        presence = observation(
            "cup-after-reboot",
            sensor_kind="cup_presence",
            transition="occupied",
            source_device_id="combined-cup-node",
            source_boot_id="boot-2",
            sequence=1,
            edge_received_ns=2_500_000_000,
            ball_id="b1",
        )
        policy.evaluate(entry, active)
        decision = policy.evaluate(presence, active)
        self.assertEqual(decision.status, "rejected")
        self.assertEqual(decision.reason, "source_rebooted_during_cup_sequence")

    def test_source_gap_and_duplicate_sequence_fail_closed(self) -> None:
        policy = NoCsPhysicalEvidencePolicy()
        policy.evaluate(
            observation(
                "tee-vacant-1",
                sensor_kind="tee_presence",
                transition="vacant",
                source_device_id="tee-node",
                sequence=1,
                value=False,
            ),
            context(),
        )
        gap = policy.evaluate(
            observation(
                "tee-vacant-3",
                sensor_kind="tee_presence",
                transition="vacant",
                source_device_id="tee-node",
                sequence=3,
                source_monotonic_ns=3_000_000_000,
                value=False,
            ),
            context(),
        )
        duplicate = policy.evaluate(
            observation(
                "tee-vacant-3b",
                sensor_kind="tee_presence",
                transition="vacant",
                source_device_id="tee-node",
                sequence=3,
                source_monotonic_ns=3_100_000_000,
                value=False,
            ),
            context(),
        )
        self.assertEqual(gap.reason, "source_sequence_gap")
        self.assertEqual(duplicate.reason, "duplicate_source_sequence")

    def test_same_physical_sequence_replays_to_identical_decisions(self) -> None:
        def replay() -> list[dict]:
            policy = NoCsPhysicalEvidencePolicy()
            active = context(
                active_ball_id="b1",
                active_player_id="p1",
                active_player_state="playing",
            )
            inputs = (
                (
                    observation(
                        "replay-tee",
                        sensor_kind="tee_presence",
                        transition="occupied",
                        source_device_id="replay-tee-node",
                        ball_id="b1",
                    ),
                    context(),
                ),
                (
                    observation(
                        "replay-cup-entry",
                        sensor_kind="cup_entry",
                        transition="entered",
                        source_device_id="replay-entry-node",
                        ball_id="b1",
                        edge_received_ns=2_000_000_000,
                    ),
                    active,
                ),
                (
                    observation(
                        "replay-cup-presence",
                        sensor_kind="cup_presence",
                        transition="occupied",
                        source_device_id="replay-presence-node",
                        ball_id="b1",
                        edge_received_ns=2_500_000_000,
                    ),
                    active,
                ),
            )
            return [policy.evaluate(edge, ctx).to_dict() for edge, ctx in inputs]

        self.assertEqual(replay(), replay())


if __name__ == "__main__":
    unittest.main()
