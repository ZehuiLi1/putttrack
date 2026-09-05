#!/usr/bin/env python3
"""Replay the identical MCU C engine on all unique raw captures.
Labels and GO times never enter the C engine. Operator episode labels are
reported as proxies only, never as independent putter-contact timing truth.
"""

from __future__ import annotations
import argparse, collections, csv, hashlib, json, pathlib, shutil, subprocess, tempfile, zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]


def digest(b):
    return hashlib.sha256(b).hexdigest()


def canonical(o):
    return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def write_json(p, o):
    p.write_text(json.dumps(o, ensure_ascii=False, sort_keys=True, indent=2) + "\n")


def write_csv(p, rows):
    keys = sorted({k for r in rows for k in r})
    with p.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def inventory(root=ROOT):
    items = {}
    duplicates = []
    manifest_meta = {}
    for m in sorted((root / "experiments").glob("**/manifest.json")):
        data = json.loads(m.read_text())
        if not isinstance(data, dict) or "episodes" not in data:
            continue
        for e0 in data["episodes"]:
            e = {**data.get("defaults", {}), **e0}
            if "capture" not in e:
                continue
            manifest_meta[(m.parent / e["capture"]).resolve()] = {
                **e,
                "manifest": str(m.relative_to(root)),
                "dataset_id": data.get("dataset_id", ""),
            }
    for p in sorted((root / "experiments").glob("**/*.jsonl")):
        b = p.read_bytes()
        if b'"tag_motion"' not in b:
            continue
        sha = digest(b)
        meta = manifest_meta.get(p.resolve(), {})
        item = {
            "sha": sha,
            "raw": b,
            "source": str(p.relative_to(root)),
            "metadata": meta,
            "category": "reviewed" if meta else "unmanifested",
        }
        if sha in items:
            duplicates.append(
                {
                    "sha256": sha,
                    "source": item["source"],
                    "canonical": items[sha]["source"],
                }
            )
        else:
            items[sha] = item
    for archive in sorted((root / "datasets").glob("*.zip")):
        with zipfile.ZipFile(archive) as z:
            matches = [n for n in z.namelist() if n.endswith("/MANIFEST.json")]
            for manifest in matches:
                entries = json.loads(z.read(manifest))
                prefix = manifest[: -len("MANIFEST.json")]
                if not isinstance(entries, list):
                    continue
                for meta in entries:
                    name = prefix + meta["packaged_path"]
                    b = z.read(name)
                    sha = digest(b)
                    if sha != meta["sha256"]:
                        raise ValueError("archive hash mismatch: " + name)
                    if b'"tag_motion"' not in b:
                        continue
                    source = str(archive.relative_to(root)) + "::" + name
                    if sha in items:
                        duplicates.append(
                            {
                                "sha256": sha,
                                "source": source,
                                "canonical": items[sha]["source"],
                            }
                        )
                        continue
                    items[sha] = {
                        "sha": sha,
                        "raw": b,
                        "source": source,
                        "metadata": meta,
                        "category": meta.get("category", "archive_unknown"),
                    }
    return sorted(items.values(), key=lambda e: e["source"]), duplicates


def decode_capture(b):
    recs = []
    issues = []
    for i, line in enumerate(b.splitlines(), 1):
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except (ValueError, UnicodeError):
            issues.append("malformed_json")
            continue
        if not isinstance(r, dict):
            issues.append("non_object")
            continue
        recs.append(r)
    motion = [r for r in recs if r.get("record_type") == "tag_motion"]
    status = [
        r for r in recs if r.get("record_type") in ("tag_status", "tag_status_final")
    ]
    go = [
        r.get("source_monotonic_us")
        for r in recs
        if r.get("record_type") == "tag_episode_marker"
    ]
    if len(go) > 1:
        issues.append("multiple_go")
    for key in ("device_id", "boot_id"):
        vals = {r[key] for r in status if r.get(key)}
        if len(vals) > 1:
            issues.append("mixed_" + key)
    results = [r for r in recs if r.get("record_type") == "tag_capture_result"]
    if any(r.get("status") != "PASS" for r in results):
        issues.append("capture_result_failed")
    stream = [r.get("stream_rate_hz") for r in status if r.get("stream_rate_hz")]
    if any(r != 50 for r in stream):
        issues.append("unsupported_stream_rate")
    return motion, status, go[0] if len(go) == 1 else None, sorted(set(issues))


