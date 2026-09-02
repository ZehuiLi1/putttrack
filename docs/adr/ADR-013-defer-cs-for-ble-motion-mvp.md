# ADR-013 — Defer Channel Sounding for the BLE + Motion MVP

**Status:** Accepted

**Date:** 2026-09-02

## Context

The nRF54L15 Tag is now physically available. SWD recovery, complete backup,
signed MCUboot and an end-to-end BLE OTA update have been validated. The
repository also has a sensor-independent Gameplay Engine, an evidence boundary
and a simulated one-hole vertical slice.

The previous execution order made Bluetooth Channel Sounding (CS), the Bbo
Anchor rig, ranging and dynamic localisation prerequisites for replacing the
simulated evidence path. That delays learning from the hardware already in hand
and is unnecessary for a one-hole prototype whose authoritative tee, cup and
narrow feature events can come from physical sensors.

## Decision

For the current MVP:

1. defer CS, Anchors, multilateration, range-domain tracking and CS scheduling;
2. keep nRF54L15 for BLE, generic motion sensing, security and signed OTA;
3. use physical tee/cup/feature sensors as independent gameplay evidence;
4. keep the Ball free of player identity, hole rules and score authority;
5. keep CS code, fixtures, contracts and earlier ADRs as dormant research;
6. do not substitute IMU dead reckoning or advertise continuous XY without
   measured independent ground truth.

ADR-002 remains historical justification for CS as a conditional ranging
candidate, but it no longer controls the active implementation order. ADR-003,
ADR-004 and ADR-008 are likewise dormant until CS is explicitly reactivated.

## Consequences

Positive:

- the proven OTA path and the physical Tag immediately become useful;
- the team can validate sensor quality, ball mechanics, BLE reliability and
  evidence-to-game integration before building Anchor infrastructure;
- the locked zero-touch gameplay and deterministic score boundary remain intact;
- fewer simultaneous unknowns make failures easier to diagnose.

Costs and limits:

- no continuous trajectory or final XY is available;
- broad geometry-only bonus/hazard zones are unavailable;
- more physical hole sensors may be required;
- motion candidates require context and cannot independently authorize every
  scoring event;
- CS research work remains incomplete rather than disproven.

## Validation

The no-CS MVP passes when:

- a repository-owned Tag image reports identity, health and generic motion;
- signed BLE OTA still supports test, rollback and confirmation;
- raw IMU episodes are replayable with timestamp/drop metadata;
- one physical hole completes normal rounds without manual score entry;
- ambiguous signals fail conservatively and operator adjustments remain audited;
- duplicate or foreign-ball signals never mutate the wrong score.

## Revisit trigger

Reconsider CS only for a specific product question: required spatial gameplay,
unacceptable physical-sensor cost, excessive unresolved evidence, or a bounded
CS/UWB experiment justified by measured MVP limitations.
