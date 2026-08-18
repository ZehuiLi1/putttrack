# ADR-001 — Spatial-First Production Authority

## Context

Public World Golf Systems patents describe hole-specific translational/rotational movement signatures used to identify valid strokes. PuttTrack needs automatic scoring while preserving a distinct, auditable architecture.

## Options

1. Hole-specific IMU signatures decide valid strokes and course events.
2. Spatial trajectory + generic motion + course geometry + physical evidence.
3. Camera-only tracking/scoring.

## Decision

Choose option 2 for production. Hole-specific movement-signature classifiers remain offline research only unless a later claims-based FTO review explicitly clears commercial use.

## Why

- creates a materially different evidence chain;
- easier to debug and explain;
- supports CS/UWB/vision substitution without rewriting gameplay;
- preserves physical cup/feature truth;
- supports publishable comparisons.

## Risks

Spatial infrastructure may cost more and CS may fail its field gates.

## Validation

Phases 1–6 of `VERIFICATION_MATRIX.md`, plus architecture-specific legal review before launch.

## Revisit trigger

- CS/UWB spatial path cannot meet scoring needs;
- relevant patent landscape changes;
- legal review clears a superior hybrid;
- movement-signature research demonstrates major value not achievable through generic motion evidence.