def engine_input(motion):
    lines = []
    for r in motion:
        fields = [
            r["sequence"],
            r["source_monotonic_us"],
            *r["bmi270_accel_micro_ms2"],
            *r["bmi270_gyro_micro_rads"],
            int(r["bmi270_valid"]),
            r["sensor_error_bits"],
        ]
        if len(fields) != 10 or any(type(v) is not int for v in fields):
            raise ValueError("invalid integer sample")
        if (
            not 0 <= fields[0] < 2**32
            or not 0 <= fields[1] < 2**64
            or not all(-(2**31) <= v < 2**31 for v in fields[2:8])
        ):
            raise ValueError("sample outside wire bounds")
        lines.append(",".join(map(str, fields)))
    return "\n".join(lines) + "\n"


def run(runner, b):
    motion, status, go, issues = decode_capture(b)
    result = subprocess.run(
        [str(runner)],
        input=engine_input(motion),
        capture_output=True,
        text=True,
        check=True,
    )
    output = [json.loads(s) for s in result.stdout.splitlines()]
    summary = output[-1]
    events = output[:-1]
    if summary["samples"] != len(motion):
        raise ValueError("sample mismatch")
    return motion, status, go, issues, summary, events


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output-dir", type=pathlib.Path, required=True)
    p.add_argument("--initial-baseline", action="store_true")
    args = p.parse_args()
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    cc = shutil.which("cc") or shutil.which("gcc")
    if not cc:
        raise SystemExit("C11 compiler required")
    src = (
        ROOT / "tools/research_baselines/stroke_pickup_initial"
        if args.initial_baseline
        else ROOT / "firmware/nrf54l15_tag_app/src"
    )
    captures, dups = inventory()
    rows = []
    all_events = []
    groups = collections.defaultdict(list)
    with tempfile.TemporaryDirectory(dir=pathlib.Path.home()) as temp:
        runner = pathlib.Path(temp) / "runner"
        subprocess.run(
            [
                cc,
                "-std=c11",
                "-O2",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-pedantic",
                "-I" + str(src),
                str(src / "stroke_pickup_v1.c"),
                str(ROOT / "tools/c/stroke_pickup_v1_replay.c"),
                "-lm",
                "-o",
                str(runner),
            ],
            check=True,
        )
        for item in captures:
            meta = item["metadata"]
            motion, status, go, issues, s, events = run(runner, item["raw"])
            post = [e for e in events if go is None or e["onset_us"] >= go]
            label = meta.get("label", meta.get("episode_label", "unlabelled"))
            row = {
                "source": item["source"],
                "sha256": item["sha"],
                "category": item["category"],
                "label": label,
                "episode_id": meta.get("episode_id", pathlib.Path(item["source"]).stem),
                "manifest": meta.get("manifest", ""),
                "archival_quality": meta.get("quality", ""),
                "session": meta.get("session", "unspecified"),
                "operator": meta.get("operator", "unspecified"),
                "surface": meta.get("surface", "unspecified"),
                "samples": len(motion),
                "go_us": go if go is not None else "",
                "raw_issues": ";".join(issues),
                "stroke_candidates": sum(e["type"] == 1 for e in post),
                "pickup_candidates": sum(e["type"] == 2 for e in post),
                "ambiguous_contacts": sum(e["type"] == 3 for e in post),
                "unknown_onsets": sum(e["type"] == 4 for e in post),
                "quality_breaks": s["quality_breaks"],
                "context_bytes": s["context_bytes"],
                "count_incomplete": s["count_incomplete"],
                "bmi_accel_near_rail_samples": sum(
                    max(map(abs, r["bmi270_accel_micro_ms2"])) >= 153768272
                    for r in motion
                ),
                "bmi_gyro_near_rail_samples": sum(
                    max(map(abs, r["bmi270_gyro_micro_rads"])) >= 34208453
                    for r in motion
                ),
                "interpretation": (
                    "post_GO_operator_proxy"
                    if go is not None and meta.get("manifest")
                    else "exploratory_only"
                ),
                "event_truth": "UNAVAILABLE",
                "authority": False,
            }
            rows.append(row)
            groups[(item["category"], str(label))].append(row)
            for e in events:
                all_events.append(
                    {
                        "capture_sha256": item["sha"],
                        "source": item["source"],
                        "post_go": go is None or e["onset_us"] >= go,
                        "authority": False,
                        **e,
                    }
                )
    write_csv(out / "capture_results.csv", rows)
    with (out / "events.jsonl").open("w") as f:
        for e in all_events:
            f.write(canonical(e) + "\n")
    gr = []
    for (cat, label), rr in sorted(groups.items()):
        gr.append(
            {
                "category": cat,
                "label": label,
                "captures": len(rr),
                "samples": sum(r["samples"] for r in rr),
                "captures_with_stroke_candidate": sum(
                    r["stroke_candidates"] > 0 for r in rr
                ),
                "captures_with_pickup_candidate": sum(
                    r["pickup_candidates"] > 0 for r in rr
                ),
                "stroke_candidates": sum(r["stroke_candidates"] for r in rr),
                "pickup_candidates": sum(r["pickup_candidates"] for r in rr),
                "ambiguous_contacts": sum(r["ambiguous_contacts"] for r in rr),
                "raw_issue_captures": sum(bool(r["raw_issues"]) for r in rr),
            }
        )
    write_csv(out / "group_summary.csv", gr)
    reviewed = [r for r in rows if "pickup_precision" in r["manifest"]]
    clean = [
        r
        for r in reviewed
        if r["label"] == "putt_gentle"
        and r["episode_id"] != "putt-gentle-plus-obstacle-r05"
    ]
    rail = [r for r in reviewed if r["label"] == "putt_rail_collision"]
    positives = [r for r in reviewed if r["label"] in ("pickup_carry", "pickup_drop")]
    no_lift = [r for r in reviewed if r["label"] == "handling"]
    summary = {
        "algorithm_id": "stroke_pickup_shadow_v1",
        "config_sha256": s["config_sha256"],
        "authority": False,
        "source_base": "ad566404272dc6f5695cb84fd551df5921f7f619",
        "unique_raw_captures": len(rows),
        "raw_motion_samples": sum(r["samples"] for r in rows),
        "exact_duplicate_paths_excluded": len(dups),
        "context_bytes": s["context_bytes"],
        "code_sha256": digest((src / "stroke_pickup_v1.c").read_bytes()),
        "clean_gentle_operator_proxy": {
            "episodes": len(clean),
            "exactly_one_candidate": sum(r["stroke_candidates"] == 1 for r in clean),
            "zero_candidates": sum(r["stroke_candidates"] == 0 for r in clean),
            "more_than_one": sum(r["stroke_candidates"] > 1 for r in clean),
        },
        "rail_operator_proxy": {
            "episodes": len(rail),
            "exactly_one_candidate": sum(r["stroke_candidates"] == 1 for r in rail),
            "zero_candidates": sum(r["stroke_candidates"] == 0 for r in rail),
            "more_than_one": sum(r["stroke_candidates"] > 1 for r in rail),
        },
        "pickup_operator_proxy": {
            "episodes": len(positives),
            "episodes_with_candidate": sum(
                r["pickup_candidates"] > 0 for r in positives
            ),
            "total_candidates": sum(r["pickup_candidates"] for r in positives),
        },
        "no_lift_operator_proxy": {
            "episodes": len(no_lift),
            "episodes_with_pickup_candidate": sum(
                r["pickup_candidates"] > 0 for r in no_lift
            ),
            "episodes_with_stroke_candidate": sum(
                r["stroke_candidates"] > 0 for r in no_lift
            ),
        },
        "independent_contact_timing_truth": False,
        "commercial_accuracy": None,
        "known_challenges": {
            "manual_roll_episodes": sum(
                r["label"] == "rolling" and r["category"] == "reviewed" for r in rows
            ),
            "manual_roll_false_stroke_candidates": sum(
                r["stroke_candidates"]
                for r in rows
                if r["label"] == "rolling" and r["category"] == "reviewed"
            ),
            "rolling_pickup_episodes": sum(
                r["label"] == "rolling_pickup" for r in rows
            ),
            "rolling_pickup_episodes_with_pickup": sum(
                r["pickup_candidates"] > 0
                for r in rows
                if r["label"] == "rolling_pickup"
            ),
            "archived_normal_putt_episodes": sum(
                r["category"] == "07_field_putt" for r in rows
            ),
            "archived_normal_putt_with_one_candidate": sum(
                r["stroke_candidates"] == 1
                for r in rows
                if r["category"] == "07_field_putt"
            ),
            "formal_roller_episodes": sum(
                r["category"] == "05_roller_official" for r in rows
            ),
            "formal_roller_stroke_candidates": sum(
                r["stroke_candidates"]
                for r in rows
                if r["category"] == "05_roller_official"
            ),
        },
        "limitations": [
            "Development/replay observations, not independent testing.",
            "All contact-source and second-stroke semantics remain candidates.",
            "No label or GO marker enters the engine.",
            "Invalid/diagnostic captures are not semantic accuracy evidence.",
            "No adjacent-window split masquerades as independent validation.",
        ],
    }
    write_json(out / "summary.json", summary)
    write_json(out / "duplicate_paths.json", dups)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
