# PuttTrack Architecture Constitution

**Status:** Architecture convergence v2  
**Date:** 2026-08-25  
**Applies to:** one-hole MVP, smart-ball evolution, 18-hole venue architecture and CS research  
**Product-behaviour authority:** [`PRODUCT_LOGIC_LOCK.md`](PRODUCT_LOGIC_LOCK.md)

This document is the current technical source of truth. The key change from v1 is that **continuous RF localisation is no longer a prerequisite for the first playable product path**. PuttTrack now develops the venue and the smart ball in stages.

The first physical product slice is an **optical-first, ordinary-ball, event-driven hole**. The smart ball is a later augmentation. Bluetooth Channel Sounding remains an active research and optional experience layer rather than a scoring dependency.

See [`adr/ADR-013-optical-first-venue-and-staged-smart-ball.md`](adr/ADR-013-optical-first-venue-and-staged-smart-ball.md).

---

## 1. Architecture rule

PuttTrack optimises, in order:

1. scoring integrity;
2. effortless player flow;
3. deterministic physical evidence;
4. outdoor maintainability;
5. graceful recovery and auditability;
6. staged product delivery;
7. smart-ball capability and research value without contaminating game authority.

A technology is not a dependency merely because it is interesting or potentially accurate.

The Gameplay Engine consumes **semantic evidence**, not raw sensor technology:

```text
physical sensor / smart ball / RF / operator
                 |
                 v
        measurement processing
                 |
                 v
        confirmed evidence
                 |
                 v
        Gameplay Engine
                 |
          score + state
                 |
        presentation/audit
```

---

## 2. Staged product architecture

### V0 — optical-first ordinary-ball MVP

The first one-hole demonstrator uses an ordinary ball and fixed photoelectric sensing.

```text
                         Local Venue Edge
                    game / scoring / event log
                              ^
                              |
                        wired Ethernet
                              |
                Waveshare ESP32-S3 8DI/8DO
                              |
                     24 V optical sensors
                              |
             +----------------+----------------+
             |                |                |
           Tee x2          Zone x4          Cup x2
```

V0 provides:

- tee presence;
- launch confirmation;
- coarse route/zone recognition;
- bonus/hazard/jackpot events;
- ordered two-beam cup confirmation;
- automatic score and feedback;
- one active player/ball per standard lane.

No smart ball, NFC, BLE, CS, UWB or camera-derived XY is required for V0 play.

### V1 — smart-ball augmentation

The venue sensing remains in place. Add a smart ball for identity and motion context:

```text
Smart Ball
nRF54L15
 + NFCT / NFC antenna
 + BLE
 + IMU
 + primary cell
       |
       +---- NFC at tee: wake + Ball ID/session association
       +---- BLE: identity/health/battery/motion state
       +---- IMU: impact/rolling/stationary/pickup evidence
```

A Hole NFC read zone may later identify the ball in the return chute if required. It does not replace physical cup sensing.

### V2 — optional Channel Sounding enhancement

Bluetooth CS may be added for:

- continuous trajectory visualisation;
- shot-path analytics and heat maps;
- multi-ball optical-event association;
- advanced position-based game mechanics;
- research differentiation and future localisation features.

CS failure must not prevent ordinary route recognition, bonus/hazard events or cup completion.

---

## 3. Canonical technology decisions

### 3.1 Production/pilot path

- **Optical through-beam sensing is the first scoring-critical spatial authority.**
- First outdoor sensors should be industrial modulated photoelectric pairs, nominal 24 V / 10–30 V, mechanically recessed/protected.
- First one-hole controller is the available **Waveshare ESP32-S3 PoE/Ethernet 8DI/8DO**.
- Hard events travel over **wired Ethernet** to the local Venue Edge.
- If field I/O exceeds onboard capacity, expand through **protected RS-485/Modbus remote I/O**.
- CAN is reserved for future intelligent actuator nodes where its arbitration model adds value; it is not the default simple DI/DO expansion bus.
- Venue Edge remains authoritative and WAN-independent.
- Game rules, rewards and hole configuration stay server-side.

