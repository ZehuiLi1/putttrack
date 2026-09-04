# PuttTrack

PuttTrack is a research and product-development repository for a smart mini-golf ball and an 18-hole, automatic-scoring venue platform.

## Current execution direction

Bluetooth Channel Sounding is deferred for the current MVP. The active path is
nRF54L15 Tag identity/health/generic motion over BLE, signed OTA, physical
tee/cup/feature sensors and the existing sensor-independent Gameplay Engine.
There is no near-term continuous-XY claim. See
[`docs/CURRENT_PLAN_NO_CS.md`](docs/CURRENT_PLAN_NO_CS.md) and
[`ADR-013`](docs/adr/ADR-013-defer-cs-for-ble-motion-mvp.md). The evidence-ranked
current dashboard is [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md).

The physical Tag currently runs confirmed repository firmware `0.1.17` from a
CR2032: signed BLE OTA, stable identity/health, ADXL367 + BMI270 telemetry,
explicit ODR/range metadata, clipping counters and an atomic
1024-sample/20.48-second frozen history are validated. Its automatic power
policy stops BMI270 and the motion stream after 30 seconds at rest, retains
ADXL367 in hardware wake-up mode with INT1 connected to nRF54L15 P0.03, stops
MCU polling, suspends the BMI270 SPI controller, slows BLE advertising, and
restores the full 50 Hz path after physical motion. Repeated interrupt
wake/re-sleep cycles, powered NFC reads, a true System OFF NFC cold wake,
return to idle and a post-confirm boot are validated with zero reported sensor,
power-management, NFC or advertising errors. VDD/CR2032 voltage observation is
also live; its percentage is explicitly an OCV estimate, not a battery-life
claim.
See [`docs/hardware/NRF54L15_TAG_MOTION_BASELINE.md`](docs/hardware/NRF54L15_TAG_MOTION_BASELINE.md)
and [`docs/hardware/NRF54L15_TAG_LOW_POWER.md`](docs/hardware/NRF54L15_TAG_LOW_POWER.md).
The confirmed image also adds a per-device advertising name, while the capture
tools lock the full encrypted device ID and boot/session continuity so a future
second Tag cannot be silently mixed into a dataset. See
[`docs/hardware/TAG_MULTI_DEVICE_IDENTITY.md`](docs/hardware/TAG_MULTI_DEVICE_IDENTITY.md).
PCA20072 design review and the assembled-ball test confirm the NFC path on
P1.02/NFC1 and P1.03/NFC2. A 26 mm, 1.0 uH loop with provisional 220 pF values
at C17/C19 passed strict PN532 URI reads and the bounded 10-second BLE service
window and NFC System OFF cold wake; final tuning, range and current remain
open. See
[`docs/hardware/NRF54L15_TAG_NFC.md`](docs/hardware/NRF54L15_TAG_NFC.md).
The exact cold-wake and battery evidence is in
[`docs/hardware/NRF54L15_TAG_SYSTEM_OFF_BATTERY.md`](docs/hardware/NRF54L15_TAG_SYSTEM_OFF_BATTERY.md).
The host-side service planner strictly cross-checks reader URI/identity/version
and rejects unsafe update eligibility; it does not itself authorize or perform
OTA. Nordic's official STEP assembly was
also reduced to a reproducible populated-board envelope and conservative
research-core keep-in; see
[`docs/hardware/NRF54L15_TAG_MECHANICAL_ENVELOPE.md`](docs/hardware/NRF54L15_TAG_MECHANICAL_ENVELOPE.md)
and
[`docs/hardware/RESEARCH_BALL_ROLLER_PROTOCOL.md`](docs/hardware/RESEARCH_BALL_ROLLER_PROTOCOL.md).
Physical stationary and continuous hand-motion windows now separate as
`STATIONARY_CANDIDATE` and `ACTIVE_MOTION_CANDIDATE`. The assembled Ball also
has a seven-episode exploratory/manual-floor dataset covering before/after
stationary, two free rolls, pickup/carry and restrained repeated taps. It shows
preliminary roll/pickup separation and confirms that ADXL367 clips before the
BMI270, but unmeasured speed and action timing prohibit final thresholds. Timed
ARMED capture now records a device-side GO marker and excludes setup/readback
delay from future labelled windows. A loopback-only field UI now selects the
action/profile, controls one-button captures, prevents overwrite/concurrency
and restores low power automatically; start it with
`python3 tools/run_field_capture_ui.py`. It also plots measured battery-voltage
readbacks and per-episode IMU peak/RMS trends, while exposing sensor, firmware,
power-state, continuity, sequence-gap and clipping status. See
[`experiments/research_ball_r1_manual_floor`](experiments/research_ball_r1_manual_floor/README.md)
and [`TAG_MOTION_EPISODE_RUNBOOK.md`](docs/hardware/TAG_MOTION_EPISODE_RUNBOOK.md).
The resulting canonical motion record can enter
the one-hole runtime as an observed/pending/rejected candidate, but cannot
infer pickup/impact semantics or directly mutate score.
Reviewed field batches now cover no-lift handling, rolling pickup,
pickup/carry, pickup/drop, gentle putt, rail collision and course-step controls.
They support a specific research hypothesis: short vertical impulse plus
low/moderate, multi-axis gyro activity separates current stationary-start
pickup examples from sustained single-axis putt/roll examples in-sample.
Gravity reversal and acceleration peak alone do not. Labels are still
operator-confirmed rather than independent video truth, so no product accuracy
is claimed. The measured status is recorded in
[`PICKUP_DETECTION_STATUS_20260904.md`](docs/research/PICKUP_DETECTION_STATUS_20260904.md),
and the dependency-ordered next work is locked in
[`NEXT_IMU_ENGINEERING_PLAN_20260904.md`](docs/research/NEXT_IMU_ENGINEERING_PLAN_20260904.md).
A repeatable export tool, `python3 tools/package_imu_dataset.py`, packages all
unique raw IMU captures with a data dictionary, quality manifest, SHA-256
checksums and model-analysis brief. The canonical first-campaign archive is now
versioned at
[`datasets/putttrack_imu_dataset_20260904.zip`](datasets/putttrack_imu_dataset_20260904.zip),
with its browsable row-level manifest under
[`docs/research/imu_analysis_20260904`](docs/research/imu_analysis_20260904/README.md).
Duplicate working copies, incomplete captures and later live `runs/` remain
local until they are reviewed into an experiment batch.
The hardware-neutral tee/cup input path is also implemented: assigned-Ball tee
presence can reach READY, while cup completion requires optical entry plus
PN532 confirmation of the exact active Ball within 3 seconds and an
already-confirmed stroke. One ESP32 may host both independently identified
sensors. It is covered by
ordering, health, idempotency, replay and HTTP end-to-end tests, but no physical
tee/cup mechanism has yet passed. See
[`docs/hardware/PHYSICAL_TEE_CUP_INGRESS.md`](docs/hardware/PHYSICAL_TEE_CUP_INGRESS.md).
A new fail-closed activation authority treats NFC as proximity only, enforces
one Ball per hole and one hole per Ball, issues monotonic hole epochs, keeps
normal stationary play in ADXL367-backed `ACTIVE_IDLE`, and returns a Ball to
System OFF only on explicit end or bounded fail-safe conditions. The accepted
decision and simple fixed-reader configuration are in
[`ADR-015`](docs/adr/ADR-015-nfc-gated-hole-activation.md) and
[`configs/venue/activation.example.json`](configs/venue/activation.example.json).
A primary-source Trackaball comparison has also produced a fail-closed
multi-receiver BLE observation layer and a research-only state/RF policy. It
does not turn RSSI into position or score authority and does not change the
physical Tag; see
[`docs/research/PUTTSHACK_TRACKABALL_TECH_REVIEW.md`](docs/research/PUTTSHACK_TRACKABALL_TECH_REVIEW.md).
The authority decision is locked in
[`ADR-014`](docs/adr/ADR-014-multi-receiver-ble-is-non-authoritative.md).

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

