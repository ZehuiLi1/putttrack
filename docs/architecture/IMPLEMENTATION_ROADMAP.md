# Dependency-Ordered Implementation Roadmap

## Principle

Deliver the playable venue in the lowest-risk order:

> optical one-hole MVP first -> smart-ball augmentation second -> Channel Sounding enhancement third.

Preserve semantic evidence contracts so later sensing technologies can be added without rewriting the Gameplay Engine.

---

## Workstream 0 — Baseline integrity

1. Keep the deterministic Gameplay Engine, event IDs and replay tests green.
2. Freeze the semantic evidence envelope used by physical controllers and future smart balls.
3. Preserve append-only audit/replay behaviour.

**Exit:** one simulated run reproduces the same gameplay result every time.

---

## Workstream 1 — Optical one-hole MVP

Build the first real physical hole with an ordinary ball.

### Hardware

- existing Waveshare ESP32-S3 PoE/Ethernet 8DI/8DO;
- 8 industrial through-beam photoelectric inputs;
- nominal 24 V field supply;
- wired Ethernet to Venue Edge;
- ordinary golf ball;
- static Challenge Roulette course geometry;
- simple light/audio/HMI feedback.

### Input map

1. tee presence;
2. tee launch confirmation;
3. zone/route A;
4. zone/route B;
5. zone/route C;
6. zone/route D;
7. upper cup/chute beam;
8. lower cup/chute beam.

### Software

- DI acquisition/debounce;
- edge timestamps/sequence;
- tee removal versus launch sequence;
- route lock/deduplication;
- two-beam cup confirmation;
- sensor-health events;
- Ethernet semantic-event adapter.

**Exit:** normal ball can produce READY -> SHOT -> ROUTE/ZONE -> HOLE COMPLETE and deterministic replay.

---

## Workstream 2 — Reward / presentation vertical slice

1. Configure Safe / Bonus / Jackpot / Hazard semantics on top of the four route inputs.
2. Ensure one legal route event cannot score repeatedly from beam chatter/re-entry.
3. Add immediate non-blocking LED/audio/HMI feedback.
4. Keep reward values in course/server configuration.
5. Add operator-visible event timeline and diagnostics.

**Exit:** a player can understand the complete interactive hole without staff explanation.

---

## Workstream 3 — Optical reliability and outdoorisation

1. Measure real ball beam-block duration versus speed.
2. Test player foot/club/hand false triggers.
3. Add high veto beams only where data shows they are needed.
4. Validate sensor alignment, sunlight, rain/wet surfaces, dirt and cleaning.
5. Recess TX/RX behind protected optical windows.
6. Run long soak/repeated-round tests.
7. Define fail-closed behaviour for missing/misaligned sensors.

**Exit:** one-hole physical sensing meets agreed false-positive/false-negative and maintenance targets.

---

## Workstream 4 — Field I/O and venue network expansion

1. Keep the first eight inputs direct to the Waveshare controller.
2. Add protected RS-485/Modbus remote DI/DO only when more I/O is required.
3. Validate remote-I/O polling/latency, bus fault isolation and recovery.
4. Keep fixed scoring events on wired Ethernet/RS-485.
5. Use CAN only for future intelligent motor/actuator nodes if justified.
6. Decide one-controller-per-hole versus shared zone cabinets from real cable/fault/maintenance evidence.

**Exit:** the one-hole controller pattern can be repeated across a small multi-hole pilot.

---

## Workstream 5 — Smart-ball NFCT/BLE prototype

Runs in parallel once V0 physical sensing is progressing; it is not a blocker for Workstreams 1–4.

### Available development path

- Bbo nRF54L15 + external NFC FPC for NFCT bring-up;
- Nordic nRF54L15 Tag when available as compact RF/IMU reference;
- optional XIAO nRF54L15 Sense as compact prototype.

### Sequence

1. NFCT tag/identity proof with phone/reader.
2. System-OFF NFC field wake.
3. NFC wake -> BLE advertisement/identity.
4. generic BLE health/battery/state record.
5. IMU logging and generic impact/rolling/stationary/pickup classification.
6. tee NFC session association.
7. optional Hole NFC identity station in the ball-return path.

**Exit:** smart ball adds deterministic identity and motion context without changing optical score authority.

---

## Workstream 6 — Smart-ball power / custom EVT

Do not freeze final PMIC/battery architecture from vendor precedent alone.

