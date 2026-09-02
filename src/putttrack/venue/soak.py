"""Deterministic no-CS one-hole software soak with evidence fault injection."""

from __future__ import annotations

import hashlib
import random
from collections import Counter
from dataclasses import dataclass
from typing import Any

from putttrack.contracts import PhysicalSensorObservation
from putttrack.gameplay import (
    EventType,
    GameplayEvent,
    HoleDefinition,
    Player,
    SessionState,
)

from .runtime import LocalRoundRuntime


@dataclass(frozen=True)
class NoCsSoakReport:
    rounds_requested: int
    rounds_completed: int
    players_per_round: int
    seed: int
    status_counts: dict[str, int]
    fault_counts: dict[str, int]
    gameplay_events_per_round: int
    authoritative_digest: str
    failures: tuple[dict[str, Any], ...]

    @property
    def passed(self) -> bool:
        return self.rounds_completed == self.rounds_requested and not self.failures

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": "PASS" if self.passed else "FAIL",
            "rounds_requested": self.rounds_requested,
            "rounds_completed": self.rounds_completed,
            "players_per_round": self.players_per_round,
            "seed": self.seed,
            "status_counts": dict(sorted(self.status_counts.items())),
            "fault_counts": dict(sorted(self.fault_counts.items())),
            "gameplay_events_per_round": self.gameplay_events_per_round,
            "authoritative_digest": self.authoritative_digest,
            "failures": list(self.failures),
            "scope": "software-only; no physical sensor reliability claim",
        }


def _observation(
    *,
    event_id: str,
    source_device_id: str,
    sequence: int,
    timestamp_ns: int,
    sensor_kind: str,
    transition: str,
    ball_id: str,
) -> PhysicalSensorObservation:
    return PhysicalSensorObservation(
        event_id=event_id,
        event_type="sensor.edge_observed",
        source_device_id=source_device_id,
        source_boot_id="boot-soak",
        sequence=sequence,
        source_monotonic_ns=timestamp_ns,
        edge_received_ns=timestamp_ns + 1_000_000,
        trace_id=f"trace-{event_id}",
        hole_id="H01",
        ball_id=ball_id,
        firmware_version="soak-node-v0",
        sensor_id=f"sensor-{source_device_id}",
        sensor_kind=sensor_kind,
        transition=transition,
        value=True,
        health="ok",
        debounce_version="soak-debounce-v1",
    )


def _state(round_index: int, players_per_round: int) -> SessionState:
    players = {
        f"p{index:02d}": Player(
            player_id=f"p{index:02d}",
            display_name=f"Player {index}",
            ball_id=f"ball-{index:02d}",
        )
        for index in range(1, players_per_round + 1)
    }
    return SessionState(
        session_id=f"soak-session-{round_index:06d}",
        players=players,
        course=[
            HoleDefinition(
                hole_id="H01",
                number=1,
                title="No-CS soak hole",
                instructions="Software fault-injection fixture",
                score_curve={1: 100, 2: 80, 3: 65},
            )
        ],
    )


