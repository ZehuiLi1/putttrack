# Dependency-Ordered Implementation Roadmap

## Principle

Do not design the final ball PCB or venue network before the sensing/scheduling gates establish the real requirements. Build thin vertical slices and preserve raw evidence.

## Workstream 0 — Baseline integrity

1. Record exact `main` HEAD and architecture branch.
2. Run existing Gameplay Engine unit tests and simulator in a connected development environment.
3. Add CI/manual verifier for Python tests and document current limitations.
4. Freeze versioned event/schema conventions before hardware logger work.

**Exit:** gameplay baseline green and repeatable.

## Workstream 1 — Phase 0 CS rig (existing Issue #1)

1. Archive Bbo schematic, pin map, boot/recovery image and vendor tools.
2. Freeze NCS/toolchain version manifest.
3. Bbo Initiator <-> Bbo Reflector baseline.
4. Bbo Initiator <-> Nordic Tag Reflector.
5. Machine-readable structured logger with source timestamp/sequence.
6. 30-minute 1 m/3 m stability runs.

**Exit:** Phase 0 gate.

## Workstream 2 — Data contracts and replay

1. Implement typed `RangeObservation`, `MotionObservation`, `PhysicalSensorEvent`, `TrackUpdate`, `EvidenceEvent`.
2. Implement JSONL/Parquet recorder and immutable run manifest.
3. Implement replay that drives localisation/evidence without live hardware.
4. Add camera sync marker and calibration metadata.

**Exit:** one captured run can be replayed deterministically.

## Workstream 3 — Ranging and static localisation

1. Single-link test matrix.
2. Per-Anchor/per-antenna calibration registry.
3. Robust WLS/multilateration baseline.
4. 3/4/5/reference layout comparison and heatmaps.
5. Decide production four/fifth-node rule based on Phase 2 gate.

**Exit:** representative static XY gate and Anchor ADR validated/revised.

## Workstream 4 — Dynamic tracking

1. Asynchronous range-domain EKF.
2. Reorder/late observation policy.
3. Course geometry plausibility and track confidence.
4. Camera-ground-truth dynamic tests.
5. Adaptive process-noise from generic motion state.
6. IMM only if ablation proves benefit.

**Exit:** dynamic gate and UWB trigger decision.

## Workstream 5 — Generic motion and evidence fusion

1. Ball motion-state logger and labelled dataset.
2. Impact/rolling/settling/pickup/drop classifiers.
3. Evidence policies for tee, stroke, narrow feature, broad zone and cup.
4. Pending/rejected/review workflow.
5. Keep hole-specific movement-signature models in offline research namespace.

**Exit:** Phase 4 evidence gates.

## Workstream 6 — Gameplay vertical slice (existing Issue #3)

1. Local check-in/guest session and ball assignment.
2. Course/rule config loader.
3. Sensor-fusion adapter to existing Gameplay Engine.
4. Tee indicator and hole screen WebSocket/SSE.
5. Physical tee/cup sensor integration.
6. Operator correction/audit persistence.
7. 1,000-round soak and WAN-loss test.

**Exit:** one complete comfortable hole.

## Workstream 7 — Zone Gateway and field bus

1. Gateway interface simulator.
2. Pilot hardware with Ethernet + two protected RS-485 branches.
3. Scheduler, time sync, buffering and health.
4. Anchor/sensor field protocol.
5. Staged update/rollback and spare replacement.
6. One-hole then 2–3-hole zone test.

**Exit:** Gateway/fault/timing gates.

## Workstream 8 — Multi-ball / venue simulation

1. CS airtime/energy model from measured procedures.
2. 4-player/hole scheduling.
3. Neighbouring RF-cell coexistence.
4. 20/40/80-ball simulation and fault injection.
5. Handoff, reconnect storms and bounded queues.
6. Connectionless-CS/PAwR research benchmark kept separate.

**Exit:** Phase 5/7 gates and final zone-size decision.

## Workstream 9 — Custom ball EVT

Starts only after Workstreams 1–5 yield measured requirements.

1. Mechanical/RF concept and two-antenna experiment.
2. nRF54L15 + candidate nPM2100/CR2447 design.
3. Wake sensor + six-axis IMU retained for EVT.
4. Secure provisioning/test pads/DFU.
5. RF-in-shell, current, impact, balance and environmental tests.
6. Reduce sensor/antenna BOM only after ablation.

**Exit:** Phase 8/9 gates.

## Workstream 10 — DVT / pilot venue

1. Production-like Anchors/Gateways/enclosures/HMI.
2. 3–6-hole outdoor pilot.
3. Managed PoE/24 V/RS-485/UPS installation.
4. Staff usability, spares and maintenance procedures.
5. Security/OTA release rehearsal.
6. Scale to 18 holes only after pilot acceptance.
7. Architecture-specific FTO/regulatory review before commercial launch.

## Proposed next Issues / PRs

1. **Architecture schema foundation:** typed envelopes, event IDs, source clock/sequence and replay fixtures.
2. **Phase 0 logger:** Bbo/Nordic CS parser + run manifest.
3. **Static localisation baseline:** calibration + robust WLS + 3/4/5 ablation.
4. **Asynchronous range EKF:** replay-first tracker and camera metrics.
5. **Generic motion dataset:** logger/labels/baselines.
6. **Evidence fusion policy:** tee/stroke/feature/cup candidates and confirmation.
7. **Zone Gateway protocol/simulator:** scheduling/time/buffering/fault model.
8. **Multi-ball scheduler simulator:** 20/40/80 load and energy model.
9. **One-hole vertical slice:** update existing Issue #3 after evidence interface exists.
10. **Custom ball EVT gate:** design begins only after measurements.

## Critical dependency graph

```text
Gameplay baseline
      |
Schema + replay
      |
CS bring-up -> ranging -> static localisation -> dynamic tracker
      |                                      |
Motion dataset ------------------------------+
      |                                      |
      +----------> Evidence Fusion ----------+
                          |
                 One-hole gameplay slice
                          |
                Zone Gateway / multi-ball
                          |
                  Custom Ball EVT
                          |
                    Pilot Venue
```

## Three-month objective

- Phase 0 hardware working;
- replayable range/IMU/camera data;
- 3/4/5 Anchor static comparison;
- first asynchronous EKF result;
- simulated evidence -> Gameplay Engine -> hole screen flow.

## Six-month objective

- dynamic and generic-motion gates;
- physical one-hole vertical slice;
- pilot Gateway/field bus;
- 4-player and neighbouring-cell scheduler evidence;
- UWB go/no-go decision based on measured CS performance.

## Twelve-month objective

- custom Ball EVT evidence;
- 3–6-hole DVT/pilot;
- production-like network/HMI/OTA/fault recovery;
- architecture-specific FTO/regulatory review;
- evidence-backed decision for full 18-hole rollout.
