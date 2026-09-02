# ADR-012 — Signed, Staged OTA with Rollback and Quarantine

## Context

PuttTrack contains many unattended field devices and battery balls. A failed or incompatible update can affect score integrity across multiple holes.

## Options

1. Manual cable flashing only.
2. Unsigned convenient OTA.
3. Signed images, compatibility policy, staged rollout, health verifier and rollback/quarantine.

## Decision

Choose option 3. Manual/service flashing remains a recovery mechanism.

## Why

- protects score/device integrity;
- enables maintainable venue fleet;
- limits blast radius;
- supports known-good rollback;
- provides audit and version compatibility.

## Risks

Boot/key/provisioning complexity; flash constraints; a badly designed release process can still cause outages.

## Validation

Unsigned/downgrade rejection, failed-image rollback, power-loss during update, cohort canary, version mismatch quarantine, spare replacement and credential revocation tests.

Physical positive-path status on 2026-09-02: the nRF54L15 Tag accepted a signed
BLE image into its secondary slot, test-booted it, was remotely confirmed and
remained active after a second reboot. Deliberate rollback, interrupted upload,
unsigned/downgrade rejection and production-key lifecycle tests remain open.

## Revisit trigger

- selected hardware cannot support safe dual-image/recovery design;
- production key architecture changes;
- offline/manual maintenance proves lower total risk for a device class;
- security/regulatory requirements become stricter.
