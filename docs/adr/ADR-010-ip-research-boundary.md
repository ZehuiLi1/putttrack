# ADR-010 — Production / Research IP Boundary

## Context

Public patent families disclose movement-signature, coded-ball/detector, movement-data transfer, charging and related venue combinations. Researching public disclosures is useful, but architecture differences alone are not a legal FTO determination.

## Options

1. Mix all research classifiers into production as they become accurate.
2. Isolate patent-sensitive work behind explicit research-only boundaries and legal gates.
3. Avoid all smart-ball research.

## Decision

Choose option 2.

Production uses spatial-first location, generic motion context, course geometry and independent physical evidence. Hole-specific movement-signature valid-stroke authority remains offline research unless an updated claims-based legal review clears the exact implementation.

## Why

- maintains clean architecture and audit history;
- supports research/papers without accidental product adoption;
- enables design-around discipline;
- preserves future options after patent/status changes.

## Risks

No design can be declared non-infringing without legal analysis; later patent families may cover other combinations.

## Validation

Maintain separate namespaces/config/release flags, architecture ADRs, code ownership and deployment checks. Obtain patent-attorney/FTO review before commercial freeze and target-jurisdiction launch.

## Revisit trigger

- relevant claims/status/licensing change;
- 2032/2033 landscape review;
- planned rechargeable/inductive charging or detector/activator design;
- planned movement/proximity-dependent RF power, multi-detector Ball tracking
  or coded magnetic tee activation;
- movement-signature research proposed for production authority;
- entry into a new jurisdiction.
