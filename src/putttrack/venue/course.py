from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from putttrack.gameplay import FeatureKind, FeatureRule, HoleDefinition


class CourseConfigError(ValueError):
    pass


@dataclass(frozen=True)
class CourseDefinition:
    course_id: str
    title: str
    holes: tuple[HoleDefinition, ...]


def _non_empty(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CourseConfigError(f"{field} must be a non-empty string")
    return value.strip()


def course_from_dict(data: dict[str, Any]) -> CourseDefinition:
    if not isinstance(data, dict):
        raise CourseConfigError("course config must be an object")
    course_id = _non_empty(data.get("course_id"), "course_id")
    title = _non_empty(data.get("title", course_id), "title")
    hole_items = data.get("holes")
    if not isinstance(hole_items, list) or not hole_items:
        raise CourseConfigError("holes must be a non-empty list")

    holes: list[HoleDefinition] = []
    seen_ids: set[str] = set()
    seen_numbers: set[int] = set()
    for raw in hole_items:
        if not isinstance(raw, dict):
            raise CourseConfigError("each hole must be an object")
        hole_id = _non_empty(raw.get("hole_id"), "hole_id")
        if hole_id in seen_ids:
            raise CourseConfigError(f"duplicate hole_id {hole_id!r}")
        seen_ids.add(hole_id)
        number = raw.get("number")
        if not isinstance(number, int) or isinstance(number, bool) or number < 1:
            raise CourseConfigError("hole number must be a positive integer")
        if number in seen_numbers:
            raise CourseConfigError(f"duplicate hole number {number}")
        seen_numbers.add(number)

        score_curve_raw = raw.get("score_curve")
        if not isinstance(score_curve_raw, dict) or not score_curve_raw:
            raise CourseConfigError(f"{hole_id}: score_curve must be a non-empty object")
        score_curve: dict[int, int] = {}
        for key, value in score_curve_raw.items():
            try:
                strokes = int(key)
            except (TypeError, ValueError) as exc:
                raise CourseConfigError(f"{hole_id}: invalid score threshold {key!r}") from exc
            if strokes < 1 or not isinstance(value, int) or isinstance(value, bool):
                raise CourseConfigError(f"{hole_id}: invalid score curve entry {key!r}")
            score_curve[strokes] = value

        features: dict[str, FeatureRule] = {}
        feature_items = raw.get("features", [])
        if not isinstance(feature_items, list):
            raise CourseConfigError(f"{hole_id}: features must be a list")
        for item in feature_items:
            if not isinstance(item, dict):
                raise CourseConfigError(f"{hole_id}: feature must be an object")
            feature_id = _non_empty(item.get("feature_id"), "feature_id")
            if feature_id in features:
                raise CourseConfigError(f"{hole_id}: duplicate feature {feature_id!r}")
            try:
                kind = FeatureKind(str(item.get("kind", "bonus")))
            except ValueError as exc:
                raise CourseConfigError(
                    f"{hole_id}: unsupported feature kind {item.get('kind')!r}"
                ) from exc
            points_delta = item.get("points_delta")
            if not isinstance(points_delta, int) or isinstance(points_delta, bool):
                raise CourseConfigError(f"{hole_id}/{feature_id}: points_delta must be int")
            max_triggers = item.get("max_triggers_per_player", 1)
            if (
                not isinstance(max_triggers, int)
                or isinstance(max_triggers, bool)
                or max_triggers < 1
            ):
                raise CourseConfigError(
                    f"{hole_id}/{feature_id}: max_triggers_per_player must be >=1"
                )
            features[feature_id] = FeatureRule(
                feature_id=feature_id,
                label=_non_empty(item.get("label", feature_id), "feature label"),
                points_delta=points_delta,
                kind=kind,
                max_triggers_per_player=max_triggers,
            )

        holes.append(
            HoleDefinition(
                hole_id=hole_id,
                number=number,
                title=_non_empty(raw.get("title", hole_id), "hole title"),
                instructions=str(raw.get("instructions", "")).strip(),
                score_curve=score_curve,
                features=features,
            )
        )

    holes.sort(key=lambda hole: hole.number)
    return CourseDefinition(course_id=course_id, title=title, holes=tuple(holes))


def load_course(path: str | Path) -> CourseDefinition:
    file_path = Path(path)
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CourseConfigError(f"cannot load course config {file_path}: {exc}") from exc
    return course_from_dict(data)
