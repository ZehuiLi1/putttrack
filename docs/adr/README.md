# Architecture Decision Records

ADRs record decisions that architecture work must not silently reverse. Each ADR includes validation and a revisit trigger.

| ADR | Decision |
|---|---|
| [ADR-001](ADR-001-spatial-first-production-authority.md) | Spatial-first production authority; movement signatures remain research-gated |
| [ADR-002](ADR-002-bluetooth-cs-conditional-primary.md) | Bluetooth CS is the conditional primary ranging technology |
| [ADR-003](ADR-003-ball-reflector-anchor-initiator.md) | Ball is Reflector; powered Anchors are Initiators |
| [ADR-004](ADR-004-four-anchor-baseline-optional-reference.md) | Four-Anchor production baseline; optional evidence-triggered reference node |
| [ADR-005](ADR-005-zone-gateway-per-two-three-holes.md) | Zone Gateway per approximately 2–3 holes |
| [ADR-006](ADR-006-wired-field-bus-and-ethernet-backbone.md) | 24 V/protected RS-485 field bus; Ethernet/PoE backbone |
| [ADR-007](ADR-007-local-edge-modular-monolith.md) | Local authoritative modular monolith |
| [ADR-008](ADR-008-asynchronous-range-domain-ekf.md) | Asynchronous range-domain EKF for dynamic tracking |
| [ADR-009](ADR-009-physical-cup-and-tee-authority.md) | Physical tee/cup evidence in Production V1 |
| [ADR-010](ADR-010-ip-research-boundary.md) | Explicit production/research IP boundary |
| [ADR-011](ADR-011-primary-cell-first-ball-power.md) | Primary-cell-first Ball power architecture |
| [ADR-012](ADR-012-signed-staged-ota.md) | Signed staged OTA with rollback/quarantine |

## ADR lifecycle

- `Accepted`: current architecture rule.
- `Proposed`: awaiting verifier/evidence.
- `Superseded`: replaced by another ADR; history retained.
- `Rejected`: considered but not selected.

An ADR is changed through a new PR that updates the Constitution, affected verification gates and the implementation roadmap.
