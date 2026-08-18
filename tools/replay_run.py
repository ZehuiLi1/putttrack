#!/usr/bin/env python3
"""Replay a captured PuttTrack evidence run twice and compare authority state."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from putttrack.evidence import DeterministicReplay, engine_from_session_file  # noqa: E402
from putttrack.recording import load_manifest  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--events", default="events.jsonl")
    parser.add_argument("--session", default="session.json")
    parser.add_argument("--allow-quarantine", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_dir = args.run_dir
    manifest = load_manifest(run_dir / "manifest.json")
    events = run_dir / args.events
    session = run_dir / args.session
    factory = lambda: engine_from_session_file(session)
    first, second = DeterministicReplay().assert_deterministic(events, factory)

    summary = {
        "run_id": manifest.run_id,
        "manifest_digest": manifest.digest(),
        "authoritative_digest_first": first.authoritative_digest,
        "authoritative_digest_second": second.authoritative_digest,
        "deterministic": first.authoritative_digest == second.authoritative_digest,
        "accepted_record_count": first.accepted_record_count,
        "gameplay_input_count": first.gameplay_input_count,
        "quarantine_count": len(first.quarantines),
        "authoritative_snapshot": first.authoritative_snapshot,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    if not summary["deterministic"]:
        return 2
    if first.quarantines and not args.allow_quarantine:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
