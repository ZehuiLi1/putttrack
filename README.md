# PuttTrack

PuttTrack is a research and product-development repository for a smart mini-golf ball and an 18-hole, automatic-scoring venue platform.

## Current execution direction

Bluetooth Channel Sounding is deferred for the current MVP. The active path is
nRF54L15 Tag identity/health/generic motion over BLE, signed OTA, physical
tee/cup/feature sensors and the existing sensor-independent Gameplay Engine.
There is no near-term continuous-XY claim. See
[`docs/CURRENT_PLAN_NO_CS.md`](docs/CURRENT_PLAN_NO_CS.md) and
[`ADR-013`](docs/adr/ADR-013-defer-cs-for-ble-motion-mvp.md).

The physical Tag currently runs confirmed repository firmware `0.1.13` from a
CR2032: signed BLE OTA, stable identity/health, ADXL367 + BMI270 telemetry,
explicit ODR/range metadata, clipping counters and an atomic
1024-sample/20.48-second frozen history are validated. Its automatic power
policy stops BMI270 and the motion stream after 30 seconds at rest, retains
ADXL367 in hardware wake-up mode with INT1 connected to nRF54L15 P0.03, stops
MCU polling, suspends the BMI270 SPI controller, slows BLE advertising, and
restores the full 50 Hz path after physical motion. Repeated interrupt
wake/re-sleep cycles and a post-confirm reboot are validated with zero reported
sensor, power-management or advertising errors.
See [`docs/hardware/NRF54L15_TAG_MOTION_BASELINE.md`](docs/hardware/NRF54L15_TAG_MOTION_BASELINE.md)
and [`docs/hardware/NRF54L15_TAG_LOW_POWER.md`](docs/hardware/NRF54L15_TAG_LOW_POWER.md).
PCA20072 design review also confirms an unpopulated optional NFC path on
P1.02/NFC1 and P1.03/NFC2 with C17/C19 tuning footprints. It remains an
unvalidated, time-boxed service/provisioning experiment; see
[`docs/hardware/NRF54L15_TAG_NFC.md`](docs/hardware/NRF54L15_TAG_NFC.md).
Physical stationary and continuous hand-motion windows now separate as
`STATIONARY_CANDIDATE` and `ACTIVE_MOTION_CANDIDATE`. Two natural-pickup and two
desk-handling repetitions also show that stronger handling overlaps pickup at
generic activity intensity. The resulting canonical motion record can enter
the one-hole runtime as an observed/pending/rejected candidate, but cannot
infer pickup/impact semantics or directly mutate score.

## Product logic

The locked player experience is defined in [`docs/PRODUCT_LOGIC_LOCK.md`](docs/PRODUCT_LOGIC_LOCK.md):

```text
Guest / booking
 -> quick check-in
 -> one assigned smart ball per player
 -> present any unfinished player's ball at the tee
 -> DETECTED / CHECKING
 -> READY
 -> normal zero-touch physical play
 -> automatic stroke / feature / cup evidence
 -> deterministic score and non-blocking feedback
 -> next player / next hole
 -> local leaderboard and final digital result
```

The existing deterministic/idempotent Gameplay Engine lives under `src/putttrack/gameplay/` and deliberately consumes semantic evidence rather than depending on CS, IMU, UWB, camera or a specific sensor implementation.

## Architecture Constitution

The end-to-end architecture is defined in:

- [`docs/ARCHITECTURE_CONSTITUTION.md`](docs/ARCHITECTURE_CONSTITUTION.md) — primary technical source of truth;
- [`docs/architecture/`](docs/architecture/) — hardware, RF, Gateway, Edge, data, security, failure, deployment and verification detail;
- [`docs/adr/`](docs/adr/) — accepted decisions with risks, gates and revisit triggers.

The former [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) is retained as the pre-convergence hypothesis and research history.

## Longer-term architecture hypothesis (CS currently deferred)

