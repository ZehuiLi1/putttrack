#!/usr/bin/env python3
"""Attach operator/video stroke-count truth to one immutable raw capture."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path


def parse_contact_times(value: str) -> list[float]:
    if not value.strip():
        return []
    result = [float(item.strip()) for item in value.split(",")]
    if any(not math.isfinite(item) or item < 0 for item in result):
        raise ValueError("contact times must be finite nonnegative seconds")
    if result != sorted(result) or len(result) != len(set(result)):
        raise ValueError("contact times must be strictly increasing")
    return result


def build_review(args: argparse.Namespace) -> dict:
    if not args.capture.is_file():
        raise ValueError(f"capture not found: {args.capture}")
    if type(args.actual_strokes) is not int or args.actual_strokes < 0:
        raise ValueError("--actual-strokes must be nonnegative")
    for field in ("session_id", "scenario"):
        if not isinstance(getattr(args, field), str) or not getattr(args, field).strip():
            raise ValueError(f"--{field.replace('_', '-')} is required")
    contact_times = parse_contact_times(args.contact_times)
    if len(contact_times) != args.actual_strokes:
        raise ValueError("contact time count must equal --actual-strokes")
    raw = args.capture.read_bytes()
    if not raw.strip():
        raise ValueError("capture is empty")
    return {
        "schema_version": 1,
        "record_type": "stroke_count_truth",
        "episode_id": args.episode_id or args.capture.stem,
        "session_id": args.session_id.strip(),
        "scenario": args.scenario.strip(),
        "actual_strokes": args.actual_strokes,
        "contact_times_from_go_s": contact_times,
        "truth_source": args.truth_source,
        "operator_reviewed": True,
        "raw_capture": str(args.capture),
        "raw_capture_sha256": hashlib.sha256(raw).hexdigest(),
        "notes": args.notes,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "authority": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--actual-strokes", type=int, required=True)
    parser.add_argument(
        "--contact-times",
        required=True,
        help="comma-separated seconds after GO; use an empty value for zero strokes",
    )
    parser.add_argument(
        "--truth-source",
        choices=("operator_button", "video_review", "sensor_plus_video"),
        required=True,
    )
    parser.add_argument("--episode-id")
    parser.add_argument("--notes", default="")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or args.capture.with_suffix(".stroke-review.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    review = build_review(args)
    with output.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(review, indent=2, sort_keys=True) + "\n")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
