"""Deterministic evidence replay into the existing Gameplay Engine."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from putttrack.contracts import EvidenceEvent, GameplayEvent as ContractGameplayEvent
from putttrack.gameplay import (
    FeatureKind,
    FeatureRule,
    GameplayEngine,
    GameplayError,
    HoleDefinition,
    Player,
    SessionState,
)
from putttrack.recording.jsonl import ReadResult, iter_jsonl

from .adapter import EvidenceAdapterError, EvidenceToGameplayAdapter
from .ordering import OrderingStatus, OrderingTracker


@dataclass(frozen=True)
class ReplayQuarantine:
    line_number: int
    event_id: str | None
    reason: str


@dataclass(frozen=True)
class ReplayReport:
    authoritative_snapshot: dict[str, Any]
    authoritative_digest: str
    accepted_record_count: int
    gameplay_input_count: int
    ordering_statuses: tuple[OrderingStatus, ...]
    quarantines: tuple[ReplayQuarantine, ...]
    notices: tuple[dict[str, Any], ...]


def _canonical_digest(value: Mapping[str, Any]) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def session_from_dict(data: Mapping[str, Any]) -> SessionState:
    players: dict[str, Player] = {}
    for raw_player in data.get("players", []):
        player = Player(
            player_id=str(raw_player["player_id"]),
            display_name=str(raw_player["display_name"]),
            ball_id=str(raw_player["ball_id"]),
            team_id=raw_player.get("team_id"),
        )
        players[player.player_id] = player

    course: list[HoleDefinition] = []
    for raw_hole in data.get("course", []):
        features: dict[str, FeatureRule] = {}
        for raw_feature in raw_hole.get("features", []):
            rule = FeatureRule(
                feature_id=str(raw_feature["feature_id"]),
                label=str(raw_feature["label"]),
                points_delta=int(raw_feature["points_delta"]),
                kind=FeatureKind(str(raw_feature.get("kind", "bonus"))),
                max_triggers_per_player=int(
                    raw_feature.get("max_triggers_per_player", 1)
                ),
            )
            features[rule.feature_id] = rule
        score_curve = {
            int(key): int(value)
            for key, value in raw_hole.get("score_curve", {}).items()
        }
        course.append(
            HoleDefinition(
                hole_id=str(raw_hole["hole_id"]),
                number=int(raw_hole["number"]),
                title=str(raw_hole["title"]),
                instructions=str(raw_hole.get("instructions", "")),
                score_curve=score_curve,
                features=features,
            )
        )
    return SessionState(session_id=str(data["session_id"]), players=players, course=course)


def engine_from_session_file(path: str | Path) -> GameplayEngine:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("session fixture must be a JSON object")
    return GameplayEngine(session_from_dict(raw))


class DeterministicReplay:
    def __init__(self, adapter: EvidenceToGameplayAdapter | None = None) -> None:
        self.adapter = adapter or EvidenceToGameplayAdapter()

    def replay_results(
        self,
        results: Iterable[ReadResult],
        engine_factory: Callable[[], GameplayEngine],
    ) -> ReplayReport:
        engine = engine_factory()
        ordering = OrderingTracker()
        statuses: list[OrderingStatus] = []
        quarantines: list[ReplayQuarantine] = []
        notices: list[dict[str, Any]] = []
        accepted = 0
        gameplay_inputs = 0

        for result in results:
            if not result.accepted or result.record is None:
                quarantines.append(
                    ReplayQuarantine(
                        line_number=result.line_number,
                        event_id=(
                            str(result.raw_object.get("event_id"))
                            if result.raw_object and result.raw_object.get("event_id")
                            else None
                        ),
                        reason=result.quarantine_reason or "not_accepted",
                    )
                )
                continue

            record = result.record
            accepted += 1
            statuses.append(ordering.observe(record))
            try:
                if isinstance(record, EvidenceEvent):
                    domain_event = self.adapter.from_evidence(record)
                elif isinstance(record, ContractGameplayEvent):
                    domain_event = self.adapter.from_contract_gameplay(record)
                else:
                    continue
                gameplay_inputs += 1
                notices.extend(asdict(item) for item in engine.process(domain_event))
            except (EvidenceAdapterError, GameplayError, ValueError) as exc:
                quarantines.append(
                    ReplayQuarantine(
                        line_number=result.line_number,
                        event_id=record.event_id,
                        reason=f"gameplay_quarantine:{type(exc).__name__}:{exc}",
                    )
                )

        snapshot = engine.evidence_snapshot()
        return ReplayReport(
            authoritative_snapshot=snapshot,
            authoritative_digest=_canonical_digest(snapshot),
            accepted_record_count=accepted,
            gameplay_input_count=gameplay_inputs,
            ordering_statuses=tuple(statuses),
            quarantines=tuple(quarantines),
            notices=tuple(notices),
        )

    def replay_jsonl(
        self,
        path: str | Path,
        engine_factory: Callable[[], GameplayEngine],
    ) -> ReplayReport:
        return self.replay_results(iter_jsonl(path), engine_factory)

    def assert_deterministic(
        self,
        path: str | Path,
        engine_factory: Callable[[], GameplayEngine],
    ) -> tuple[ReplayReport, ReplayReport]:
        first = self.replay_jsonl(path, engine_factory)
        second = self.replay_jsonl(path, engine_factory)
        if first.authoritative_digest != second.authoritative_digest:
            raise AssertionError(
                "replay produced different authoritative digests: "
                f"{first.authoritative_digest} != {second.authoritative_digest}"
            )
        if first.authoritative_snapshot != second.authoritative_snapshot:
            raise AssertionError("replay produced different authoritative snapshots")
        return first, second