```text
                            CLOUD (non-authoritative)
 bookings / optional accounts / loyalty / analytics / release control
                                  ^
                                  | queued sync
                                  |
Managed Ethernet/PoE LAN ---- Venue Edge (authoritative local game)
        |                         registry / assignments / localisation
        |                         evidence / Gameplay Engine / audit / HMI
        |
   Zone Gateways
   ~2-3 holes each
        |
24 V + protected RS-485
        |
Anchors + Tee/Cup/Feature sensors
        |
Bluetooth Channel Sounding
        |
Smart Ball
nRF54L15 + generic motion sensing
CS Reflector + BLE control/health
```

### Core decisions

- Nordic nRF54L15 Tag remains the moving research reference.
- Five identical Bbo Anchors plus a spare remain the research rig.
- Production starts from four perimeter/geometry Anchors; the fifth node is optional and should be RF-optimal/elevated when evidence justifies it.
- Ball is CS Reflector; powered Anchors are Initiators.
- Standard encrypted connected CS is the conditional Production V1 path; only one CS procedure per ball is active at a time.
- Dynamic tracking uses an asynchronous range-domain EKF; robust multilateration remains for initialization, static benchmarking and reacquisition.
- Generic motion informs scheduling/evidence/process noise; the ball does not own score or hole-specific rules.
- Zone Gateways coordinate approximately 2–3 holes, with wired 24 V/protected RS-485 to field nodes and Ethernet/PoE to the venue LAN.
- Venue Edge is a local authoritative modular monolith and continues through WAN loss.
- Camera is research/calibration/replay ground truth, not production positioning authority.
- Independent tee and physical cup evidence remain in Production V1.
- ML is limited initially to range bias/variance/outlier modelling, not opaque score or authoritative XY.
- UWB is an evidence-triggered benchmark/fallback if CS fails accuracy, NLOS, scalability or energy gates.
- Hole-specific movement-signature valid-stroke logic remains research-only pending a later claims-based FTO review.

## Evidence Foundation

Issue #6 turns the architecture contracts into executable software:

- typed `RangeObservation`, `MotionObservation`, `PhysicalSensorObservation`, `TrackUpdate`, `EvidenceEvent` and persistable `GameplayEvent` records;
- compatible schema-version handling and fail-closed unknown majors;
- append-only, crash-aware canonical JSONL capture;
- immutable SHA-256-verified run manifests;
- source boot/sequence/monotonic-time ordering diagnostics;
- deterministic evidence replay into the unchanged Gameplay Engine;
- derived Parquet research export through the optional `research` dependency;
- Bbo vendor-log and structured-JSON Channel Sounding capture tooling.

Run the complete software verifier:

```bash
python tools/verify.py
```

Replay the checked-in run twice:

```bash
PYTHONPATH=src python tools/replay_run.py experiments/evidence_replay_example
```

Prepare a fixture Phase-0 capture:

```bash
make capture-fixture
```

See [`docs/EVIDENCE_FOUNDATION.md`](docs/EVIDENCE_FOUNDATION.md) and [`experiments/phase0_cs/README.md`](experiments/phase0_cs/README.md). This tooling does not claim that real Bbo/Nordic hardware has passed Issue #1.

## Pre-hardware readiness

The repository is designed so a tall overhead camera is **not** a prerequisite for the RF research:

- Phase 0/1 single-link truth uses measured physical separation;
- Phase 2 static 3/4/5-Anchor truth can use a surveyed floor/grid with no camera;
- Phase 3 dynamic truth can use a stable low/oblique camera mapped to venue XY through surveyed ground-control points;
- a second low/oblique view can be added where one camera is occluded;
- ramps/non-planar regions are excluded, segmented or handled with a later multi-view method rather than being incorrectly projected onto a flat plane.

Camera/survey tooling:

```bash
PYTHONPATH=src python tools/calibrate_ground_plane.py camera_points.json calibration.json
PYTHONPATH=src python tools/fit_camera_sync.py sync_pairs.csv camera_time_map.json
PYTHONPATH=src python tools/project_camera_gt.py annotations.csv calibration.json ground_truth.csv --time-map camera_time_map.json
```

Run the full software + pre-hardware verifier:

```bash
make verify-prehardware
```

The first source baseline is pinned to Nordic nRF Connect SDK `v3.0.2` / sdk-nrf commit `89ba1294ac9b624e28271a5c71e99193ed4d92a4`. The official RAS Initiator/Reflector and the PuttTrack telemetry helper can be source-built with:

