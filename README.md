# PuttTrack

PuttTrack is a research and product-development repository for a smart mini-golf ball and an 18-hole, automatic-scoring venue platform.

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

## Converged direction

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

## Research Rig

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

Do not start the final Ball PCB until measured CS, IMU, dual-antenna, scheduling and power requirements exist.

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
- [`docs/EXPERIMENT_PLAN.md`](docs/EXPERIMENT_PLAN.md)
- [`docs/PATENT_RESEARCH.md`](docs/PATENT_RESEARCH.md)

## Immediate dependency order

1. Run and maintain the exact-tree software verifier and canonical replay foundation.
2. Bring up Bbo <-> Bbo and Bbo <-> Nordic Tag CS using exact NCS/toolchain manifests and `tools/capture_cs.py`.
3. Collect single-link and 3/4/5-Anchor camera-ground-truth datasets without changing the evidence schema.
4. Implement robust WLS plus asynchronous range-domain EKF.
5. Add generic motion dataset and evidence policies.
6. Replace simulated one-hole events with confirmed physical evidence while preserving the existing venue/UI boundary.
7. Build Zone Gateway/field-bus and multi-ball scheduler simulation.
8. Start custom Ball EVT only after power/RF/scheduling gates.
9. Complete a claims-based FTO/regulatory checkpoint before commercial freeze.

## IP / legal note

This repository records engineering research, public prior art and design constraints; it is not legal advice or a freedom-to-operate opinion. Production remains spatial-first and hole-independent. Patent-sensitive hole-specific movement-signature authority, charging/activation combinations and target-jurisdiction launch require an up-to-date claims-based review.
