# Bbo Channel Sounding Bring-Up Notes

## 1. Purpose

Use the vendor-supplied images only to prove the RF/boot/serial path before PuttTrack invests in custom scheduling, logging and localisation firmware.

Canonical archive identity and binary hashes are in [`SOURCE_MANIFEST.md`](SOURCE_MANIFEST.md).

## 2. Gate 0 — zero-custom-code smoke test

Use two Bbo boards:

```text
Bbo A -> channel_sounding_ras_initiator.signed.bin
Bbo B -> channel_sounding_ras_reflector.signed.bin
```

Preferred first programming path: vendor serial bootloader over Type-C/CH340. Avoid an unnecessary first-step SWD mass erase; the vendor guide states that SWD/J-Link can remove the default serial bootloader and identifies `release_boot_01.hex` as recovery.

Gate 0 passes only when the Initiator repeatedly emits the expected sample markers, including:

- `Starting Channel Sounding Initiator Sample`
- `Ranging data ready`
- `Distance estimates on antenna path ...`
- numeric `ifft`, `phase_slope` and `rtt` values.

Record the exact firmware hash and host/serial configuration in the test log.

## 3. Stock-image limitation

The supplied Initiator image contains `Sleeping for a few seconds...`. Do not use this stock image to set the product tracking-rate claim or multi-ball scheduling architecture.

After smoke test, rebuild the Nordic sample from pinned NCS source and move to a PuttTrack-owned scheduler/logger.

## 4. First range-baseline dataset

Before 2D localisation, collect a single-link baseline at:

```text
0.5 m
1.0 m
2.0 m
3.0 m
5.0 m
8.0 m
10.0 m
```

At each distance, capture enough repeated procedures to report distributions rather than a few hand-read values. The Phase-1 matrix must include:

- Anchor orientation: 0/90/180/270 degrees minimum;
- moving-target/Reflector orientation;
- near-ground geometry;
- body blockage;
- wall/corner proximity;
- representative metal/course features;
- final/enclosure variants when available.

Recommended minimum record fields:

```text
schema_version
device_id
boot_id
firmware_id
ncs_version
anchor_id
ball_or_reflector_id
source_monotonic_time
sequence
procedure_id
antenna_path
ifft_m
phase_slope_m
rtt_m
rssi_dbm
quality/status fields
truth_distance_m
anchor_orientation_deg
reflector_orientation_deg
condition
config_digest
```

Do not collapse the record to one convenience distance.

## 5. Hardware comparison order

The first goal is to establish a reproducible baseline, not to replace hardware before measuring it.

Recommended order:

1. Bbo Initiator <-> Bbo Reflector — prove vendor path and collect baseline.
2. Bbo Initiator <-> Nordic nRF54L15 Tag Reflector — moving-target reference interoperability.
3. Fixed-Anchor candidate comparison — Bbo board RF versus XIAO nRF54L15 with controlled external FPC installation, using identical truth geometry.
4. Ball prototype comparison — compact XIAO nRF54L15 Sense candidate versus Nordic nRF54L15 Tag reference under random orientation/rolling/multipath.
5. Only after those measurements, decide whether dual-antenna capability belongs in the production Ball and whether it earns cost/complexity on fixed Anchors.

The XIAO candidates are an experiment proposal, not facts derived from the Bbo package.

## 6. Analysis outputs required

For every hardware/configuration pair report:

- bias by truth distance;
- MAE and RMSE;
- P50/P90/P95 absolute error;
- missing/no-fix rate;
- severe-outlier rate;
- orientation-conditioned tails;
- obstruction-conditioned tails;
- estimator disagreement (`ifft` vs `phase_slope` vs `rtt`);
- procedure/update timing.

Antenna/diversity changes should be judged primarily by tail error, no-fix/outlier behavior and installation robustness, not only mean/P50.

## 7. Exit to multi-Anchor work

Proceed to the 3/4/5-Anchor static localisation matrix only when:

- CS procedures are repeatable;
- source-built firmware/versioning is reproducible;
- logs are machine-parseable with source timestamps and gap/duplicate handling;
- the single-link dataset has enough coverage to define calibration and measurement rejection rules;
- Bbo/Tag interoperability is demonstrated if the Tag remains the moving reference.
