# PuttTrack Evidence Foundation V1

## Status

This implementation is the canonical software foundation for Issue #6. It converts the Architecture Constitution's evidence contract into executable Python types, append-only capture, immutable run manifests and deterministic replay.

It does **not** claim that Bbo or Nordic hardware has passed Phase 0. Hardware-dependent results remain open in Issue #1.

## Authority boundary

```text
RF / IMU / physical sensor
        -> typed observation
        -> append-only JSONL
        -> measurement / evidence processing
        -> EvidenceEvent
        -> sensor-independent adapter
        -> existing GameplayEvent
        -> deterministic GameplayEngine
```

`src/putttrack/gameplay/` remains unchanged. It imports no CS, UWB, Nordic or camera implementation.

## Typed contracts

`src/putttrack/contracts/` implements:

- `RangeObservation`
- `MotionObservation`
- `PhysicalSensorObservation`
- `TrackUpdate`
- `EvidenceEvent`
- persistable boundary `GameplayEvent`

Every record has a versioned envelope capable of carrying:

- schema and record/event type;
- event ID, trace/correlation ID;
- source device and source boot ID;
- source sequence and monotonic acquisition time;
- Edge receive time and optional wall time;
- venue/zone/hole/ball context;
- firmware/config/calibration/model versions;
- raw evidence references;
- forward-compatible additive extension fields.

## Schema compatibility

- `1.x` additive optional fields are accepted and retained in `extensions`.
- Unit or semantic changes require a new major version.
- Unknown major versions are quarantined and cannot silently enter authoritative Gameplay.
- Unknown record types or malformed mandatory fields are explicit decode errors/quarantines.

## Canonical capture

`AppendOnlyJsonlWriter` uses O_APPEND and optional fsync. JSONL is the canonical raw evidence source because it preserves:

- receive order;
- source timestamp and source sequence;
- original top-level extension fields;
- replay identifiers;
- crash-tail visibility.

A malformed final unterminated line is quarantined as a potential interrupted write. Corruption in the middle of a stream fails rather than being silently skipped.

## Parquet research export

`tools/export_parquet.py` derives one Parquet file per record type from accepted JSONL records. It requires the optional dependency:

```bash
pip install '.[research]'
python tools/export_parquet.py runs/<run>/ranges.jsonl runs/<run>/parquet
```

Parquet is never the only raw source. Unknown/quarantined evidence remains in JSONL and is not misrepresented as a valid typed row.

## Immutable run manifest

Every capture run creates `manifest.json` plus a SHA-256 sidecar. Creation is exclusive; existing manifests are never overwritten.

The manifest records:

- run ID and UTC start;
- host/platform/Python/tool version;
- Git SHA;
- firmware and NCS versions;
- board identities;
- Anchor coordinates;
- Ball identity;
- experimental condition;
- calibration and camera metadata;
- configuration hashes;
- executed command and selected environment metadata.

## Ordering and restart model

Records preserve source monotonic time, boot ID and sequence separately from Edge receive time. `OrderingTracker` reports:

- sequence gaps;
- duplicate sequence;
- out-of-order arrival;
- source clock regression;
- device reboot/new boot domain.

It never fabricates missing evidence.

## Deterministic replay

`DeterministicReplay`:

1. decodes JSONL in capture order;
2. quarantines incompatible schema/invalid records;
3. records source-order diagnostics;
4. adapts only confirmed `EvidenceEvent` / contract `GameplayEvent` records;
5. drives the existing idempotent Gameplay Engine;
6. produces a canonical authoritative snapshot and SHA-256 digest.

Run the checked-in example twice:

```bash
PYTHONPATH=src python tools/replay_run.py experiments/evidence_replay_example
```

The duplicate `stroke.confirmed` record has the same logical event ID and does not increment the stroke twice.

## Phase 0 capture

`tools/capture_cs.py` accepts:

- Bbo vendor RAS text logs;
- PuttTrack structured JSON lines;
- stdin or fixture files;
- real serial ports with optional `pyserial`.

Fixture example:

```bash
PYTHONPATH=src python tools/capture_cs.py \
  --input experiments/phase0_cs/fixtures/bbo_vendor_smoke.log \
  --run-root /tmp/putttrack-runs \
  --run-id fixture \
  --anchor-id A \
  --reflector-id ball-reference \
  --truth-distance-m 1.0 \
  --condition fixture \
  --anchor-config configs/anchors/phase0.example.json \
  --max-records 2
```

Real hardware capture uses `--port COMx` or `--port /dev/ttyUSBx` after installing `.[hardware]`.

Vendor text does not provide a device acquisition timestamp in the parsed distance line. The tool therefore marks host receive time as a fallback. Source-built firmware should emit source monotonic time and sequence directly before Phase 1 performance conclusions.

## Verifier

```bash
python tools/verify.py
```

The verifier runs:

- all Gameplay and foundation unit tests;
- gameplay simulator;
- deterministic replay fixture twice;
- Phase 0 fixture capture through the real CLI;
- contract/module imports;
- manifest/output validation;
- Parquet exporter dependency/path tests.

A nonzero exit code means the software foundation is not accepted.