```bash
make ncs-phase0-build
```

An official-DK compile is only a source/toolchain compatibility check. It does not prove the Bbo overlay, flashing, RF path or physical performance.

See:

- [`docs/research/PRE_HARDWARE_READINESS.md`](docs/research/PRE_HARDWARE_READINESS.md)
- [`docs/research/CAMERA_GROUND_TRUTH.md`](docs/research/CAMERA_GROUND_TRUTH.md)
- [`docs/hardware/NCS_PHASE0_BUILD.md`](docs/hardware/NCS_PHASE0_BUILD.md)
- [`experiments/phase0_cs/PHYSICAL_RIG_RUNBOOK.md`](experiments/phase0_cs/PHYSICAL_RIG_RUNBOOK.md)
- [`experiments/ux_dry_run/README.md`](experiments/ux_dry_run/README.md)

## One-hole player-experience vertical slice

The local vertical slice under `src/putttrack/venue/` exercises the locked customer flow before physical sensing is available:

- guest-first check-in and booking-code lookup;
- optional account linking;
- server-side smart-ball allocation with human-readable Ball labels;
- flexible player order;
- amber `DETECTED / CHECKING` presentation followed by authoritative green `READY`;
- simulated stroke/feature/pickup/cup semantic events routed through the existing Gameplay Engine;
- SSE hole-screen feedback and local leaderboard;
- append-only local Gameplay audit and audited operator correction endpoint.

Run it with:

```bash
PYTHONPATH=src python tools/run_hole_demo.py
```

Then open `http://127.0.0.1:8080/checkin`. The simulation controls exist only to exercise the UI while Issue #1 remains a real-hardware gate. See [`docs/GAMEPLAY_VERTICAL_SLICE_V1.md`](docs/GAMEPLAY_VERTICAL_SLICE_V1.md).

## Deferred CS Research Rig

This rig is retained for a bounded future experiment under ADR-013. It is not a
dependency of the active BLE + motion MVP.

### Moving target

- 1–2 Nordic `nRF54L15 Tag` boards;
- one golden reference where possible;
- a second for enclosure/rolling/impact/orientation experiments.

### Anchors

- 5 identical Bbo nRF54L15 boards as A/B/C/D + experimental reference E;
- 1 spare/development board;
- experiments compare 3, four perimeter, ground-centre, elevated reference, best-4-of-5 and weighted/robust five.

The research count does not freeze production Anchor quantity.

## Validation before production hardware

The spatial/Anchor gates below apply only if the CS track is reactivated. Motion,
identity isolation, gameplay, OTA and endurance gates remain active.

See [`docs/architecture/VERIFICATION_MATRIX.md`](docs/architecture/VERIFICATION_MATRIX.md). Headline candidate gates include:

- single-link LOS P90 <=0.5 m;
- static XY P90 <=0.5 m and P95 <=0.8 m;
- dynamic XY P90 <=0.6 m, P95 <=1.0 m and reacquisition <=1 s;
- confirmed event to HMI <=500 ms;
- stroke recall >=99% and false-stroke rate <=0.1% of labelled non-stroke episodes;
- zero cross-ball/duplicate score mutation;
- one-hole 1,000-round soak;
- 20/40/80-ball scheduling simulation with bounded queues and measured headroom;
- custom-ball conservative service-life projection >=2 years, stretch >=5 years.

Do not start the final Ball PCB until measured IMU, BLE, power, mechanics, OTA
and service requirements exist. If CS is reactivated, its RF, antenna and
scheduling requirements must also be measured before that design freeze.

## Gameplay demo and tests

```bash
PYTHONPATH=src python simulator/demo_gameplay.py
PYTHONPATH=src python -m unittest discover -s tests -v
```

## Documentation map

### Locked product/gameplay

- [`docs/PRODUCT_LOGIC_LOCK.md`](docs/PRODUCT_LOGIC_LOCK.md)
- [`docs/GAMEPLAY_EXPERIENCE.md`](docs/GAMEPLAY_EXPERIENCE.md)
- [`docs/GAMEPLAY_IMPLEMENTATION.md`](docs/GAMEPLAY_IMPLEMENTATION.md)
- [`docs/GAMEPLAY_VERTICAL_SLICE_V1.md`](docs/GAMEPLAY_VERTICAL_SLICE_V1.md)

