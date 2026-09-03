# ADR-009 — Physical Cup and Tee Evidence in Production V1

## Context

Wireless localisation can produce outliers, especially in NLOS/multipath. Tee arming and cup completion are scoring-critical transitions that must feel immediate and trustworthy.

## Options

1. CS/IMU only.
2. Camera only.
3. Independent tee/cup sensors fused with spatial/motion evidence.
4. Manual confirmation.

## Decision

Choose option 3 for Production V1. Narrow scoring-critical feature gates also use physical sensors where practical. Broad zones may use geometry when confidence gates pass.

ADR-015 selects the first no-CS mechanism: a fixed PN532 at Tee, then an optical
Cup entry edge plus PN532 confirmation of the exact active Ball. The two Cup
sensors may share one controller but not one sensor identity.

## Why

- independent failure mode;
- prevents a single RF outlier from arming/completing;
- reduces disputes and support cost;
- supports graceful degradation and evidence audit;
- preserves zero-touch player flow.

## Risks

More field hardware, wiring and maintenance; sensor faults require health logic.

## Validation

Cup/tee false-positive/negative, stuck/missing sensor injection, 10,000-trial cup gate, one-hole soak and operator recovery tests.

## Revisit trigger

- long-term data proves CS+motion is independently authoritative at lower total lifecycle cost;
- a different cup/tee mechanism is mechanically superior;
- special hole design requires another confirmation policy.
