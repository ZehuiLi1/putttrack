# Architecture Decision Records

ADRs record decisions that architecture work must not silently reverse. Each ADR includes validation and a revisit trigger.

| ADR | Decision | Current scope/status |
|---|---|---|
| [ADR-001](ADR-001-spatial-first-production-authority.md) | Spatial/evidence-first production authority; movement signatures remain research-gated | Accepted |
| [ADR-002](ADR-002-bluetooth-cs-conditional-primary.md) | Bluetooth CS conditional primary ranging | **Superseded for product dependency by ADR-013; retained for CS research** |
| [ADR-003](ADR-003-ball-reflector-anchor-initiator.md) | Ball is Reflector; powered Anchors are Initiators | CS-enabled subsystem only |
| [ADR-004](ADR-004-four-anchor-baseline-optional-reference.md) | Four-Anchor baseline; optional reference node | CS-enabled subsystem only |
| [ADR-005](ADR-005-zone-gateway-per-two-three-holes.md) | Zone Gateway per approximately 2–3 holes | Planning hypothesis; first pilot may use one controller/hole |
| [ADR-006](ADR-006-wired-field-bus-and-ethernet-backbone.md) | 24 V/protected RS-485 field bus; Ethernet/PoE backbone | Accepted |
| [ADR-007](ADR-007-local-edge-modular-monolith.md) | Local authoritative modular monolith | Accepted |
| [ADR-008](ADR-008-asynchronous-range-domain-ekf.md) | Asynchronous range-domain EKF for dynamic tracking | CS-enabled subsystem only |
| [ADR-009](ADR-009-physical-cup-and-tee-authority.md) | Physical tee/cup evidence | Accepted and strengthened by optical-first V0 |
| [ADR-010](ADR-010-ip-research-boundary.md) | Explicit production/research IP boundary | Accepted |
| [ADR-011](ADR-011-primary-cell-first-ball-power.md) | Primary-cell-first Ball power architecture | Accepted; nPM2100 vs direct battery remains A/B decision |
| [ADR-012](ADR-012-signed-staged-ota.md) | Signed staged OTA with rollback/quarantine | Accepted |
| [ADR-013](ADR-013-optical-first-venue-and-staged-smart-ball.md) | **Optical-first ordinary-ball V0; NFC/BLE/IMU smart-ball V1; CS optional V2** | **Accepted / current product dependency order** |

## ADR lifecycle

- `Accepted`: current architecture rule.
- `Proposed`: awaiting verifier/evidence.
- `Superseded`: replaced by another ADR; history retained.
- `Rejected`: considered but not selected.

An ADR is changed through a new PR that updates the Constitution, affected verification gates and the implementation roadmap.
