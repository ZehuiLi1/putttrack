#!/usr/bin/env python3
"""Attach independent observed event times; never infer truth from a plan."""

import argparse, hashlib, json, math, pathlib


def times(text, duration):
    values = [] if not text.strip() else [float(v) for v in text.split(",")]
    if any(not math.isfinite(v) or not 0 <= v <= duration for v in values):
        raise ValueError("event outside raw time span")
    if values != sorted(set(values)):
        raise ValueError("event times must be strictly increasing")
    return values


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("trial", type=pathlib.Path)
    p.add_argument("--session", required=True)
    p.add_argument("--operator", required=True)
    p.add_argument(
        "--putter-times", required=True, help="seconds after GO; empty string for zero"
    )
    p.add_argument("--pickup-times", required=True)
    p.add_argument("--collision-times", required=True)
    p.add_argument(
        "--truth-source", choices=("video_review", "operator_review"), required=True
    )
    p.add_argument(
        "--reference",
        required=True,
        help="video reference or description of independent observation",
    )
    p.add_argument(
        "--split", choices=("development", "prospective_holdout"), required=True
    )
    args = p.parse_args()
    raw = (args.trial / "raw.jsonl").read_bytes()
    records = [json.loads(line) for line in raw.splitlines() if line.strip()]
    markers = [
        r["source_monotonic_us"]
        for r in records
        if r.get("record_type") == "tag_episode_marker"
    ]
    sample_times = [
        r["source_monotonic_us"]
        for r in records
        if r.get("record_type") == "tag_motion"
    ]
    if len(markers) != 1 or not sample_times:
        raise ValueError("missing unique GO/raw samples")
    results = [r for r in records if r.get("record_type") == "tag_capture_result"]
    if len(results) != 1 or results[0].get("status") != "PASS":
        raise ValueError("raw capture did not pass")
    duration = (max(sample_times) - markers[0]) / 1e6
    obj = {
        "schema_version": 1,
        "authority": False,
        "truth_source": args.truth_source,
        "reference": args.reference,
        "session": args.session,
        "operator": args.operator,
        "split": args.split,
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
        "putter_times_from_go_s": times(args.putter_times, duration),
        "pickup_times_from_go_s": times(args.pickup_times, duration),
        "collision_times_from_go_s": times(args.collision_times, duration),
        "duration_s": duration,
    }
    with (args.trial / "truth.json").open("x") as f:
        json.dump(obj, f, indent=2, sort_keys=True)
        f.write("\n")
    print(args.trial / "truth.json")


if __name__ == "__main__":
    main()
