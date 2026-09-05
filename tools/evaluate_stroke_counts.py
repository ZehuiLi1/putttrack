#!/usr/bin/env python3
"""Evaluate reviewed episode counts; this tool does not detect strokes."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def count(value, field):
    if type(value) is not int or value < 0:
        raise ValueError(f"{field} must be a nonnegative integer")
    return value


def summarize(rows):
    decided = [row for row in rows if row["predicted_strokes"] is not None]
    errors = [row["predicted_strokes"] - row["actual_strokes"] for row in decided]
    return {
        "episodes": len(rows),
        "decided": len(decided),
        "unknown": len(rows) - len(decided),
        "exact_count_episodes": sum(error == 0 for error in errors),
        "overcount_strokes": sum(max(0, error) for error in errors),
        "undercount_strokes": sum(max(0, -error) for error in errors),
        "coverage": len(decided) / len(rows) if rows else None,
        "exact_count_rate_all_episodes": sum(error == 0 for error in errors) / len(rows) if rows else None,
        "mean_absolute_count_error_decided": sum(abs(error) for error in errors) / len(errors) if errors else None,
    }


def evaluate(payload):
    if payload.get("schema_version") != 1 or type(payload.get("schema_version")) is not int:
        raise ValueError("schema_version must be 1")
    if not isinstance(payload.get("detector_id"), str) or not payload["detector_id"].strip():
        raise ValueError("detector_id is required")
    rows = payload.get("episodes")
    if not isinstance(rows, list) or not rows:
        raise ValueError("episodes must be a nonempty list")
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("episode must be an object")
        for field in ("episode_id", "session_id", "scenario", "truth_source", "raw_capture"):
            if not isinstance(row.get(field), str) or not row[field].strip():
                raise ValueError(f"{field} is required")
        if row["episode_id"] in seen:
            raise ValueError("duplicate episode_id")
        seen.add(row["episode_id"])
        if row.get("operator_reviewed") is not True:
            raise ValueError("operator_reviewed must be true; planned counts are not truth")
        count(row.get("actual_strokes"), "actual_strokes")
        if "predicted_strokes" not in row:
            raise ValueError("predicted_strokes is required; use null for UNKNOWN")
        if row["predicted_strokes"] is not None:
            count(row["predicted_strokes"], "predicted_strokes")
        elif not isinstance(row.get("unknown_reason"), str) or not row["unknown_reason"].strip():
            raise ValueError("UNKNOWN requires unknown_reason")
    groups = {
        field: {key: summarize([row for row in rows if row[field] == key])
                for key in sorted({row[field] for row in rows})}
        for field in ("scenario", "session_id")
    }
    return {
        "schema_version": 1,
        "detector_id": payload["detector_id"],
        "authority": False,
        "overall": summarize(rows),
        "groups": groups,
        "limitations": [
            "Count agreement can hide one missed stroke plus one false stroke; event timing requires separate review.",
            "Input review/provenance are declared by the operator; this tool does not verify raw IMU or video.",
            "An episode is not necessarily a complete hole. No collision-source accuracy is inferred.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = args.input.read_bytes()
    result = evaluate(json.loads(raw))
    result["input_sha256"] = hashlib.sha256(raw).hexdigest()
    with args.output.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
