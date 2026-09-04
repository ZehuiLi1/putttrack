#!/usr/bin/env python3
"""Evaluate frozen pickup V0 directly from PuttTrack manifest/raw JSONL files."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import sys
from typing import Any, Iterable, Mapping

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from putttrack.motion.pickup_v0 import (  # noqa: E402
    PickupDecision,
    evaluate_capture_path,
)


POSITIVE_LABELS = {"pickup_carry", "pickup_drop"}
NEGATIVE_LABELS = {"handling", "putt_gentle", "putt_rail_collision", "track_step_drop"}
UNSUPPORTED_LABELS = {"rolling_pickup"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifests", nargs="+", type=Path)
    parser.add_argument(
        "--detector-config",
        type=Path,
        default=REPO_ROOT / "configs" / "research" / "pickup_detector_v0.json",
    )
    parser.add_argument(
        "--evaluation-profile",
        type=Path,
        default=REPO_ROOT
        / "configs"
        / "research"
        / "pickup_detector_v0_eval_profile.json",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def load_manifest(path: Path) -> tuple[str, list[dict[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: expected JSON object")
    if int(payload.get("schema_version", -1)) != 1:
        raise ValueError(f"{path}: unsupported schema_version")
    dataset_id = str(payload.get("dataset_id", "")).strip()
    defaults = payload.get("defaults", {})
    if not isinstance(defaults, dict):
        raise ValueError(f"{path}: defaults must be object")
    episodes = payload.get("episodes")
    if not isinstance(episodes, list):
        raise ValueError(f"{path}: episodes must be list")
    result = []
    for item in episodes:
        if not isinstance(item, dict):
            raise ValueError(f"{path}: episode must be object")
        merged = {**defaults, **item}
        merged["_episode_notes_explicit"] = item.get("notes")
        result.append(merged)
    return dataset_id, result


def wilson_interval(
    successes: int, trials: int, z: float = 1.959963984540054
) -> tuple[float | None, float | None]:
    if trials <= 0:
        return None, None
    p = successes / trials
    denominator = 1.0 + z * z / trials
    center = (p + z * z / (2.0 * trials)) / denominator
    half = (
        z
        * math.sqrt(
            p * (1.0 - p) / trials + z * z / (4.0 * trials * trials)
        )
        / denominator
    )
    return max(0.0, center - half), min(1.0, center + half)


def expected_target(label: str) -> int | None:
    if label in POSITIVE_LABELS:
        return 1
    if label in NEGATIVE_LABELS:
        return 0
    return None


def is_mixed_episode(episode: Mapping[str, Any]) -> bool:
    explicit = " ".join(
        str(episode.get(key, ""))
        for key in ("episode_id", "strength", "_episode_notes_explicit")
    ).lower()
    return (
        bool(episode.get("exclude_from_clean_metrics", False))
        or "plus-obstacle" in explicit
        or "planned-mixed" in explicit
        or "preserve as a mixed" in explicit
        or "exclude from clean" in explicit
    )


def flatten_row(
    *,
    dataset_id: str,
    manifest: Path,
    episode: Mapping[str, Any],
    result: Any,
) -> dict[str, Any]:
    label = str(episode.get("label", "")).strip().lower()
    target = expected_target(label)
    predicted = (
        1
        if result.decision == PickupDecision.PICKUP_SUSPECTED
        else 0
        if result.decision == PickupDecision.NOT_PICKUP
        else None
    )
    mixed = is_mixed_episode(episode)
    eligible = target is not None and label not in UNSUPPORTED_LABELS and not mixed
    row: dict[str, Any] = {
        "dataset_id": dataset_id,
        "manifest": _portable_path(manifest),
        "episode_id": episode.get("episode_id"),
        "capture": episode.get("capture"),
        "label": label,
        "session": episode.get("session"),
        "operator": episode.get("operator"),
        "core_revision": episode.get("core_revision"),
        "shell_revision": episode.get("shell_revision"),
        "surface": episode.get("surface"),
        "mixed_or_diagnostic": mixed,
        "metric_eligible": eligible,
        "target": target,
        "prediction": predicted,
        "decision": result.decision.value,
        "correct": target == predicted if eligible and predicted is not None else None,
        "unknown": result.decision == PickupDecision.UNKNOWN,
        "reason_codes": ";".join(result.reason_codes),
        "detector_id": result.detector_id,
        "detector_config_sha256": result.detector_config_sha256,
        "evaluation_profile_sha256": result.evaluation_profile_sha256,
        "authority": result.authority,
    }
    for key, value in sorted(result.rule_passes.items()):
        row[f"rule_{key}"] = value
    if result.features is not None:
        for key, value in result.features.__dict__.items():
            row[key] = value
    return row


def _portable_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve()))
    except ValueError:
        return str(path.resolve())


def confusion(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    eligible = [row for row in rows if row["metric_eligible"]]
    definitive = [row for row in eligible if row["prediction"] is not None]
    tp = sum(row["target"] == 1 and row["prediction"] == 1 for row in definitive)
    tn = sum(row["target"] == 0 and row["prediction"] == 0 for row in definitive)
    fp = sum(row["target"] == 0 and row["prediction"] == 1 for row in definitive)
    fn = sum(row["target"] == 1 and row["prediction"] == 0 for row in definitive)
    unknown = len(eligible) - len(definitive)
    positives = sum(row["target"] == 1 for row in eligible)
    negatives = sum(row["target"] == 0 for row in eligible)
    precision_n = tp + fp
    recall_n = positives
    precision = tp / precision_n if precision_n else None
    recall = tp / recall_n if recall_n else None
    fpr_all_negatives = fp / negatives if negatives else None
    coverage = len(definitive) / len(eligible) if eligible else None
    return {
        "eligible_episodes": len(eligible),
        "definitive_episodes": len(definitive),
        "unknown_episodes": unknown,
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "pickup_precision": precision,
        "pickup_precision_wilson95": wilson_interval(tp, precision_n),
        "pickup_recall_with_unknown_as_miss": recall,
        "pickup_recall_wilson95": wilson_interval(tp, recall_n),
        "false_pickup_rate_all_negatives": fpr_all_negatives,
        "false_pickup_rate_wilson95": wilson_interval(fp, negatives),
        "definitive_coverage": coverage,
        "definitive_coverage_wilson95": wilson_interval(
            len(definitive), len(eligible)
        ),
        "note": "UNKNOWN is reported separately and is never coerced to NOT_PICKUP.",
    }


def grouped_metrics(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        key = str(row.get(field) or "<missing>")
        groups.setdefault(key, []).append(row)
    return {key: confusion(group) for key, group in sorted(groups.items())}


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()
    rows: list[dict[str, Any]] = []
    for manifest in sorted(path.resolve() for path in args.manifests):
        dataset_id, episodes = load_manifest(manifest)
        for episode in sorted(
            episodes, key=lambda item: str(item.get("episode_id", ""))
        ):
            capture = manifest.parent / str(episode["capture"])
            result = evaluate_capture_path(
                capture,
                args.detector_config,
                args.evaluation_profile,
                manifest_label=str(episode.get("label", "")),
            )
            rows.append(
                flatten_row(
                    dataset_id=dataset_id,
                    manifest=manifest,
                    episode=episode,
                    result=result,
                )
            )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.output_dir / "episode_decisions.csv", rows)
    report = {
        "schema_version": 1,
        "detector_id": rows[0]["detector_id"] if rows else None,
        "authority": False,
        "overall": confusion(rows),
        "by_label": grouped_metrics(rows, "label"),
        "by_session": grouped_metrics(rows, "session"),
        "by_operator": grouped_metrics(rows, "operator"),
        "by_core_revision": grouped_metrics(rows, "core_revision"),
        "by_surface": grouped_metrics(rows, "surface"),
        "unsupported": [
            row for row in rows if row["label"] in UNSUPPORTED_LABELS
        ],
        "excluded_mixed_or_diagnostic": [
            row["episode_id"] for row in rows if row["mixed_or_diagnostic"]
        ],
    }
    (args.output_dir / "evaluation_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["overall"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
