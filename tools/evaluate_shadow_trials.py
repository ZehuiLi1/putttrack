#!/usr/bin/env python3
"""Count AND one-to-one timing audit on independently reviewed physical trials.
Unknowns and journal loss remain visible; candidate totals are not confirmed scores.
"""

import argparse, hashlib, json, math, pathlib


def match_times(predicted, truth, tolerance):
    p = sorted(predicted)
    t = sorted(truth)
    i = j = 0
    errors = []
    while i < len(p) and j < len(t):
        if abs(p[i] - t[j]) <= tolerance:
            errors.append(p[i] - t[j])
            i += 1
            j += 1
        elif p[i] < t[j] - tolerance:
            i += 1
        else:
            j += 1
    return {
        "matched": len(errors),
        "unmatched_candidates": len(p) - len(errors),
        "missed_truth_events": len(t) - len(errors),
        "onset_errors_s": errors,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("trials", nargs="+", type=pathlib.Path)
    p.add_argument("--tolerance", type=float, default=0.25)
    p.add_argument("--output", type=pathlib.Path, required=True)
    args = p.parse_args()
    if not math.isfinite(args.tolerance) or args.tolerance < 0:
        raise ValueError("invalid tolerance")
    rows = []
    for path in args.trials:
        raw = (path / "raw.jsonl").read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        truth = json.loads((path / "truth.json").read_text())
        result = json.loads((path / "trial-result.json").read_text())
        if sha != truth["raw_sha256"] or sha != result["raw_capture_sha256"]:
            raise ValueError("truth/raw/result hash mismatch")
        if result.get("authority") is not False or truth.get("authority") is not False:
            raise ValueError("authority violation")
        records = [json.loads(line) for line in raw.splitlines() if line.strip()]
        go = [
            r["source_monotonic_us"]
            for r in records
            if r.get("record_type") == "tag_episode_marker"
        ]
        if len(go) != 1:
            raise ValueError("unique GO required")
        events = result["events"]
        stroke = [(e["onset_us"] - go[0]) / 1e6 for e in events if e["type"] == 1]
        pickup = [(e["onset_us"] - go[0]) / 1e6 for e in events if e["type"] == 2]
        row = {
            "trial": str(path),
            "session": truth["session"],
            "operator": truth["operator"],
            "split": truth["split"],
            "config_sha256": result["config_sha256"],
            "scenario": result["scenario"],
            "count_status": result["count_status"],
            "journal_loss": result["journal_loss"],
            "unresolved_events": result["unresolved_events"],
            "observed_stroke_candidates": len(stroke),
            "actual_putter_contacts": len(truth["putter_times_from_go_s"]),
            "exact_candidate_count_agreement": len(stroke)
            == len(truth["putter_times_from_go_s"]),
            "stroke_event_audit": match_times(
                stroke, truth["putter_times_from_go_s"], args.tolerance
            ),
            "pickup_event_audit": match_times(
                pickup, truth["pickup_times_from_go_s"], args.tolerance
            ),
            "authority": False,
        }
        rows.append(row)
    output = {
        "authority": False,
        "scope": "shadow candidate audit, not validated game decisions",
        "timing_tolerance_s": args.tolerance,
        "reviewed_trials": len(rows),
        "incomplete_journals": sum(r["journal_loss"] for r in rows),
        "unresolved_trials": sum(r["unresolved_events"] > 0 for r in rows),
        "rows": rows,
        "warning": "Do not treat UNKNOWN as zero. Equal total counts can hide a missed putter contact plus a false collision event. Do not tune on prospective holdout.",
    }
    with args.output.open("x") as f:
        json.dump(output, f, sort_keys=True, indent=2)
        f.write("\n")
    print(args.output)


if __name__ == "__main__":
    main()