def run_no_cs_hole_soak(
    *,
    rounds: int = 1_000,
    players_per_round: int = 4,
    seed: int = 54_015,
) -> NoCsSoakReport:
    """Exercise physical ingress and Gameplay authority over many fresh rounds.

    Each player receives five deliberate transport/context faults around a
    valid tee -> independent stroke -> two-stage cup path. Any score/state
    mutation from a fault is recorded as a failed round.
    """

    if rounds < 1:
        raise ValueError("rounds must be >= 1")
    if players_per_round < 1:
        raise ValueError("players_per_round must be >= 1")
    if players_per_round > 32:
        raise ValueError("players_per_round must be <= 32")

    rng = random.Random(seed)
    statuses: Counter[str] = Counter()
    faults: Counter[str] = Counter()
    failures: list[dict[str, Any]] = []
    digest_rows: list[str] = []
    completed = 0

    for round_index in range(1, rounds + 1):
        try:
            runtime = LocalRoundRuntime(_state(round_index, players_per_round))
            order = list(runtime.state.players)
            rng.shuffle(order)
            tee_sequence = 0
            entry_sequence = 0
            presence_sequence = 0
            timestamp_ns = round_index * 1_000_000_000_000

            for play_index, player_id in enumerate(order, start=1):
                ball_id = runtime.state.players[player_id].ball_id
                wrong_ball_id = (
                    "foreign-ball"
                    if players_per_round == 1
                    else runtime.state.players[
                        next(item for item in order if item != player_id)
                    ].ball_id
                )

                tee_sequence += 1
                foreign_tee = _observation(
                    event_id=f"r{round_index}-p{play_index}-tee-foreign",
                    source_device_id="tee-H01",
                    sequence=tee_sequence,
                    timestamp_ns=timestamp_ns,
                    sensor_kind="tee_presence",
                    transition="occupied",
                    ball_id="foreign-ball",
                )
                decision = runtime.process_physical_sensor_observation(foreign_tee)
                statuses[decision.status] += 1
                faults["foreign_tee"] += 1
                if (
                    decision.status != "rejected"
                    or runtime.state.current_runtime.active_player_id is not None
                ):
                    raise AssertionError("foreign tee observation changed authority")

                timestamp_ns += 10_000_000
                tee_sequence += 1
                tee = _observation(
                    event_id=f"r{round_index}-p{play_index}-tee",
                    source_device_id="tee-H01",
                    sequence=tee_sequence,
                    timestamp_ns=timestamp_ns,
                    sensor_kind="tee_presence",
                    transition="occupied",
                    ball_id=ball_id,
                )
                decision = runtime.process_physical_sensor_observation(tee)
                statuses[decision.status] += 1
                if decision.status != "accepted":
                    raise AssertionError(f"valid tee was {decision.status}")

                duplicate_sequence = _observation(
                    event_id=f"r{round_index}-p{play_index}-tee-duplicate-sequence",
                    source_device_id="tee-H01",
                    sequence=tee_sequence,
                    timestamp_ns=timestamp_ns + 1_000_000,
                    sensor_kind="tee_presence",
                    transition="occupied",
                    ball_id=ball_id,
                )
                decision = runtime.process_physical_sensor_observation(
                    duplicate_sequence
                )
                statuses[decision.status] += 1
                faults["duplicate_tee_sequence"] += 1
                if decision.status != "rejected":
                    raise AssertionError("duplicate source sequence was not rejected")

                runtime.process_gameplay(
                    GameplayEvent(
                        event_id=f"r{round_index}-p{play_index}-stroke",
                        event_type=EventType.STROKE_CONFIRMED,
                        timestamp_ms=(timestamp_ns // 1_000_000) + 20,
                        hole_id="H01",
                        ball_id=ball_id,
                        source="independent-soak-stroke",
                    )
                )
                if runtime.state.stats[player_id].total_strokes != 1:
                    raise AssertionError("independent stroke count changed unexpectedly")

                timestamp_ns += 30_000_000
                presence_sequence += 1
                presence_only = _observation(
                    event_id=f"r{round_index}-p{play_index}-presence-only",
                    source_device_id="cup-presence-H01",
                    sequence=presence_sequence,
                    timestamp_ns=timestamp_ns,
                    sensor_kind="cup_presence",
                    transition="occupied",
                    ball_id=ball_id,
                )
                decision = runtime.process_physical_sensor_observation(presence_only)
                statuses[decision.status] += 1
                faults["cup_presence_without_entry"] += 1
                if decision.status != "pending":
                    raise AssertionError("single cup presence did not stay pending")

                timestamp_ns += 10_000_000
                entry_sequence += 1
                wrong_entry = _observation(
                    event_id=f"r{round_index}-p{play_index}-entry-wrong-ball",
                    source_device_id="cup-entry-H01",
                    sequence=entry_sequence,
                    timestamp_ns=timestamp_ns,
                    sensor_kind="cup_entry",
                    transition="entered",
                    ball_id=wrong_ball_id,
                )
                decision = runtime.process_physical_sensor_observation(wrong_entry)
                statuses[decision.status] += 1
                faults["wrong_ball_cup_entry"] += 1
                if decision.status != "rejected":
                    raise AssertionError("wrong-Ball cup entry was not rejected")

                timestamp_ns += 10_000_000
                entry_sequence += 1
                entry = _observation(
                    event_id=f"r{round_index}-p{play_index}-entry",
                    source_device_id="cup-entry-H01",
                    sequence=entry_sequence,
                    timestamp_ns=timestamp_ns,
                    sensor_kind="cup_entry",
                    transition="entered",
                    ball_id=ball_id,
                )
                decision = runtime.process_physical_sensor_observation(entry)
                statuses[decision.status] += 1
                if decision.status != "pending":
                    raise AssertionError("valid cup entry did not stay pending")

                timestamp_ns += 100_000_000
                presence_sequence += 1
                presence = _observation(
                    event_id=f"r{round_index}-p{play_index}-presence",
                    source_device_id="cup-presence-H01",
                    sequence=presence_sequence,
                    timestamp_ns=timestamp_ns,
                    sensor_kind="cup_presence",
                    transition="occupied",
                    ball_id=ball_id,
                )
                decision = runtime.process_physical_sensor_observation(presence)
                statuses[decision.status] += 1
                if decision.status != "accepted":
                    raise AssertionError(f"valid cup pair was {decision.status}")

                before_retry = runtime.engine.evidence_snapshot()
                repeated = runtime.process_physical_sensor_observation(presence)
                faults["exact_cup_retransmission"] += 1
                if repeated is not decision:
                    raise AssertionError("exact retransmission was not cached")
                if runtime.engine.evidence_snapshot() != before_retry:
                    raise AssertionError("exact retransmission mutated Gameplay")

            expected_events = players_per_round * 3
            if runtime.state.status.value != "complete":
                raise AssertionError("round did not complete")
            if len(runtime.state.seen_event_ids) != expected_events:
                raise AssertionError("unexpected authoritative Gameplay event count")
            for player_id, stats in runtime.state.stats.items():
                if (stats.total_strokes, stats.total_points, stats.holes_completed) != (
                    1,
                    100,
                    1,
                ):
                    raise AssertionError(f"score invariant failed for {player_id}")

            digest_rows.append(
                f"{round_index}|{','.join(order)}|{expected_events}|"
                + ",".join(
                    f"{player_id}:1:100:1" for player_id in sorted(runtime.state.stats)
                )
            )
            completed += 1
        except Exception as exc:  # retain the first bounded failures in the report
            if len(failures) < 20:
                failures.append(
                    {
                        "round": round_index,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )

    digest = hashlib.sha256("\n".join(digest_rows).encode("utf-8")).hexdigest()
    return NoCsSoakReport(
        rounds_requested=rounds,
        rounds_completed=completed,
        players_per_round=players_per_round,
        seed=seed,
        status_counts=dict(statuses),
        fault_counts=dict(faults),
        gameplay_events_per_round=players_per_round * 3,
        authoritative_digest=digest,
        failures=tuple(failures),
    )