1. Measure representative NFC/BLE/IMU duty cycle.
2. Build custom-board A/B provision for:
   - primary cell direct to nRF54L15;
   - primary cell through nPM2100.
3. Compare sleep, NFC wake, BLE burst sag, usable capacity, battery estimation and total BOM/area.
4. Start with one primary cell; add a second only if lifetime evidence and mechanical balance justify it.
5. Validate NFC antenna tuning/orientation in the ball shell.
6. Validate mass balance, impact, potting/shell RF effects and service procedure.

**Exit:** evidence-backed ball power and mechanical architecture.

---

## Workstream 7 — Multi-hole pilot

1. Replicate the optical hole-controller pattern to 3–6 holes.
2. Validate player/session routing and one-active-ball standard-lane rule.
3. Install managed Ethernet/PoE, local 24 V supplies and RS-485 expansions where needed.
4. Add staff maintenance/diagnostic workflow.
5. Test WAN loss, controller replacement and replay recovery.
6. Introduce smart balls only after optical gameplay remains stable.

**Exit:** production-like venue behaviour without relying on CS.

---

## Workstream 8 — Channel Sounding research track

This remains active but does not gate the optical product path.

1. Freeze current NCS/toolchain manifests for Bbo/Nordic experiments.
2. Capture raw/sufficient per-tone Channel Sounding data.
3. Benchmark Nordic IFFT/phase-slope/RTT against MUSIC, OMP and public subspace methods on the same data.
4. Build per-link calibration/confidence metrics.
5. Run 3/4/5-node static and dynamic research tests if useful.
6. Evaluate multi-anchor scheduling separately from range-estimator accuracy.
7. Keep camera/survey truth only for research validation.

**Exit:** measured CS capability and failure modes, not a production claim.

---

## Workstream 9 — Optional CS product plugin

Only start after Workstream 8 demonstrates a feature with clear product value.

Candidate features:

- live trajectory display;
- shot-path analytics/heat maps;
- multi-ball event association;
- lost-ball assistance;
- advanced position-based hole mechanics.

Promotion gate includes accuracy/tail error, update rate, battery cost, RF scalability, infrastructure cost and user-visible value.

Core scoring must still function when the CS service is unavailable.

---

## Proposed next Issues / PRs

1. **Optical hole adapter:** Waveshare 8DI input map, debounce and semantic event output.
2. **Optical event tests:** tee launch, route lock and ordered cup confirmation fixtures.
3. **Challenge Roulette course config:** Safe/Bonus/Jackpot/Hazard reward rules.
4. **Hole controller Ethernet adapter:** publish/retry/event sequencing and health.
5. **Physical one-hole runbook:** sensor placement, 24 V wiring, acceptance matrix and soak log.
6. **RS-485 remote-I/O adapter:** deferred until >8 inputs are needed.
7. **NFCT bring-up:** Bbo + external NFC coil, field wake and Ball ID proof.
8. **Smart-ball BLE/IMU prototype:** generic states and health transport.
9. **Power A/B plan:** direct primary cell versus nPM2100 on custom EVT.
10. **CS estimator benchmark:** maintain as parallel research, not MVP dependency.

---

## Critical dependency graph

```text
Gameplay/Event baseline
        |
        v
Optical 8-DI one-hole MVP
        |
        +----> Reward / HMI
        |
        +----> Outdoor soak / RS-485 expansion
        |
        v
3–6 hole optical pilot
        |
        v
18-hole venue rollout candidate

Smart-ball NFCT/BLE/IMU ---------> augments the optical venue

CS research ---------------------> optional future trajectory plugin
```

---

## Near-term objective

- one ordinary-ball physical hole running on the existing 8DI/8DO controller;
- deterministic tee/route/cup evidence;
- reward/penalty feedback and local score UI;
- real optical pulse/false-trigger dataset;
- Bbo NFCT/BLE proof running in parallel.

## Medium-term objective

- 3–6-hole optical pilot;
- RS-485 remote-I/O pattern where needed;
- smart-ball NFC identity/wake and generic IMU/BLE state;
- measured direct-battery versus nPM2100 decision;
- CS research benchmark available as a separate optional module.

## Commercial-freeze objective

- repeatable outdoor maintenance and fault-recovery process;
- production-like event authority and audit;
- validated ball mechanical/power design if smart ball is retained;
- no scoring dependency on an unproven continuous-localisation subsystem;
- claims-based IP/regulatory review before commercial launch.
