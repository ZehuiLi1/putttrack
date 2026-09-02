# ADR-002 — Bluetooth Channel Sounding as Conditional Primary Ranging

**Execution note (2026-09-02):** deferred for the active MVP by
[ADR-013](ADR-013-defer-cs-for-ble-motion-mvp.md). This record is retained as
the historical conditional-ranging decision, not the current dependency order.

## Context

PuttTrack needs sub-metre localisation in a rotating, ground-level, multipath object while keeping the ball small and low power. Bluetooth CS reuses the nRF54L15 radio; UWB offers stronger native precision but adds a second radio/antenna/system.

## Options

1. Bluetooth CS primary.
2. UWB primary.
3. Vision primary.
4. CS + UWB from day one.

## Decision

Use Bluetooth CS for Research Rig and Pilot V1, conditional on explicit accuracy, scalability and energy gates. Keep UWB as a same-course benchmark/fallback.

## Why

- one integrated BLE/CS radio/MCU;
- official nRF54L support and available research boards;
- smallest initial ball/BOM path;
- strong research novelty;
- product gameplay does not require centimetre-level continuous XY if physical scoring sensors remain.

## Risks

Connected 1:1 scheduling, random orientation, NLOS and multipath may prevent the required tail accuracy/update rate.

## Validation

Phases 0–5 and UWB decision gate in `VERIFICATION_MATRIX.md`.

## Revisit trigger

- dynamic P90 >0.6 m or P95 >1.0 m after full optimisation;
- NLOS errors cannot be detected/contained;
- multi-hole connected scheduling misses update/energy gates;
- a game feature requires repeatable <0.2 m geometry;
- UWB total-system comparison is superior.
