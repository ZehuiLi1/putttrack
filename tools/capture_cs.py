#!/usr/bin/env python3
"""Capture Bbo/Nordic Channel Sounding output into canonical PuttTrack evidence.

The CLI can read a real serial port (optional pyserial dependency), stdin, or a
fixture file. Hardware-free fixture capture is intentionally supported so the
pipeline can be verified before the boards arrive.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, TextIO

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from putttrack.contracts import RangeObservation  # noqa: E402
from putttrack.cs import CsParseError, CsSerialParser  # noqa: E402
from putttrack.recording import (  # noqa: E402
    AppendOnlyJsonlWriter,
    RunManifest,
    config_hashes,
    write_immutable_manifest,
)

TOOL_VERSION = "capture-cs/1.2"


def _event_id(device_id: str, boot_id: str, sequence: int) -> str:
    namespace = uuid.UUID("7e204de2-6dbc-4d36-a1cf-f2f3ec694ba1")
    return f"rng-{uuid.uuid5(namespace, f'{device_id}:{boot_id}:{sequence}')}"


def _load_anchor_config(
    path: Path | None, anchor_id: str
) -> tuple[dict, tuple[float, float, float] | None]:
    if path is None:
        return {}, None
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("anchor config must be a JSON object")
    anchors = raw.get("anchors", {})
    anchor = anchors.get(anchor_id, {}) if isinstance(anchors, dict) else {}
    coordinate = anchor.get("coordinate_m") if isinstance(anchor, dict) else None
    parsed_coordinate = (
        tuple(float(value) for value in coordinate)
        if isinstance(coordinate, list) and len(coordinate) == 3
        else None
    )
    return raw, parsed_coordinate


@contextmanager
def _input_stream(args: argparse.Namespace) -> Iterator[TextIO]:
    if args.port:
        try:
            import serial  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError(
                "serial capture requires pyserial: pip install '.[hardware]'"
            ) from exc
        stream = serial.Serial(args.port, args.baud, timeout=args.timeout)
        text = None
        try:
            import io

            text = io.TextIOWrapper(
                io.BufferedReader(stream), encoding="utf-8", errors="replace"
            )
            yield text
        finally:
            if text is not None:
                text.detach()
            stream.close()
    elif args.input:
        with Path(args.input).open("r", encoding="utf-8", errors="replace") as handle:
            yield handle
    else:
        yield sys.stdin


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--port", help="serial port such as COM5 or /dev/ttyUSB0")
    source.add_argument("--input", help="fixture/text file; stdin is default")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--timeout", type=float, default=1.0)
    parser.add_argument("--run-root", default="runs/phase0_cs")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--anchor-id", required=True)
    parser.add_argument("--reflector-id", required=True)
    parser.add_argument("--zone-id", default="LAB")
    parser.add_argument("--hole-id", default="H-LAB")
    parser.add_argument("--rf-cell-id", default="CELL-LAB")
    parser.add_argument(
        "--source-boot-id",
        default=None,
        help=(
            "fallback boot domain for vendor logs that do not emit source_boot_id; "
            "source-built structured telemetry overrides this per record"
        ),
    )
    parser.add_argument("--truth-distance-m", type=float, default=None)
    parser.add_argument("--condition", default="unspecified")
    parser.add_argument("--anchor-orientation-deg", type=float, default=None)
    parser.add_argument("--reflector-orientation-deg", type=float, default=None)
    parser.add_argument("--firmware-version", default="unknown")
    parser.add_argument("--ncs-version", default=None)
    parser.add_argument("--config-version", default="phase0-capture-v1")
    parser.add_argument("--calibration-version", default="uncalibrated")
    parser.add_argument("--git-sha", default=os.environ.get("PUTTTRACK_GIT_SHA", "unknown"))
    parser.add_argument("--anchor-config", type=Path, default=None)
    parser.add_argument("--max-records", type=int, default=0, help="0 means unlimited")
    parser.add_argument("--no-fsync", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_id = args.run_id or datetime.now(timezone.utc).strftime("phase0-%Y%m%dT%H%M%SZ")
    run_dir = Path(args.run_root) / run_id
    if run_dir.exists():
        raise SystemExit(f"run directory already exists: {run_dir}")
    run_dir.mkdir(parents=True)

    anchor_config, coordinate = _load_anchor_config(args.anchor_config, args.anchor_id)
    config_paths = [args.anchor_config] if args.anchor_config else []
    fallback_boot_id = args.source_boot_id or f"capture-boot-{uuid.uuid4()}"

    condition = {
        "name": args.condition,
        "truth_distance_m": args.truth_distance_m,
        "anchor_orientation_deg": args.anchor_orientation_deg,
        "reflector_orientation_deg": args.reflector_orientation_deg,
        "input_mode": "serial" if args.port else "file" if args.input else "stdin",
    }
    board_identities = {
        args.anchor_id: {
            "class": "anchor",
            "port": args.port,
            "baud": args.baud if args.port else None,
            "config": anchor_config.get("anchors", {}).get(args.anchor_id, {}),
        }
    }
    manifest = RunManifest.for_current_host(
        run_id=run_id,
        git_sha=args.git_sha,
        tool_version=TOOL_VERSION,
        firmware_versions={args.anchor_id: args.firmware_version},
        ncs_version=args.ncs_version,
        board_identities=board_identities,
        anchor_coordinates_m={args.anchor_id: coordinate} if coordinate else {},
        ball_identity={"ball_id": args.reflector_id, "role": "reflector"},
        experiment_condition=condition,
        calibration_version=args.calibration_version,
        camera_metadata={},
        config_hash_values=config_hashes(config_paths),
        command=sys.argv if argv is None else ["capture_cs.py", *argv],
        environment={"PYTHONPATH": os.environ.get("PYTHONPATH", "")},
        notes=(
            "Phase-0 capture tooling; no hardware-performance claim is implied. "
            "Vendor text uses capture/CLI identity fallbacks; source-built telemetry "
            "should emit source_device_id, source_boot_id, source_monotonic_ns and "
            "source_sequence."
        ),
    )
    write_immutable_manifest(run_dir / "manifest.json", manifest)

    raw_path = run_dir / "raw_serial.log"
    record_writer = AppendOnlyJsonlWriter(
        run_dir / "ranges.jsonl", fsync=not args.no_fsync
    )
    parser = CsSerialParser()
    local_sequence = 0
    captured = 0
    parse_errors = 0
    identity_mismatches = 0
    observed_boot_ids: set[str] = set()
    observed_device_ids: set[str] = set()
    device_timestamp_records = 0
    device_sequence_records = 0
    device_boot_records = 0
    device_id_records = 0

    with _input_stream(args) as stream, raw_path.open("a", encoding="utf-8") as raw_handle:
        for line_number, line in enumerate(stream, start=1):
            edge_time = time.monotonic_ns()
            raw_handle.write(line if line.endswith("\n") else line + "\n")
            raw_handle.flush()
            if not args.no_fsync:
                os.fsync(raw_handle.fileno())
            try:
                estimate = parser.parse_line(line)
            except CsParseError as exc:
                parse_errors += 1
                print(f"parse error line {line_number}: {exc}", file=sys.stderr)
                continue
            if estimate is None:
                continue

            if (
                estimate.source_device_id is not None
                and estimate.source_device_id != args.anchor_id
            ):
                identity_mismatches += 1
                print(
                    f"source device mismatch line {line_number}: firmware={estimate.source_device_id!r} "
                    f"capture_anchor={args.anchor_id!r}",
                    file=sys.stderr,
                )
                continue

            local_sequence += 1
            sequence = (
                estimate.source_sequence
                if estimate.source_sequence is not None
                else local_sequence
            )
            source_time = (
                estimate.source_monotonic_ns
                if estimate.source_monotonic_ns is not None
                else edge_time
            )
            effective_boot_id = estimate.source_boot_id or fallback_boot_id
            observed_boot_ids.add(effective_boot_id)
            if estimate.source_device_id is not None:
                observed_device_ids.add(estimate.source_device_id)
            device_timestamp_records += int(estimate.source_monotonic_ns is not None)
            device_sequence_records += int(estimate.source_sequence is not None)
            device_boot_records += int(estimate.source_boot_id is not None)
            device_id_records += int(estimate.source_device_id is not None)

            quality = {
                **estimate.quality,
                "truth_distance_m": args.truth_distance_m,
                "condition": args.condition,
                "anchor_orientation_deg": args.anchor_orientation_deg,
                "reflector_orientation_deg": args.reflector_orientation_deg,
                "capture_line_number": line_number,
            }
            record = RangeObservation(
                event_id=_event_id(args.anchor_id, effective_boot_id, sequence),
                event_type="cs.range_observed",
                source_device_id=args.anchor_id,
                source_boot_id=effective_boot_id,
                sequence=sequence,
                source_monotonic_ns=source_time,
                edge_received_ns=edge_time,
                trace_id=f"run:{run_id}",
                correlation_id=estimate.procedure_id,
                zone_id=args.zone_id,
                hole_id=args.hole_id,
                ball_id=args.reflector_id,
                firmware_version=args.firmware_version,
                config_version=args.config_version,
                calibration_version=args.calibration_version,
                raw_evidence_refs=(f"raw_serial.log#line={line_number}",),
                wall_time=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                anchor_id=args.anchor_id,
                rf_cell_id=args.rf_cell_id,
                procedure_id=estimate.procedure_id,
                antenna_path=estimate.antenna_path,
                distance_ifft_m=estimate.distance_ifft_m,
                distance_phase_m=estimate.distance_phase_m,
                distance_rtt_m=estimate.distance_rtt_m,
                rssi_dbm=estimate.rssi_dbm,
                quality=quality,
                anchor_position_m=coordinate,
            )
            record_writer.append(record)
            captured += 1
            if args.max_records and captured >= args.max_records:
                break

    summary = {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "captured_records": captured,
        "parse_errors": parse_errors,
        "identity_mismatches": identity_mismatches,
        "hardware_validated": False,
        "observed_source_boot_ids": sorted(observed_boot_ids),
        "observed_source_device_ids": sorted(observed_device_ids),
        "device_timestamp_records": device_timestamp_records,
        "device_sequence_records": device_sequence_records,
        "device_boot_records": device_boot_records,
        "device_id_records": device_id_records,
        "source_identity_complete": (
            captured > 0
            and identity_mismatches == 0
            and device_timestamp_records == captured
            and device_sequence_records == captured
            and device_boot_records == captured
            and device_id_records == captured
        ),
    }
    (run_dir / "capture_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if captured > 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