### 3.2 Smart ball

- **nRF54L15 remains the leading V1 ball MCU/radio candidate.**
- NFCT is retained because it can support near-field tee wake/identity without a separate NFC tag IC.
- BLE transports ball identity, health, battery and generic state.
- A 6-axis IMU is retained for prototyping; final sensor count is determined by measured classification and power benefit.
- Primary-cell architecture remains preferred.
- Compare `direct battery -> nRF54L15` against `battery -> nPM2100 -> nRF54L15` on custom hardware before final power freeze.
- Do not add a second primary cell until measured lifetime and mechanical balance prove it is necessary.

### 3.3 Channel Sounding research

- Nordic nRF54L15 Tag remains a moving RF/IMU reference.
- The six Bbo nRF54L15 boards remain a useful CS research rig.
- Existing raw-IQ, estimator, multilateration and tracking work remains valid research.
- Production does **not** assume four/five CS Anchors per hole unless a later game requirement and measured benefit justify them.
- ADRs describing CS link direction, Anchor layouts and asynchronous range EKF apply only when the CS subsystem is enabled.

### 3.4 Explicitly not required for V0/V1 core scoring

- continuous XY;
- CS Anchor network;
- UWB;
- camera runtime localisation;
- magnetic landmark network;
- motorised roulette/turntable mechanism;
- cloud-authoritative score.

---

## 4. One-hole MVP constitution

The current physical build target is described in [`architecture/OPTICAL_FIRST_ONE_HOLE_MVP.md`](architecture/OPTICAL_FIRST_ONE_HOLE_MVP.md).

Baseline eight-input allocation:

| DI | Evidence |
|---|---|
| 1 | tee presence |
| 2 | launch confirmation |
| 3 | zone/route A |
| 4 | zone/route B |
| 5 | zone/route C |
| 6 | zone/route D |
| 7 | upper cup/chute beam |
| 8 | lower cup/chute beam |

The two tee inputs distinguish launch from manual removal. The two cup inputs require a legal ordered passage before `cup.confirmed`.

DI3–DI6 provide **discrete event-driven zone tracking**, not exact coordinates.

The first signature-hole design direction is a static **Challenge Roulette** layout with one tee, four route/zone outcomes and one final cup. Reward semantics can start as `ZONE_A..D` and later be configured as Safe / Bonus / Jackpot / Hazard.

The centre feature is fixed with lighting/graphics in V0; a motorised mechanism is deferred.

---

## 5. Field controller constitution

### One-hole pilot

The Waveshare 8DI/8DO controller is the hole controller.

Responsibilities:

- digital input acquisition and debounce;
- source timestamps and sequence numbers;
- ordered-pattern detection such as tee launch and cup passage;
- local sensor health/fault handling;
- short outage buffering/retry;
- simple output triggers;
- semantic event publication to Venue Edge.

It does **not** own authoritative score.

### Expansion

When more I/O is needed:

```text
Hole/Zone Controller
       |
protected RS-485 / Modbus RTU
       |
remote 8/16-DI / DI-DO modules
```

Prefer remote I/O near sensor clusters rather than long individual GPIO wiring to one cabinet.

For the wider venue, several holes may later share a zone cabinet/gateway if wiring, maintenance and fault-domain testing support it. Do not force the old 2–3-hole gateway assumption onto the first physical MVP.

---

## 6. Venue network constitution

```text
                         Internet / Cloud
                         (non-authoritative)
                                ^
                                |
                         queued sync
                                |
                       Local Venue Edge
                    authoritative gameplay
                                |
                    Managed Ethernet / PoE
                +---------------+---------------+
                |               |               |
          Hole controller   HMI/display     admin/check-in
                |
         local 24 V field supply
                |
     optical sensors / RS-485 remote I/O
```

- Wired Ethernet/PoE is preferred for controllers, displays and Edge connectivity.
- 24 V SELV is preferred for outdoor field sensing/control.
- RS-485 is the default simple field-expansion bus.
- Core scoring remains functional during WAN loss.
- Outdoor surge, earthing, enclosure, condensation and service-access design remain mandatory.

