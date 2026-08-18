# ADR-007 — Local Edge Modular Monolith

## Context

Live game state must remain consistent and operational during WAN loss. Venue scale is moderate; state/order/recovery are harder than CPU throughput.

## Options

1. Cloud-first microservices.
2. Many local microservices/containers.
3. Local modular monolith in a few supervised processes.
4. Fully distributed logic in Gateways.

## Decision

Choose option 3. Venue Edge owns local authority; Gateways coordinate fields but not final score. Cloud is eventually consistent and non-authoritative for live play.

## Why

- simple transactional game authority;
- low latency and easy replay;
- fewer deployment/failure modes;
- modules can be split later when evidence requires it;
- one venue does not need cloud-scale orchestration.

## Risks

Poor internal boundaries could become a monolith that is difficult to evolve; Edge is a significant local dependency.

## Validation

Typed contracts, process restart/replay tests, venue-load simulation, WAN-loss tests, warm-spare restore and module ownership review.

## Revisit trigger

- a module requires independent scaling/security/release cadence;
- process isolation materially improves reliability;
- multi-venue central functions emerge;
- Edge resource/load gates are missed.
