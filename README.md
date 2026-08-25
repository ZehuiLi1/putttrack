# PuttTrack

PuttTrack is a research and product-development repository for an automatic-scoring mini-golf venue and a staged smart-ball platform.

The current product direction is **venue-first and event-driven**:

> Build a complete ordinary-ball optical hole first; add NFC/BLE/IMU smart-ball capability second; keep Bluetooth Channel Sounding as an optional trajectory/research layer rather than a scoring dependency.

## Current source of truth

- [`docs/PRODUCT_LOGIC_LOCK.md`](docs/PRODUCT_LOGIC_LOCK.md) — player/game authority boundaries.
- [`docs/ARCHITECTURE_CONSTITUTION.md`](docs/ARCHITECTURE_CONSTITUTION.md) — current technical architecture.
- [`docs/architecture/OPTICAL_FIRST_ONE_HOLE_MVP.md`](docs/architecture/OPTICAL_FIRST_ONE_HOLE_MVP.md) — immediate physical build target.
- [`docs/adr/ADR-013-optical-first-venue-and-staged-smart-ball.md`](docs/adr/ADR-013-optical-first-venue-and-staged-smart-ball.md) — decision that changed the product dependency order.

The older [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and CS-focused ADRs remain useful research history, but they are no longer the production dependency chain.

## Converged staged direction

```text
V0 — ORDINARY BALL / OPTICAL VENUE

ordinary ball
    |
tee x2 -> route/zone x4 -> cup x2
    |
Waveshare ESP32-S3 PoE/Ethernet 8DI/8DO
    |
wired Ethernet
    |
Local Venue Edge
Gameplay Engine / scoring / event log / HMI


V1 — SMART BALL AUGMENTATION

nRF54L15 + NFCT + BLE + IMU + primary cell
    |
NFC tee wake / Ball ID
BLE health/state
IMU motion evidence
    |
existing optical venue remains scoring authority


V2 — OPTIONAL CHANNEL SOUNDING

CS research / trajectory / analytics / multi-ball association
    |
optional feature plugin
    |
core optical game still runs when CS is absent
```

## Immediate one-hole build

The first physical demo is a static **Challenge Roulette** hole with one tee, four route/zone outcomes and one final cup.

The V0 controller uses exactly eight digital inputs:

| DI | Function |
|---|---|
| DI1 | Tee ball presence |
| DI2 | Launch confirmation in front of tee |
| DI3 | Route/zone A |
| DI4 | Route/zone B |
| DI5 | Route/zone C |
| DI6 | Route/zone D |
| DI7 | Upper cup/return-chute beam |
| DI8 | Lower cup/return-chute beam |

This fits the existing Waveshare ESP32-S3 8DI/8DO controller without an expander.

Outdoor field sensors should be industrial modulated through-beam photoelectric pairs on nominal 24 V. Fixed scoring-critical events go upstream over wired Ethernet. When more field I/O is required, expand with protected **RS-485/Modbus remote I/O**; CAN is reserved for future intelligent actuator nodes rather than simple DI expansion.

See [`docs/architecture/OPTICAL_FIRST_ONE_HOLE_MVP.md`](docs/architecture/OPTICAL_FIRST_ONE_HOLE_MVP.md).

## V0 gameplay model

V0 uses ordinary balls and assumes one active player/ball in a normal single-lane hole.

```text
ball placed on tee
 -> READY
 -> tee clears + launch beam confirms passage
 -> SHOT STARTED
 -> one route/zone event
 -> immediate bonus/hazard/jackpot feedback
 -> upper cup beam
 -> lower cup beam
 -> HOLE COMPLETE
```

DI3–DI6 are discrete event-driven zone evidence, not continuous XY localisation.

A first reward configuration can be:

- Safe: 0;
- Bonus: +30 / +50;
- Jackpot: +80 / x2 mode;
- Hazard: -20 / -30.

Rewards are course/server configuration, not sensor firmware. Duplicate beam events must never duplicate score.

## Smart-ball V1

The smart ball is an augmentation, not a prerequisite for the first venue demo.

Current preferred direction:

- **nRF54L15** remains the MCU/radio candidate;
- NFCT + external NFC coil for tee wake/near-field identity;
- BLE for identity, firmware, battery/health and generic state transport;
- 6-axis IMU during prototyping for impact/rolling/stationary/pickup evidence;
- one primary lithium cell;
- direct battery versus nPM2100 remains an A/B hardware decision;
- CS capability stays available in the nRF54L15 but is not required in V1 firmware.

A later Hole NFC read zone may identify the smart ball in the return chute. Physical optical cup detection remains authoritative.

## Channel Sounding research

The CS work is deliberately retained as a parallel research track.

Available research hardware remains valuable:

- Nordic nRF54L15 Tag boards as moving RF/IMU references;
- six Bbo nRF54L15 boards for initiator/reflector, raw-data and multi-node experiments.

Research topics remain:

- raw Channel Sounding capture;
- Nordic baseline versus MUSIC/OMP/subspace estimators;
- per-link calibration/confidence;
- multi-anchor ranging and tracking;
- optional trajectory and multi-ball event association.

The key rule is that **CS research must not delay the optical one-hole MVP**.

## Gameplay authority

The deterministic/idempotent Gameplay Engine under `src/putttrack/gameplay/` consumes semantic evidence rather than depending on a specific sensor technology.

Canonical examples:

```text
tee.presented
tee.launch_confirmed
zone.entered
feature.confirmed
cup.entry_candidate
cup.confirmed
pickup.detected
operator.adjustment
```

The ball, field controller and HMI never own authoritative score.

## Venue infrastructure

Current baseline:

```text
Cloud (non-authoritative)
       ^
       | queued sync
       |
Local Venue Edge
       |
Managed Ethernet / PoE LAN
       |
Hole / Zone controllers
       |
24 V sensors + protected RS-485 expansion
```

- local venue play continues through WAN loss;
- Ethernet/PoE is preferred for controllers, displays and Edge;
- 24 V is preferred for outdoor field sensing/control;
- RS-485/Modbus is the default simple DI/DO expansion path;
- CAN is optional for future intelligent motor/actuator subsystems;
- Home/consumer wireless links are not the scoring-critical fixed-sensor backbone.

## Evidence foundation

The repository already contains typed evidence/event models, deterministic replay and CS research capture tooling. Those capabilities remain useful under the new architecture because the Gameplay Engine is sensor-agnostic.

Run the main verifier:

```bash
python tools/verify.py
```

Replay the checked-in evidence example:

```bash
PYTHONPATH=src python tools/replay_run.py experiments/evidence_replay_example
```

Gameplay demo/tests:

```bash
PYTHONPATH=src python simulator/demo_gameplay.py
PYTHONPATH=src python -m unittest discover -s tests -v
```

## Current dependency order

1. Keep existing Gameplay Engine/event/replay tests green.
2. Build the **8-DI optical one-hole MVP** with an ordinary ball.
3. Integrate reward/penalty feedback, local HMI and deterministic event logging.
4. Soak-test tee, zone and cup detection; collect real pulse durations/false-trigger data.
5. Add RS-485 remote I/O only when the first eight inputs are insufficient.
6. Bring up nRF54L15 NFCT/BLE/IMU smart-ball prototype in parallel.
7. Add NFC tee identity/wake without changing optical score authority.
8. Validate primary-cell power and direct-versus-nPM2100 custom-board options.
9. Expand to multi-hole outdoor pilot.
10. Continue CS research as an optional trajectory/analytics plugin and promote only features that pass measured value/accuracy/power/scalability gates.

## Documentation map

### Product/gameplay

- [`docs/PRODUCT_LOGIC_LOCK.md`](docs/PRODUCT_LOGIC_LOCK.md)
- [`docs/GAMEPLAY_EXPERIENCE.md`](docs/GAMEPLAY_EXPERIENCE.md)
- [`docs/GAMEPLAY_IMPLEMENTATION.md`](docs/GAMEPLAY_IMPLEMENTATION.md)
- [`docs/GAMEPLAY_VERTICAL_SLICE_V1.md`](docs/GAMEPLAY_VERTICAL_SLICE_V1.md)

### Current architecture

- [`docs/ARCHITECTURE_CONSTITUTION.md`](docs/ARCHITECTURE_CONSTITUTION.md)
- [`docs/architecture/OPTICAL_FIRST_ONE_HOLE_MVP.md`](docs/architecture/OPTICAL_FIRST_ONE_HOLE_MVP.md)
- [`docs/architecture/HARDWARE_TOPOLOGY.md`](docs/architecture/HARDWARE_TOPOLOGY.md)
- [`docs/architecture/SMART_BALL.md`](docs/architecture/SMART_BALL.md)
- [`docs/architecture/IMPLEMENTATION_ROADMAP.md`](docs/architecture/IMPLEMENTATION_ROADMAP.md)
- [`docs/architecture/EVENT_CONTRACT.md`](docs/architecture/EVENT_CONTRACT.md)
- [`docs/architecture/VENUE_EDGE.md`](docs/architecture/VENUE_EDGE.md)
- [`docs/adr/`](docs/adr/)

### Research

- [`docs/EVIDENCE_FOUNDATION.md`](docs/EVIDENCE_FOUNDATION.md)
- [`docs/EXPERIMENT_PLAN.md`](docs/EXPERIMENT_PLAN.md)
- [`docs/research/PRE_HARDWARE_READINESS.md`](docs/research/PRE_HARDWARE_READINESS.md)
- [`experiments/phase0_cs/`](experiments/phase0_cs/)

## IP / legal note

This repository records engineering research, public prior art and design constraints; it is not legal advice or a freedom-to-operate opinion. Production decisions still require an appropriate claims-based IP and regulatory review before commercial freeze.
