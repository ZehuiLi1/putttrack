# ADR-004 — Four-Anchor Production Baseline, Optional Reference Node

## Context

Research purchases support five identical Anchors, but production must balance geometry, tail error, airtime, wiring and maintenance.

## Options

1. Three Anchors.
2. Four perimeter Anchors.
3. Four plus mandatory centre Anchor.
4. Four plus evidence-triggered elevated/reference Anchor.

## Decision

Use five nodes for research ablation. Production baseline is option 2; retain option 4 only when measured P95/no-fix/blind-region improvement justifies it. Reject a mandatory ground-centre node.

## Why

- four gives redundancy over the 2D minimum;
- centre location can be obstructed and geometrically weak;
- an elevated LOS reference may provide more useful diversity;
- fifth-node cost includes airtime, calibration, wiring and fault management.

## Risks

Four may be insufficient in strongly obstructed holes.

## Validation

Compare 3, 4, centre-5, elevated-5, best-4-of-5 and weighted-5. Keep fifth node if P95 improves >=20%, no-fix falls >=50%, or a scoring-critical blind region is resolved.

## Revisit trigger

- course geometry changes;
- production enclosure/antenna changes tail performance;
- physical feature sensors reduce required continuous XY;
- Anchor sharing changes geometry/fault domain.