### Architecture

- [`docs/ARCHITECTURE_CONSTITUTION.md`](docs/ARCHITECTURE_CONSTITUTION.md)
- [`docs/architecture/SYSTEM_CONTEXT.md`](docs/architecture/SYSTEM_CONTEXT.md)
- [`docs/architecture/HARDWARE_TOPOLOGY.md`](docs/architecture/HARDWARE_TOPOLOGY.md)
- [`docs/architecture/SMART_BALL.md`](docs/architecture/SMART_BALL.md)
- [`docs/architecture/ANCHOR_RF_CELL.md`](docs/architecture/ANCHOR_RF_CELL.md)
- [`docs/architecture/GATEWAY.md`](docs/architecture/GATEWAY.md)
- [`docs/architecture/VENUE_EDGE.md`](docs/architecture/VENUE_EDGE.md)
- [`docs/architecture/CLOUD_BOUNDARY.md`](docs/architecture/CLOUD_BOUNDARY.md)
- [`docs/architecture/HMI.md`](docs/architecture/HMI.md)
- [`docs/architecture/DATA_MODEL.md`](docs/architecture/DATA_MODEL.md)
- [`docs/architecture/EVENT_CONTRACT.md`](docs/architecture/EVENT_CONTRACT.md)
- [`docs/architecture/TIME_SYNC.md`](docs/architecture/TIME_SYNC.md)
- [`docs/architecture/SECURITY.md`](docs/architecture/SECURITY.md)
- [`docs/architecture/FAILURE_MODES.md`](docs/architecture/FAILURE_MODES.md)
- [`docs/architecture/MULTIBALL_SCALABILITY.md`](docs/architecture/MULTIBALL_SCALABILITY.md)
- [`docs/architecture/DEPLOYMENT.md`](docs/architecture/DEPLOYMENT.md)
- [`docs/architecture/VERIFICATION_MATRIX.md`](docs/architecture/VERIFICATION_MATRIX.md)
- [`docs/architecture/IMPLEMENTATION_ROADMAP.md`](docs/architecture/IMPLEMENTATION_ROADMAP.md)
- [`docs/architecture/REFERENCES.md`](docs/architecture/REFERENCES.md)
- [`docs/adr/README.md`](docs/adr/README.md)

### Evidence / research / IP

- [`docs/EVIDENCE_FOUNDATION.md`](docs/EVIDENCE_FOUNDATION.md)
- [`docs/verification/EVIDENCE_FOUNDATION_V1.md`](docs/verification/EVIDENCE_FOUNDATION_V1.md)
- [`docs/research/PRE_HARDWARE_READINESS.md`](docs/research/PRE_HARDWARE_READINESS.md)
- [`docs/research/CAMERA_GROUND_TRUTH.md`](docs/research/CAMERA_GROUND_TRUTH.md)
- [`docs/EXPERIMENT_PLAN.md`](docs/EXPERIMENT_PLAN.md)
- [`docs/PATENT_RESEARCH.md`](docs/PATENT_RESEARCH.md)

## Immediate dependency order

1. Preserve the verified Tag backup, DAPLink recovery and signed OTA baseline.
2. Replace the generic SMP sample with a repository-owned Tag identity/health application.
3. Bring up ADXL367 and BMI270 and capture replayable raw BLE telemetry.
4. Collect labelled bare-Tag and controlled-ball-core motion episodes.
5. Implement deterministic generic motion candidates without putting score logic in the Ball.
6. Replace simulated one-hole events with physical tee/cup/feature evidence plus Ball context.
7. Select pilot Gateway hardware only after the BLE contract and physical I/O count are measured.
8. Re-open CS/ranging only on the explicit triggers in ADR-013.
9. Complete a claims-based FTO/regulatory checkpoint before commercial freeze.

## IP / legal note

This repository records engineering research, public prior art and design constraints; it is not legal advice or a freedom-to-operate opinion. Production remains spatial-first and hole-independent. Patent-sensitive hole-specific movement-signature authority, charging/activation combinations and target-jurisdiction launch require an up-to-date claims-based review.
