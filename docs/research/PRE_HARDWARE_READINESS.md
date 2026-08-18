# Pre-Hardware Readiness

## Goal

Bring PuttTrack to the point where the next meaningful blocker is **physical nRF54L15 hardware**, not missing software contracts, camera assumptions, test-fixture ambiguity or unrepeatable experiment setup.

This document deliberately avoids implementing localisation/ML results before measurements exist.

## Current readiness state

The pre-hardware gate has now been completed and merged through PR #17.

Verified source baseline:

- nRF Connect SDK tag: `v3.0.2`;
- sdk-nrf commit: `89ba1294ac9b624e28271a5c71e99193ed4d92a4`;
- target: `nrf54l15dk/nrf54l15/cpuapp`;
- official RAS Initiator source build: PASS;
- official RAS Reflector source build: PASS;
- PuttTrack telemetry smoke application: PASS;
- canonical software verifier: PASS;
- pre-hardware readiness verifier: PASS.

The next blocker is the **actual Bbo board revision/overlay/flash/RF path and Nordic Tag interoperability**, not generic NCS source compatibility.

## Ready-now workstreams

### A. Source-built Channel Sounding build path

Pinned authority for the first reproducible source baseline:

- nRF Connect SDK tag: `v3.0.2`;
- sdk-nrf commit: `89ba1294ac9b624e28271a5c71e99193ed4d92a4`;
- official RAS Initiator sample: `samples/bluetooth/channel_sounding_ras_initiator`;
- official RAS Reflector sample: `samples/bluetooth/channel_sounding_ras_reflector`;
- official supported target includes `nrf54l15dk/nrf54l15/cpuapp`;
- PuttTrack source telemetry helper: `firmware/phase0_cs/putttrack_cs_telemetry.*`.

The vendor Bbo images remain Gate-0 smoke evidence. The pinned Nordic source build is the first research baseline.

The repository includes a reproducible build script and CI workflow. The official Nordic DK source path has compiled successfully. The Bbo-specific overlay/package remains vendor-controlled and must be confirmed against the physical board/package before claiming a Bbo source build.

**Do not call official-DK compile success a Bbo hardware PASS.**

### B. Ground truth without a tall overhead camera

Ground-truth strategy is deliberately camera-height-independent:

- Phase 0/1 single-link truth: surveyed/measured physical distance, camera unnecessary;
- Phase 2 static XY: independently surveyed grid/control points, camera unnecessary;
- Phase 3 dynamic: low/oblique planar camera via homography;
- if one low view is occluded: two overlapping low/oblique views;
- non-planar ramps: separate plane / multi-view later, or exclude from the first baseline.

See `docs/research/CAMERA_GROUND_TRUTH.md`.

### C. Physical rig / experiment discipline

Before boards arrive, prepare:

- physical labels A/B/C/D/E + spare;
- non-conductive mounting fixtures;
- measured test line / grid;
- laser/tape measurement method;
- orientation reference marks;
- run-specific Anchor coordinate files;
- USB/serial naming sheet;
- controlled vendor-archive storage;
- camera calibration markers if dynamic video will be used;
- visible sync LED/marker if dynamic camera timing will be compared to Edge time.

See `experiments/phase0_cs/PHYSICAL_RIG_RUNBOOK.md`.

### D. Player-experience dry run

The local one-hole software vertical slice can be tested with ordinary balls and simulated EvidenceEvents before RF hardware arrives.

Run four first-time players through:

```text
check-in -> assigned ball -> DETECTED -> READY -> play -> feedback -> cup -> next player
```

Observe confusion/recovery rather than coaching them. Record where staff explanation is required.

This is a **comprehension/recovery dry run only**. It does not replace physical tee/cup/RF/HMI validation.

See `experiments/ux_dry_run/README.md`.

## What remains intentionally blocked on hardware

Do not pre-complete these with simulation-only evidence:

- Bbo vendor smoke;
- Bbo-specific source build/flash validation;
- Bbo <-> Nordic Tag interoperability;
- IFFT/phase/RTT accuracy distributions;
- real update rate;
- 1 m/3 m stability;
- orientation/NLOS tails;
- 3/4/5-Anchor production decision;
- dynamic EKF accuracy;
- multi-ball RF scheduling capacity;
- Ball energy/update;
- final antenna count;
- final Smart Ball PCB.

Likewise, do not invent Gateway scheduler timings, RF airtime models or EKF covariance values before the corresponding real measurements exist.

## Hardware-arrival Day 0 checklist

1. Photograph and label every board/revision before programming.
2. Hash/preserve the actual vendor archive/package used and confirm the controlled copy.
3. Run `python tools/verify_pre_hardware.py` on the capture machine and retain the output.
4. Install `pip install '.[hardware]'` when live serial capture is required.
5. Record COM/TTY mapping and USB hub/power arrangement.
6. Create a new run-specific Anchor config; never overwrite old configs.
7. Fix the physical coordinate frame and RF reference points before multi-Anchor data collection.
8. Vendor Initiator <-> vendor Reflector smoke first.
9. Preserve full raw serial, manifests, photos and notes; screenshots are secondary evidence only.
10. Confirm actual Bbo revision/overlay assumptions, then build/flash the pinned source baseline.
11. Confirm `source_device_id`, `source_boot_id`, sequence and device monotonic time.
12. Run 1 m and 3 m fixed LOS stability without changing the procedure profile.
13. Only then begin the declared distance/orientation/obstruction matrix.
14. Move to Issue #7 only after the Phase-0 exit gate is satisfied.

## Stop condition — SATISFIED

The pre-hardware stop condition is now satisfied because:

- the standard software verifier is green;
- the camera/survey GT tooling is green;
- the official Nordic RAS source build smoke is green;
- the PuttTrack telemetry source smoke build is green;
- experiment/runbooks are complete;
- UX dry-run protocol is ready;
- no open PR remains from the pre-hardware convergence pass once the final documentation sync is merged.

Therefore PuttTrack should **stop adding speculative localisation/product code and wait for real hardware evidence in Issue #1**.
