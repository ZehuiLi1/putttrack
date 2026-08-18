from __future__ import annotations

import inspect
import tempfile
import unittest
from pathlib import Path

from putttrack.contracts import EvidenceEvent, RangeObservation
from putttrack.evidence import DeterministicReplay, EvidenceToGameplayAdapter
from putttrack.gameplay import (
    FeatureKind,
    FeatureRule,
    GameplayEngine,
    HoleDefinition,
    Player,
    SessionState,
)
from putttrack.recording import AppendOnlyJsonlWriter


class ReplayTests(unittest.TestCase):
    def engine_factory(self):
        def factory() -> GameplayEngine:
            players = {"p1": Player("p1", "Alex", "ball-1")}
            hole = HoleDefinition(
                hole_id="H01",
                number=1,
                title="Replay Hole",
                score_curve={1: 100, 2: 80},
                features={
                    "bonus": FeatureRule(
                        "bonus", "Bonus", 25, FeatureKind.BONUS
                    )
                },
            )
            return GameplayEngine(SessionState("session-1", players, [hole]))

        return factory

    def evidence(
        self,
        event_id: str,
        semantic_type: str,
        sequence: int,
        *,
        boot: str = "boot-1",
        payload=None,
    ) -> EvidenceEvent:
        return EvidenceEvent(
            event_id=event_id,
            event_type=semantic_type,
            source_device_id="fusion-1",
            source_boot_id=boot,
            sequence=sequence,
            source_monotonic_ns=sequence * 1_000_000,
            edge_received_ns=sequence * 1_000_000,
            trace_id="trace-1",
            correlation_id="round-1",
            zone_id="Z01",
            hole_id="H01",
            ball_id="ball-1",
            model_version="fusion-model-1",
            raw_evidence_refs=(f"raw-{event_id}",),
            semantic_type=semantic_type,
            session_id="session-1",
            player_id="p1",
            confidence=0.99,
            fusion_policy_version="policy-1",
            payload=payload or {},
        )

    def test_duplicate_event_does_not_double_score_and_replay_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "events.jsonl"
            writer = AppendOnlyJsonlWriter(path)
            tee = self.evidence("tee", "tee.presented", 1)
            stroke = self.evidence("stroke", "stroke.confirmed", 2)
            cup = self.evidence("cup", "cup.confirmed", 3)
            writer.append(tee)
            writer.append(stroke)
            writer.append(stroke)
            writer.append(cup)

            replay = DeterministicReplay()
            first, second = replay.assert_deterministic(path, self.engine_factory())
            self.assertEqual(first.authoritative_digest, second.authoritative_digest)
            stats = first.authoritative_snapshot["stats"]["p1"]
            self.assertEqual(stats["total_strokes"], 1)
            self.assertEqual(stats["total_points"], 100)
            self.assertEqual(first.authoritative_snapshot["seen_event_count"], 3)
            self.assertTrue(any(not status.clean for status in first.ordering_statuses))

    def test_gap_out_of_order_and_reboot_are_diagnostic(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "events.jsonl"
            writer = AppendOnlyJsonlWriter(path)
            for sequence, boot in ((1, "boot-1"), (3, "boot-1"), (2, "boot-1"), (1, "boot-2")):
                writer.append(
                    RangeObservation(
                        event_id=f"r-{boot}-{sequence}",
                        event_type="cs.range_observed",
                        source_device_id="anchor-A",
                        source_boot_id=boot,
                        sequence=sequence,
                        source_monotonic_ns=sequence * 100,
                        edge_received_ns=sequence * 100 + 1,
                        trace_id="trace-range",
                        ball_id="ball-1",
                        anchor_id="anchor-A",
                        distance_ifft_m=1.0,
                    )
                )
            report = DeterministicReplay().replay_jsonl(path, self.engine_factory())
            self.assertEqual(report.gameplay_input_count, 0)
            self.assertIsNotNone(report.ordering_statuses[1].sequence_gap)
            self.assertTrue(report.ordering_statuses[2].out_of_order)
            self.assertTrue(report.ordering_statuses[3].new_boot)

    def test_invalid_state_transition_is_quarantined_without_score_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "events.jsonl"
            AppendOnlyJsonlWriter(path).append(
                self.evidence("cup", "cup.confirmed", 1)
            )
            report = DeterministicReplay().replay_jsonl(path, self.engine_factory())
            self.assertEqual(report.authoritative_snapshot["stats"]["p1"]["total_points"], 0)
            self.assertEqual(len(report.quarantines), 1)
            self.assertIn("GameplayError", report.quarantines[0].reason)

    def test_adapter_has_no_sensor_technology_import(self) -> None:
        source = inspect.getsource(EvidenceToGameplayAdapter)
        self.assertNotIn("putttrack.cs", source)
        self.assertNotIn("uwb", source.lower())
        self.assertNotIn("nordic", source.lower())


if __name__ == "__main__":
    unittest.main()
