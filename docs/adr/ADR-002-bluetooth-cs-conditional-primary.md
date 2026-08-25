# ADR-002 — Bluetooth Channel Sounding as Conditional Primary Ranging

**Status:** Superseded for product/pilot dependency by ADR-013; retained for CS research history.

## Context

PuttTrack originally investigated sub-metre continuous localisation of a rotating, ground-level, multipath object while keeping the ball small and low power. Bluetooth CS reuses the nRF54L15 radio; UWB offers stronger native precision but adds a second radio/antenna/system.

## Original options

1. Bluetooth CS primary.
2. UWB primary.
3. Vision primary.
4. CS + UWB from day one.

## Original decision

Use Bluetooth CS for the Research Rig and conditional Pilot V1, subject to accuracy, scalability and energy gates.

## Current scope after ADR-013

ADR-013 changed the product dependency order on 2026-08-25:

- the first playable/pilot path is ordinary-ball + optical sensing;
- smart-ball V1 adds NFC/BLE/IMU without requiring continuous localisation;
- Bluetooth CS remains an active research and optional product-enhancement path;
- UWB is no longer a required fallback decision for the core optical game.

Therefore this ADR now governs only experiments/features that explicitly enable CS, such as trajectory, shot analytics or multi-ball event association.

## Why CS research is still retained

- one integrated BLE/CS radio/MCU;
- official nRF54L support and available Bbo/Nordic research hardware;
- strong research value;
- potential trajectory and advanced-gameplay value;
- future product features may benefit even though core scoring does not require it.

## Risks

Connected 1:1 scheduling, random ball orientation, NLOS and multipath may limit tail accuracy, update rate and energy efficiency.

## Validation

Continue measured raw-data, estimator, calibration, multi-anchor and scheduling work under the CS research track. Do not convert an experimental CS result into a scoring dependency without a separate value/performance architecture decision.

## Revisit trigger

Promote CS into a specific commercial feature only when:

- that feature has clear user/product value;
- measured accuracy/tail error is sufficient;
- multi-ball scheduling is stable;
- ball power cost is acceptable;
- infrastructure/maintenance cost is justified;
- failure of CS does not silently corrupt scoring-critical optical events.
