from __future__ import annotations

import unittest

from putttrack.contracts import (
    EvidenceEvent,
    RangeObservation,
    RecordCodecError,
    TrackUpdate,
    UnsupportedSchemaVersion,
    record_from_dict,
    record_to_dict,
)


class ContractTests(unittest.TestCase):
    def base(self, **kwargs):
        return {
            "event_id": "evt-1",
            "event_type": "test.event",
            "source_device_id": "device-1",
            "source_boot_id": "boot-1",
            "sequence": 1,
            "source_monotonic_ns": 100,
            "edge_received_ns": 200,
            "trace_id": "trace-1",
            **kwargs,
        }

    def test_range_round_trip_preserves_typed_fields(self) -> None:
        record = RangeObservation(
            **self.base(event_type="cs.range_observed", ball_id="ball-1"),
            anchor_id="anchor-A",
            antenna_path=1,
            distance_ifft_m=1.25,
            distance_phase_m=1.20,
            distance_rtt_m=1.7,
            quality={"tone_quality": 0.9},
            anchor_position_m=(0.0, 0.0, 1.0),
        )
        decoded = record_from_dict(record_to_dict(record))
        self.assertEqual(decoded, record)

    def test_additive_minor_fields_are_preserved_as_extensions(self) -> None:
        raw = record_to_dict(
            RangeObservation(
                **self.base(event_type="cs.range_observed", ball_id="ball-1"),
                schema_version="1.2",
                anchor_id="anchor-A",
                distance_ifft_m=1.0,
            )
        )
        raw["future_optional_metric"] = {"value": 7}
        decoded = record_from_dict(raw)
        self.assertEqual(decoded.extensions["future_optional_metric"], {"value": 7})
        self.assertEqual(
            record_to_dict(decoded)["future_optional_metric"], {"value": 7}
        )

    def test_unknown_major_version_fails_closed(self) -> None:
        raw = record_to_dict(
            RangeObservation(
                **self.base(event_type="cs.range_observed", ball_id="ball-1"),
                anchor_id="anchor-A",
                distance_ifft_m=1.0,
            )
        )
        raw["schema_version"] = "2.0"
        with self.assertRaises(UnsupportedSchemaVersion):
            record_from_dict(raw)

    def test_missing_required_field_rejected(self) -> None:
        raw = record_to_dict(
            RangeObservation(
                **self.base(event_type="cs.range_observed", ball_id="ball-1"),
                anchor_id="anchor-A",
                distance_ifft_m=1.0,
            )
        )
        del raw["event_id"]
        with self.assertRaises(RecordCodecError):
            record_from_dict(raw)

    def test_track_and_evidence_records_validate(self) -> None:
        track = TrackUpdate(
            **self.base(event_type="track.updated", ball_id="ball-1"),
            position_m=(1.0, 2.0),
            velocity_mps=(0.1, 0.2),
            covariance=((0.1, 0.0), (0.0, 0.2)),
            confidence=0.9,
            track_state="TRACKING",
            anchors_recent=("A", "B", "C"),
            algorithm_version="ekf-1",
        )
        evidence = EvidenceEvent(
            **self.base(
                event_id="evd-1",
                event_type="cup.confirmed",
                ball_id="ball-1",
                hole_id="H01",
            ),
            semantic_type="cup.confirmed",
            session_id="session-1",
            player_id="player-1",
            confidence=0.999,
            fusion_policy_version="cup-v1",
        )
        self.assertEqual(record_from_dict(record_to_dict(track)), track)
        self.assertEqual(record_from_dict(record_to_dict(evidence)), evidence)


if __name__ == "__main__":
    unittest.main()
