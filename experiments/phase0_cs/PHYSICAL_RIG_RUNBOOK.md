# Phase-0 Physical Rig Runbook

## Purpose

Make the first real nRF54L15 Channel Sounding measurements repeatable enough that they can support engineering and research decisions.

## 1. Equipment to prepare

Minimum:

- 5 Bbo nRF54L15 boards + 1 spare;
- 1–2 Nordic nRF54L15 Tags;
- Windows/Linux capture PC;
- powered USB hub(s) with individually identifiable cables where practical;
- tape measure and/or laser distance meter;
- non-conductive board stands;
- removable floor tape / chalk for coordinate marks;
- labels for A/B/C/D/E, SPARE, TAG-01, TAG-02;
- phone/camera for installation photos;
- optional low/oblique research camera;
- optional visible sync LED/marker.

Recommended:

- tripod/clamp for camera;
- spirit level;
- ruler/caliper for board RF-reference height;
- printed run sheet;
- extension lead/power arrangement that stays unchanged through a comparison block.

## 2. Coordinate convention

Define one right-handed lab/site frame before collecting multi-Anchor data:

```text
origin O = surveyed fixed mark
+x       = along test lane / course direction
+y       = left when looking +x
+z       = upward
```

Every Anchor coordinate refers to a documented physical RF/antenna reference point, not the board edge or enclosure corner.

For Phase-0 single-link truth record:

- Anchor reference point x/y/z;
- Reflector reference point x/y/z;
- direct separation;
- Anchor orientation;
- Reflector orientation;
- board/enclosure state.

## 3. Physical labels and identity

Before flashing:

| Label | Physical role |
|---|---|
| A | baseline Anchor 1 |
| B | baseline Anchor 2 |
| C | baseline Anchor 3 |
| D | baseline Anchor 4 |
| E | experimental reference / fifth node |
| SPARE | replacement/development |

Photograph each physical label beside the board revision/serial evidence.

For source-built telemetry, firmware `source_device_id` must match the physical label and `tools/capture_cs.py --anchor-id`. Mismatch is a hard error.

## 4. Run directory discipline

Never put multiple physical conditions into one ambiguous log.

Suggested run ID:

```text
P0_202608xx_A_TAG01_D1.0m_LOS_A0_R0_R01
```

The immutable manifest remains authoritative; human-readable names are convenience only.

For every run preserve:

```text
manifest.json
manifest.json.sha256
raw_serial.log
ranges.jsonl
capture_summary.json
installation photo reference
run notes
```

Do not use terminal screenshots as the primary evidence.

## 5. Gate-0 — vendor Bbo smoke

Use one Bbo Initiator + one Bbo Reflector with the vendor-supplied signed RAS images.

Success means:

- both boards boot without unexplained resets;
- BLE/CS connects repeatedly;
- `Ranging data ready` appears;
- IFFT / phase-slope / RTT lines appear;
- `tools/capture_cs.py` parses them automatically;
- raw serial and manifests are retained.

Expected limitation:

```text
source_identity_complete = false
```

because vendor text lacks complete device-source timing/identity. That is acceptable for smoke only.

## 6. Source-built baseline

After vendor smoke:

- pin exact NCS/toolchain revision;
- compile the official RAS source path;
- apply only the documented Bbo board/overlay changes;
- integrate PuttTrack telemetry;
- flash Initiator and Reflector;
- verify JSON source identity;
- power-cycle/reboot and prove boot-domain changes are visible.

Do not tune CS procedure timing before the first source baseline is recorded.

## 7. First stability runs

### 1 m

- stable LOS;
- fixed mounts;
- minimum 30 minutes;
- record all estimators, not only best range;
- record gaps/resets/parse errors.

### 3 m

Repeat without changing firmware/profile.

Compare:

- sample count;
- procedure success;
- median/bias;
- P90/P95 absolute error;
- estimator disagreement;
- reset/boot-domain count;
- effective source update interval distribution.

## 8. Distance matrix

Truth distances:

```text
0.5 m
1 m
2 m
3 m
5 m
8 m
10 m
```

At each condition preserve at least:

- IFFT;
- phase-slope;
- RTT;
- RSSI when available;
- antenna path;
- source sequence/time;
- truth distance;
- orientation;
- condition tags.

Do not average in the logger.

## 9. Orientation / obstruction matrix

Minimum orientation baseline:

```text
Anchor:    0 / 90 / 180 / 270 deg
Reflector: 0 / 90 / 180 / 270 deg
```

Then representative adverse cases:

- Tag near ground;
- person standing between devices;
- person beside line of sight;
- wall/corner proximity;
- representative metal obstacle;
- future enclosure variants.

The matrix can be reduced after early data shows which axes matter, but do not skip orientation entirely.

## 10. Camera/survey truth choice

- single-link distance: measured physical separation;
- static XY: surveyed grid;
- dynamic rolling: low/oblique calibrated camera when practical;
- no requirement for a tall overhead mast.

See `docs/research/CAMERA_GROUND_TRUTH.md`.

## 11. Pre-run checklist

- [ ] Correct physical board/label selected.
- [ ] Correct firmware hash recorded.
- [ ] Correct NCS/toolchain/profile recorded.
- [ ] Correct COM/TTY selected.
- [ ] `source_device_id` matches physical Anchor when using source telemetry.
- [ ] Run-specific config saved.
- [ ] Truth geometry measured.
- [ ] Orientation recorded.
- [ ] Environment/obstruction recorded.
- [ ] Camera calibration ID recorded if used.
- [ ] `python tools/verify.py` is green on capture machine.

## 12. Post-run checklist

- [ ] `capture_summary.json` exists.
- [ ] Captured record count > 0.
- [ ] Parse error count reviewed.
- [ ] Source identity complete for source-built data.
- [ ] Manifest SHA-256 verifies.
- [ ] Raw serial preserved.
- [ ] Installation photo/notes linked.
- [ ] No unexplained board reset ignored.
- [ ] Data copied to controlled project storage before changing the rig.

## 13. Phase-0 exit

Do not advance to 3/4/5-Anchor localisation until:

- Bbo -> Nordic Tag interoperability is repeatable;
- source-built firmware identity is pinned;
- 1 m and 3 m stability is understood;
- the declared single-link matrix is captured;
- range quality/tails are sufficient to define calibration and rejection rules.
