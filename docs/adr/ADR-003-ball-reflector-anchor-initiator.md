# ADR-003 — Ball Reflector, Powered Anchor Initiator

## Context

The battery-powered ball should minimize active scheduling, result processing and connection-management load. Fixed infrastructure has wired power and maintainable compute.

## Options

1. Ball Initiator, Anchors Reflectors.
2. Ball Reflector, Anchors Initiators.
3. Dynamic role switching.

## Decision

Choose option 2 for Production V1. Zone Gateway coordinates powered Anchor Initiators; Ball is Reflector plus generic motion node.

## Why

- powered infrastructure carries active procedure/result work;
- aligns with tag-like reflector model;
- ball remains small and simple;
- central scheduling and diagnostics are easier;
- final XY remains off-ball.

## Risks

Multiple Anchor links to one ball may create connected-CS setup/scheduling overhead. Current supported operation must be treated as sequential, not concurrent.

## Validation

Measure persistent multi-link versus rotating-link setup, energy, procedure success and handoff in Phase 5.

## Revisit trigger

- controller/stack cannot maintain the required local links;
- ball-initiated or connectionless mode demonstrates materially lower total energy/latency;
- selected non-Nordic platform requires a different interoperability model.