- typed `RangeObservation`, `MotionObservation`, `PhysicalSensorObservation`,
  `RadioReceptionObservation`, `TrackUpdate`, `EvidenceEvent` and persistable
  `GameplayEvent` records;
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

The local vertical slice under `src/putttrack/venue/` exercises the locked
customer flow while physical mechanisms are still being built:

- guest-first check-in and booking-code lookup;
- optional account linking;
- server-side smart-ball allocation with human-readable Ball labels;
- flexible player order;
- amber `DETECTED / CHECKING` presentation followed by authoritative green `READY`;
- simulated stroke/feature/pickup/cup semantic events routed through the existing Gameplay Engine;
- canonical physical tee/cup observation ingress with fail-closed authority,
  audit and two-stage cup confirmation;
- SSE hole-screen feedback and local leaderboard;
- append-only local Gameplay audit and audited operator correction endpoint.

Run the deterministic no-CS one-hole fault-injection soak with:

```bash
PYTHONPATH=src python tools/soak_no_cs_hole.py --rounds 1000 --players 4
```

The checked baseline completed all 1,000 rounds with 20,000 injected faults and
zero invariant failures. This is a software gate, not a physical sensor
reliability claim; see
[`docs/verification/NO_CS_ONE_HOLE_SOAK.md`](docs/verification/NO_CS_ONE_HOLE_SOAK.md).

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

1. Collect genuine putter impact/free-roll/settle, handling, collision and cup
   repetitions using timed ARMED captures and independent marker/video truth;
   the 86-capture programmable-roller phase is complete.
2. Fit and hold out a deterministic generic-motion FSM without giving the Ball
   direct score authority.
3. Build the selected Tee PN532 and Cup optical-entry + PN532 identity rigs and
   drive the implemented one-hole evidence path with physical inputs.
4. Provision production Ball/controller credentials, persist active leases and
   connect authenticated activate/end commands to the Tag firmware.
5. Measure whole-Tag current, NFC range/tuning and multi-receiver BLE behavior.
6. Select pilot Gateway hardware only after BLE, physical I/O and buffering
   requirements are measured.
7. Re-open CS/ranging only on the explicit triggers in ADR-013.
8. Complete claims-based FTO/regulatory checkpoints before commercial freeze.

## IP / legal note

This repository records engineering research, public prior art and design constraints; it is not legal advice or a freedom-to-operate opinion. Production remains spatial-first and hole-independent. Patent-sensitive hole-specific movement-signature authority, charging/activation combinations and target-jurisdiction launch require an up-to-date claims-based review.
