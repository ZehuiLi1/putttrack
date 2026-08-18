# Phase 0 — nRF54L15 Channel Sounding Capture

## Purpose

This directory is ready for Issue #1 hardware work. It defines experiment metadata and fixtures without claiming any physical Bbo/Nordic measurement has passed.

## Required order

1. Verify the retained vendor archive/hash against `docs/hardware/bbo-nrf54l15dk/SOURCE_MANIFEST.md`.
2. Bbo Initiator ↔ Bbo Reflector vendor-image smoke test.
3. Rebuild/pin the Nordic sample and record exact NCS/toolchain/firmware hashes.
4. Bbo Initiator ↔ Nordic Tag Reflector.
5. 30-minute fixed 1 m and 3 m stability runs.
6. Complete the distance/orientation/near-ground/NLOS matrix in `matrix.json`.

## Fixture verification

```bash
python tools/verify.py
```

or run the capture CLI directly:

```bash
PYTHONPATH=src python tools/capture_cs.py \
  --input experiments/phase0_cs/fixtures/bbo_vendor_smoke.log \
  --run-root /tmp/putttrack-runs \
  --run-id fixture \
  --anchor-id A \
  --reflector-id ball-reference \
  --truth-distance-m 1.0 \
  --condition fixture \
  --firmware-version vendor-fixture \
  --ncs-version 3.0.2-fixture \
  --anchor-config configs/anchors/phase0.example.json \
  --max-records 2
```

This produces:

```text
manifest.json
manifest.json.sha256
raw_serial.log
ranges.jsonl
capture_summary.json
```

## Real serial capture

Install the hardware extra:

```bash
pip install '.[hardware]'
```

Then replace `--input` with a port:

```bash
PYTHONPATH=src python tools/capture_cs.py \
  --port COM5 \
  --baud 115200 \
  --run-root runs/phase0_cs \
  --anchor-id A \
  --reflector-id nordic-tag-001 \
  --truth-distance-m 1.0 \
  --condition los_bench \
  --firmware-version <exact-hash-or-version> \
  --ncs-version <exact-version> \
  --anchor-config configs/anchors/phase0.example.json
```

Do not use the fixture or vendor stock image to claim tracking rate, multi-ball capacity, power or accuracy. Those require real source-built hardware evidence.
