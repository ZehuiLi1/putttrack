# PuttTrack Architecture Index

Start with [`../ARCHITECTURE_CONSTITUTION.md`](../ARCHITECTURE_CONSTITUTION.md).

## Core views

1. [`ARCHITECTURE_AUDIT.md`](ARCHITECTURE_AUDIT.md) — audited baseline, changes, evidence gaps and verification limitations.
2. [`SYSTEM_CONTEXT.md`](SYSTEM_CONTEXT.md) — actors, authority and trust boundaries.
3. [`HARDWARE_TOPOLOGY.md`](HARDWARE_TOPOLOGY.md) — full Ball-to-Cloud physical topology.
4. [`SMART_BALL.md`](SMART_BALL.md) — research Tag, custom Ball hardware, power, mechanics and firmware.
5. [`ANCHOR_RF_CELL.md`](ANCHOR_RF_CELL.md) — 3/4/5-Anchor evidence model, RF placement and production Anchor.
6. [`GATEWAY.md`](GATEWAY.md) — Zone Gateway decision, responsibilities and field-bus architecture.
7. [`VENUE_EDGE.md`](VENUE_EDGE.md) — local authoritative software architecture and persistence.
8. [`CLOUD_BOUNDARY.md`](CLOUD_BOUNDARY.md) — non-authoritative cloud responsibilities and reconciliation.
9. [`HMI.md`](HMI.md) — check-in, ball assignment, READY, hole screen, recovery and accessibility.
10. [`DATA_MODEL.md`](DATA_MODEL.md) — ownership, persistence, retention and replay authority.
11. [`EVENT_CONTRACT.md`](EVENT_CONTRACT.md) — observation-to-game semantic event envelope and ordering rules.
12. [`SCHEMAS.md`](SCHEMAS.md) — canonical JSON examples and compatibility rules.
13. [`STATE_MACHINES.md`](STATE_MACHINES.md) — Ball, Anchor, Gateway, track, evidence, session, OTA and fault states.
14. [`TIME_SYNC.md`](TIME_SYNC.md) — clock domains, source timestamps and research-camera synchronization.
15. [`SECURITY.md`](SECURITY.md) — identity, secure boot, signed OTA, local trust and operator authorization.
16. [`FAILURE_MODES.md`](FAILURE_MODES.md) — detect/degrade/recover/player/operator/scoring behavior.
17. [`MULTIBALL_SCALABILITY.md`](MULTIBALL_SCALABILITY.md) — connected-CS scheduling for 20/40/80-ball venue scenarios.
18. [`DEPLOYMENT.md`](DEPLOYMENT.md) — Research Rig, EVT, DVT, pilot and production evolution.
19. [`VERIFICATION_MATRIX.md`](VERIFICATION_MATRIX.md) — measurable go/no-go gates from single link to custom PCB.
20. [`IMPLEMENTATION_ROADMAP.md`](IMPLEMENTATION_ROADMAP.md) — dependency-ordered work packages.
21. [`ISSUE_MAP.md`](ISSUE_MAP.md) — live mapping from architecture workstreams to GitHub Issues.
22. [`KEEP_CHANGE_DEFER_REJECT.md`](KEEP_CHANGE_DEFER_REJECT.md) — explicit disposition of every requested hypothesis.
23. [`REFERENCES.md`](REFERENCES.md) — source register and fact/inference/unknown discipline.

Architectural decisions are indexed in [`../adr/README.md`](../adr/README.md).

## Authority order

When documents disagree, use this order:

1. `docs/PRODUCT_LOGIC_LOCK.md` for locked player/product behavior;
2. `docs/ARCHITECTURE_CONSTITUTION.md` for the converged technical architecture;
3. accepted ADRs for individual decisions;
4. supporting architecture views;
5. `docs/ARCHITECTURE.md` only as the pre-convergence historical hypothesis.
