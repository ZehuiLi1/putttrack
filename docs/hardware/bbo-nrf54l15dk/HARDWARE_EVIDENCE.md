# Bbo nRF54L15DK Hardware Evidence

## Scope and evidence discipline

This note is derived from the vendor package identified in [`SOURCE_MANIFEST.md`](SOURCE_MANIFEST.md). Statements are classified as:

- **FACT** — directly supported by the inspected vendor files/binary strings.
- **INFERENCE** — PuttTrack engineering interpretation that still needs measurement.
- **UNKNOWN** — not established by the supplied material.

No vendor accuracy statement is treated as PuttTrack performance evidence.

## FACT — core board resources

The Bbo development guide describes the core board with:

- nRF54L15, 1.5 MB NVM and 256 KB RAM;
- reset button, user button and status/power LEDs;
- onboard CH340 serial interface and USB Type-C power/data path;
- GPIO and SWD interfaces broken out;
- vendor serial upgrade support.

The separate Bbo Kit expansion-board section lists the LSM6DS3TR-C six-axis IMU. Therefore the inspected material does **not** support the statement that every bare Bbo core board includes that IMU.

The serial-upgrade guide states that the board ships with a boot program and can use the CH340/Type-C path with `BboTool`. The development guide warns that J-Link/SWD flashing can erase the default boot program and identifies `release_boot_01.hex` as the recovery image.

## FACT — RF path on the inspected schematic revision

The inspected `SCH_nRF54L15DK.pdf` shows one nRF54L15 `ANT` RF feed through a matching network to the board antenna connection. No second physical antenna feed/switch is evidenced on that core-board schematic revision.

For PuttTrack Phase 0 this board revision is therefore treated as a **single physical RF-feed baseline**. The Channel Sounding software still reports an antenna-path index, so every captured record must retain that field rather than hard-code it away.

A later board revision must be re-inspected rather than assumed identical.

## FACT — supplied Channel Sounding path

The vendor guide points to nRF Connect SDK examples named:

- `channel_sounding_ras_initiator`
- `channel_sounding_ras_reflector`

and supplies signed binaries with matching names.

The guide describes Initiator as the side that normally runs the ranging algorithm and Reflector as the lower-complexity responding/tag side. This matches the PuttTrack architectural direction of powered infrastructure as Initiator and the moving Ball endpoint as Reflector.

The guide states that its log exposes three estimator forms:

- `ifft` — vendor describes it as usually the most accurate but subject to outliers;
- `phase_slope` — vendor describes it as more stable/fewer outliers but with systematic positive bias in its example;
- `rtt` — vendor describes it as lower precision and primarily useful for cross-checking/outlier detection.

These are **vendor descriptions**. PuttTrack must measure estimator bias/tails independently.

## FACT — supplied CS binary provenance

Inspection of printable strings in the supplied Initiator binary confirms:

- it identifies the Nordic `nrf/applications/channel_sounding_ras_initiator/src/main.c` path;
- it prints `Ranging data ready`;
- it formats `Distance estimates on antenna path %u: ifft: %f, phase_slope: %f, rtt: %f`;
- it contains `Sleeping for a few seconds...`;
- it identifies nRF Connect SDK `v3.0.2-89ba1294ac9b` and Zephyr `v4.0.99-f791c49f492c`.

The Reflector binary identifies `Starting Channel Sounding Reflector Sample`, `Nordic CS Reflector` and the same NCS/Zephyr banners.

The vendor package also includes ordinary demo trees for both NCS 3.0.2 and 3.3.0, while the supplied CS smoke-test binaries identify NCS 3.0.2.

## INFERENCE — PuttTrack suitability

The evidence is sufficient to keep Bbo as a useful Phase-0 device because it provides:

- a vendor-supported UART/boot path;
- a known nRF54L15 platform;
- signed Initiator and Reflector smoke-test images;
- log output containing estimator values needed for early range-baseline work;
- SWD access for later source-built firmware.

The supplied image should be treated as **bring-up evidence only**, not as final tracking firmware. The explicit `Sleeping for a few seconds...` string is a strong reason to move to a source-built scheduler before dynamic tracking measurements.

Because the inspected core-board schematic shows one RF feed, Phase-1 data must deliberately sweep board/target orientation, near-ground conditions and obstruction. A fixed Anchor can later use installation/orientation control to reduce this risk; the moving Ball cannot.

## UNKNOWN — must be measured

The source package does not establish:

- PuttTrack LOS/NLOS P50/P90/P95 range error;
- outlier/no-fix distribution in a mini-golf environment;
- random-orientation and rolling-object robustness;
- performance close to wet ground, steel, decorative structures or people;
- maximum sustainable CS procedure/update rate;
- exact stock-sample procedure duration and airtime;
- 3/4/5-Anchor localisation performance;
- multi-ball scheduling capacity;
- energy per procedure;
- final-enclosure detuning;
- production reliability, security/update lifecycle or environmental qualification.

## Decision carried forward

**KEEP** Bbo as the Phase-0 baseline/debug Anchor platform.

**DO NOT PROMOTE** it to production Anchor solely from this vendor package.

**COMPARE** later fixed-Anchor antenna candidates and moving-target antenna diversity against the same ground-truth dataset before freezing the production RF architecture.
