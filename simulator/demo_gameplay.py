"""Small end-to-end gameplay simulation.

Run from the repository root with:

    PYTHONPATH=src python simulator/demo_gameplay.py
"""

from __future__ import annotations

import json

from putttrack.gameplay import (
    EventType,
    FeatureKind,
    FeatureRule,
    GameplayEngine,
    GameplayEvent,
    HoleDefinition,
    Player,
    SessionState,
)


SCORE_CURVE = {1: 100, 2: 80, 3: 65, 4: 55, 5: 45, 6: 35, 7: 30, 8: 25}


def event(seq: int, event_type: EventType, hole_id: str, ball_id: str, **kwargs):
    return GameplayEvent(
        event_id=f"evt-{seq:03d}",
        event_type=event_type,
        timestamp_ms=seq * 1_000,
        hole_id=hole_id,
        ball_id=ball_id,
        source="simulator",
        **kwargs,
    )


def main() -> None:
    players = {
        "p1": Player("p1", "Alex", "ball-blue-07"),
        "p2": Player("p2", "Sam", "ball-orange-12"),
    }
    holes = [
        HoleDefinition(
            hole_id="H01",
            number=1,
            title="First Light",
            instructions="Learn the system. Precision Gate +25.",
            score_curve=SCORE_CURVE,
            features={
                "precision_gate": FeatureRule(
                    "precision_gate", "Precision Gate", 25, FeatureKind.BONUS
                )
            },
        ),
        HoleDefinition(
            hole_id="H02",
            number=2,
            title="Risk Ridge",
            instructions="Safe route or risk lane: +50 / hazard -25.",
            score_curve=SCORE_CURVE,
            features={
                "risk_lane": FeatureRule(
                    "risk_lane", "Risk Lane", 50, FeatureKind.ROUTE
                ),
                "hazard": FeatureRule(
                    "hazard", "Hazard", -25, FeatureKind.HAZARD, max_triggers_per_player=2
                ),
            },
        ),
    ]

    engine = GameplayEngine(SessionState("demo-session", players, holes))

    # Flexible order: Sam plays first on H01 even though Alex is p1.
    events = [
        event(1, EventType.TEE_PRESENTED, "H01", "ball-orange-12"),
        event(2, EventType.STROKE_CONFIRMED, "H01", "ball-orange-12"),
        event(
            3,
            EventType.FEATURE_CONFIRMED,
            "H01",
            "ball-orange-12",
            feature_id="precision_gate",
        ),
        event(4, EventType.CUP_CONFIRMED, "H01", "ball-orange-12"),
        event(5, EventType.TEE_PRESENTED, "H01", "ball-blue-07"),
        event(6, EventType.STROKE_CONFIRMED, "H01", "ball-blue-07"),
        event(7, EventType.STROKE_CONFIRMED, "H01", "ball-blue-07"),
        event(8, EventType.CUP_CONFIRMED, "H01", "ball-blue-07"),
        event(9, EventType.TEE_PRESENTED, "H02", "ball-blue-07"),
        event(10, EventType.STROKE_CONFIRMED, "H02", "ball-blue-07"),
        event(
            11,
            EventType.FEATURE_CONFIRMED,
            "H02",
            "ball-blue-07",
            feature_id="risk_lane",
        ),
        event(12, EventType.CUP_CONFIRMED, "H02", "ball-blue-07"),
        event(13, EventType.TEE_PRESENTED, "H02", "ball-orange-12"),
        event(14, EventType.STROKE_CONFIRMED, "H02", "ball-orange-12"),
        event(15, EventType.STROKE_CONFIRMED, "H02", "ball-orange-12"),
        event(
            16,
            EventType.FEATURE_CONFIRMED,
            "H02",
            "ball-orange-12",
            feature_id="hazard",
        ),
        event(17, EventType.CUP_CONFIRMED, "H02", "ball-orange-12"),
    ]

    for item in events:
        for notice in engine.process(item):
            print(f"[{notice.kind}] {notice.text}")

    print("\nFinal evidence snapshot:\n")
    print(json.dumps(engine.evidence_snapshot(), indent=2))


if __name__ == "__main__":
    main()
