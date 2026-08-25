# ADR-013 — Optical-First Venue and Staged Smart-Ball Adoption

**Status:** Accepted  
**Date:** 2026-08-25

## Context

The earlier architecture treated Bluetooth Channel Sounding (CS) as the conditional primary localisation path for the first pilot. Subsequent product review showed that the scoring-critical questions for a standard mini-golf hole do not require continuous XY:

- is a ball present at the tee;
- did it actually leave the tee;
- which route/zone did it enter;
- did it enter a bonus/hazard feature;
- did it physically enter the cup.

These questions can be answered more deterministically with fixed optical sensors. The first venue demonstrator also needs to be buildable with ordinary balls so the course, event engine, scoring and feedback can be demonstrated before the smart-ball hardware is complete.

## Decision

Adopt a staged architecture.

### V0 — optical-first ordinary-ball MVP

The first one-hole pilot uses ordinary balls and fixed photoelectric sensing as the scoring-critical spatial authority.

Baseline input allocation is eight digital inputs:

1. tee presence;
2. launch confirmation in front of the tee;
3. route/zone A;
4. route/zone B;
5. route/zone C;
6. route/zone D;
7. upper cup/chute beam;
8. lower cup/chute beam.

The cup is confirmed only by the expected two-beam sequence. The standard V0 hole operates with one active ball/player at a time; `ball_id` may be null and the current active player owns accepted events.

Pilot controller baseline is the existing Waveshare ESP32-S3 PoE/Ethernet 8DI/8DO controller. Field sensors use industrial 10–30 V / 24 V modulated photoelectric pairs. The controller forwards semantic events over wired Ethernet to the local Venue Edge.

When more than eight field inputs are required, expand with protected RS-485/Modbus remote I/O. CAN is reserved for future intelligent actuator nodes rather than simple DI/DO expansion.

### V1 — smart-ball augmentation

Add a smart ball without replacing the optical venue layer.

Preferred ball direction:

- nRF54L15;
- NFCT with external NFC antenna;
- BLE for identity/health/state transport;
- 6-axis IMU or a reduced motion-sensor set after testing;
- one primary lithium cell;
- nPM2100 versus direct-battery power remains an A/B engineering decision.

Tee NFC may provide wake + deterministic Ball ID/session association. Hole NFC may later be added in the return chute if physical Ball ID confirmation is needed. IMU provides generic motion state. Optical sensors remain the scoring-critical spatial truth.

### V2 — optional Channel Sounding enhancement

Bluetooth CS remains an active research track and an optional product enhancement for:

- continuous trajectory visualisation;
- shot-path/heat-map analytics;
- multi-ball event association;
- advanced position-based game mechanics;
- research differentiation.

Failure or absence of CS must not prevent ordinary hole operation, route recognition or cup completion.

## Consequences

### Positive

- the first physical demo no longer waits for custom smart-ball or CS accuracy;
- critical score events are physically deterministic and auditable;
- the existing Gameplay Engine semantic-evidence boundary remains valid;
- smart-ball and CS work can be added incrementally without reworking the venue authority model;
- the six Bbo boards and Nordic Tags remain useful as a parallel CS research rig rather than sunk cost;
- field expansion uses conventional Ethernet/24 V/RS-485 infrastructure.

### Trade-offs

- ordinary-ball V0 assumes one active ball/player per standard hole because optical beams do not identify a ball;
- fixed optical hardware must be mechanically protected, aligned and maintained;
- zone tracking is discrete/event-driven rather than continuous XY;
- a later multi-ball mode may need smart-ball identity, BLE proximity, CS or another association mechanism.

## Supersedes / narrows earlier decisions

This ADR supersedes the **production/pilot dependency** portions of ADR-002, ADR-003, ADR-004 and ADR-008. Those ADRs remain valid as documentation of the CS research path when CS is enabled.

It reinforces ADR-006: wired Ethernet/PoE plus protected RS-485 remains the preferred venue infrastructure.

## Revisit triggers

Revisit the optical-first production authority only if measured field operation shows that optical sensing cannot meet reliability/maintenance requirements, or if a future game mode fundamentally requires concurrent continuous per-ball position as a scoring authority.
