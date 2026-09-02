from __future__ import annotations

import unittest
from dataclasses import replace

from putttrack.contracts import RadioReceptionObservation, record_from_dict, record_to_dict
from putttrack.radio import (
    BallRadioState,
    MultiReceiverContext,
    aggregate_radio_receptions,
    deterministic_repetition_offsets_ms,
    research_radio_profile,
)


DIGEST = "a" * 64


def reception(
    receiver_id: str,
    *,
    receiver_sequence: int,
    rssi_dbm: int,
    edge_received_ns: int,
    **overrides,
) -> RadioReceptionObservation:
    values = {
        "event_id": f"{receiver_id}-packet-42",
        "event_type": "radio.packet_observed",
        "source_device_id": receiver_id,
        "source_boot_id": f"{receiver_id}-boot",
        "sequence": receiver_sequence,
        "source_monotonic_ns": edge_received_ns - 100,
        "edge_received_ns": edge_received_ns,
        "trace_id": "trace-radio-42",
        "hole_id": "H01",
        "ball_id": "ball-01",
        "ball_device_id": "0011223344556677",
        "ball_boot_id": "8899aabbccddeeff",
        "ball_radio_sequence": 42,
        "payload_digest": DIGEST,
        "rssi_dbm": rssi_dbm,
        "tx_power_dbm": 0,
        "channel_index": 37,
    }
    values.update(overrides)
    return RadioReceptionObservation(**values)


class MultiReceiverRadioTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = MultiReceiverContext(
            device_to_ball={"0011223344556677": "ball-01"},
            allowed_receiver_ids=("rx-tee", "rx-mid", "rx-cup"),
            minimum_receivers=2,
            maximum_receive_span_ns=50_000_000,
        )

    def test_contract_round_trip_preserves_separate_ball_and_receiver_identity(self) -> None:
        item = reception(
            "rx-tee",
            receiver_sequence=10,
            rssi_dbm=-41,
            edge_received_ns=1_000_000,
        )
        decoded = record_from_dict(record_to_dict(item))
        self.assertEqual(decoded, item)
        self.assertEqual(decoded.source_device_id, "rx-tee")
        self.assertEqual(decoded.ball_device_id, "0011223344556677")

    def test_two_receivers_meet_diversity_without_position_or_gameplay_authority(self) -> None:
        decision = aggregate_radio_receptions(
            [
                reception(
                    "rx-tee",
                    receiver_sequence=10,
                    rssi_dbm=-42,
                    edge_received_ns=1_000_000,
                ),
                reception(
                    "rx-mid",
                    receiver_sequence=20,
                    rssi_dbm=-58,
                    edge_received_ns=2_000_000,
                ),
            ],
            self.context,
        )

        self.assertTrue(decision.quorum_met)
        self.assertEqual(decision.receiver_count, 2)
        self.assertEqual(decision.strongest_receiver_id, "rx-tee")
        self.assertEqual(decision.median_path_loss_db, 50.0)
        self.assertFalse(decision.position_authority)
        self.assertFalse(decision.gameplay_authority)

    def test_single_receiver_stays_observed(self) -> None:
        decision = aggregate_radio_receptions(
            [
                reception(
                    "rx-tee",
                    receiver_sequence=10,
                    rssi_dbm=-42,
                    edge_received_ns=1_000_000,
                )
            ],
            self.context,
        )
        self.assertEqual(decision.status, "observed")
        self.assertEqual(decision.reason, "additional_receiver_required")

    def test_identity_unknown_receiver_packet_mix_and_late_reports_fail_closed(self) -> None:
        base = reception(
            "rx-tee",
            receiver_sequence=10,
            rssi_dbm=-42,
            edge_received_ns=1_000_000,
        )
        cases = (
            (
                [replace(base, ball_id="other")],
                "ball_device_mapping_mismatch",
            ),
            (
                [replace(base, source_device_id="foreign")],
                "receiver_is_not_registered",
            ),
            (
                [
                    base,
                    reception(
                        "rx-mid",
                        receiver_sequence=20,
                        rssi_dbm=-58,
                        edge_received_ns=2_000_000,
                        ball_radio_sequence=43,
                    ),
                ],
                "observations_do_not_describe_one_ball_packet",
            ),
            (
                [
                    base,
                    reception(
                        "rx-mid",
                        receiver_sequence=20,
                        rssi_dbm=-58,
                        edge_received_ns=100_000_000,
                    ),
                ],
                "receiver_observations_exceed_aggregation_window",
            ),
        )
        for observations, expected_reason in cases:
            with self.subTest(expected_reason):
                decision = aggregate_radio_receptions(observations, self.context)
                self.assertEqual(decision.status, "rejected")
                self.assertEqual(decision.reason, expected_reason)

    def test_research_radio_profiles_are_bounded_and_not_deployment_authority(self) -> None:
        shipping = research_radio_profile(BallRadioState.SHIPPING)
        idle = research_radio_profile(BallRadioState.IDLE)
        active = research_radio_profile(BallRadioState.ACTIVE)

        self.assertFalse(shipping.enabled)
        self.assertLess(idle.tx_power_dbm, active.tx_power_dbm)
        self.assertGreater(idle.advertising_interval_min_ms, active.advertising_interval_min_ms)
        self.assertTrue(active.research_only)
        with self.assertRaises(ValueError):
            research_radio_profile("unknown")

    def test_contract_rejects_invalid_radio_ranges_and_digest(self) -> None:
        with self.assertRaises(ValueError):
            reception(
                "rx-tee",
                receiver_sequence=1,
                rssi_dbm=-128,
                edge_received_ns=1,
            )
        with self.assertRaises(ValueError):
            reception(
                "rx-tee",
                receiver_sequence=1,
                rssi_dbm=-40,
                edge_received_ns=1,
                payload_digest="not-a-digest",
            )

    def test_decentralized_repetition_jitter_is_stable_and_packet_specific(self) -> None:
        first = deterministic_repetition_offsets_ms("ball-a:boot-a:42")
        repeated = deterministic_repetition_offsets_ms("ball-a:boot-a:42")
        next_packet = deterministic_repetition_offsets_ms("ball-a:boot-a:43")

        self.assertEqual(first, repeated)
        self.assertNotEqual(first, next_packet)
        self.assertEqual(first[0], 0)
        self.assertEqual(tuple(sorted(set(first))), first)
        self.assertLessEqual(first[-1], 120)
        with self.assertRaises(ValueError):
            deterministic_repetition_offsets_ms("", repetitions=3)


if __name__ == "__main__":
    unittest.main()