---

## 7. Event and authority boundary

The field layer emits semantic evidence such as:

```text
tee.presented
tee.launch_confirmed
zone.entered
feature.confirmed
cup.entry_candidate
cup.confirmed
sensor.fault
```

Events include stable IDs, source, timestamps and sequence numbers so duplicate transport cannot duplicate score.

### V0 identity

Ordinary balls have no electronic ID. A normal single-lane V0 hole therefore has one active player/ball at a time. Optical events are attributed to the active player/session.

### V1 identity

A smart ball introduces `BALL_ID` and authenticated/session-aware association. Player/session mapping remains server-side.

The ball never owns:

- player profile;
- score;
- course rules;
- final game outcome.

---

## 8. Reward and feedback constitution

Reward logic belongs to course/game configuration, not sensors.

Example four-route configuration:

| Route | Example |
|---|---:|
| Safe | 0 |
| Bonus | +30 / +50 |
| Jackpot | +80 / x2 mode |
| Hazard | -20 / -30 |

Only a legal first route event for a shot should mutate its route reward unless the configured game mode explicitly permits another rule. Repeated beam interruptions cannot repeatedly award points.

Visual/audio feedback should be immediate and non-blocking. Complex LED/DMX/Art-Net sequences may later live on a dedicated lighting controller; the hole controller sends semantic triggers.

---

## 9. Smart-ball constitution

V1 smart ball goal:

```text
one primary cell
       |
 direct-power path OR nPM2100 candidate
       |
    nRF54L15
    /   |   \
 NFCT  BLE  IMU
  |
external NFC coil
```

Normal field architecture may keep VDD present while nRF54L15 enters System OFF with NFCT wake enabled. Do not use a PMIC ship/hibernate state that removes SoC power if NFC wake is required.

V1 smart-ball responsibilities:

- physical Ball ID;
- NFC wake/near-field association support;
- BLE discovery/health/state transport;
- generic motion evidence;
- battery/firmware/health reporting.

CS is optional and can be enabled later without changing the authority boundary.

---

## 10. Research separation

The repo keeps two parallel paths:

### Product delivery path

```text
Gameplay baseline
 -> optical one-hole MVP
 -> reward/feedback
 -> outdoor wiring/soak
 -> smart-ball NFC/BLE/IMU
 -> multi-hole pilot
 -> optional CS enhancement
```

### CS research path

```text
Bbo / Nordic Tag bring-up
 -> raw Channel Sounding data
 -> estimator benchmark
 -> calibration / confidence
 -> multi-anchor / tracking experiments
 -> optional product plugin if justified
```

Neither path invalidates the other. CS research must not delay the optical MVP.

---

## 11. Production evolution

### V0 acceptance

A normal ball can complete one physical hole with:

- READY at tee;
- launch detected correctly;
- one of four zone/route events recognised;
- matching reward/penalty feedback;
- ordered cup confirmation;
- deterministic score replay from event log.

### V1 acceptance

A smart ball can add:

- NFC tee wake/identity;
- BLE state/health;
- IMU motion state;
- optional Hole NFC identity;

without changing or weakening V0 optical scoring.

### V2 acceptance

CS may be promoted for a specific feature only after that feature demonstrates measured user/product value and acceptable accuracy, power, RF scalability and maintenance cost.

---

## 12. Rejected shortcuts

- Do not infer scoring-critical route/cup state from one uncertain localisation point.
- Do not require a smart ball before the venue can demonstrate automatic play.
- Do not use Wi-Fi/BLE as the primary transport for fixed scoring-critical sensors when wired Ethernet/RS-485 is practical.
- Do not add motorised course mechanisms to the first sensor/software MVP unless they are necessary to test the core game loop.
- Do not put score authority in field controllers, balls or presentation clients.

---

## 13. Architecture review rule

Every proposed component should answer:

> Does this materially improve scoring integrity, player experience, maintainability, staged delivery or a measured optional feature?

If not, it should not be a dependency of the current stage.
