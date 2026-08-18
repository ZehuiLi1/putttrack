# Architecture Convergence Audit

## Repository baseline

- Base branch: `main`
- Audited base SHA: `8f7cbd28e75f0581f55b4ffb2dc56ff949a74c30`
- Locked product source: `docs/PRODUCT_LOGIC_LOCK.md`
- Existing deterministic gameplay authority: `src/putttrack/gameplay/`
- Tracking issue: #4

## What was preserved

- guest-first/player-ball-session model;
- flexible order and one active player on ordinary holes;
- DETECTED -> READY -> PLAYING interaction;
- semantic evidence boundary and deterministic/idempotent Gameplay Engine;
- local WAN-independent game authority;
- spatial-first/generic-motion production boundary;
- Nordic Tag/Bbo research rig and camera-ground-truth experiment intent.

## What changed

1. Five Anchors are no longer a production assumption. Four is the geometry baseline; the fifth is an optional RF-optimal/elevated reference justified by P95/no-fix evidence.
2. Dynamic tracking uses asynchronous range-domain EKF. Snapshot multilateration is retained for initialization/reacquisition/static experiments.
3. One Zone Gateway per approximately 2–3 holes is the production planning topology.
4. Field nodes use 24 V + protected/isolated RS-485; Ethernet/PoE is the venue backbone.
5. Venue Edge becomes a local authoritative modular monolith with append-only semantic/gameplay audit.
6. Standard connected CS is explicitly sequential and adaptive; only active balls receive high-rate ranging.
7. Physical tee/cup evidence remains first-production authority.
8. Primary-cell custom ball and signed staged OTA are formal architecture decisions.

## What remains evidence-gated

- CS accuracy under final shell/course NLOS;
- persistent multi-link behavior and effective active update rate;
- four vs optional fifth Anchor;
- single vs dual antenna production benefit;
- one vs two motion sensors;
- nPM2100/CR2447 service life;
- exact Gateway MCU and production Anchor module;
- exact Zone size and shared Anchor opportunities;
- IMM and ML value;
- UWB fallback;
- connectionless CS/PAwR;
- rechargeable/wireless charging.

## Verification limitations of this pass

This pass is architecture/documentation work. Repository content and branch/file topology were verified through the GitHub API. The execution container could not resolve `github.com`, so it could not clone the repository or execute the existing Python test suite. No claim is made that tests ran during this pass. The first implementation item is therefore an exact-head baseline verifier in a connected development/CI environment.

## Completion test

The Architecture Constitution and supporting documents now answer:

- Ball contents, firmware states, power/security/service path;
- Anchor role/count/placement and failure behavior;
- Zone Gateway need and responsibility;
- 18-hole power/network topology;
- Edge/Cloud authority split;
- event/data/time/security contracts;
- stroke/feature/cup evidence path;
- multi-ball connected-CS scheduling;
- UWB and PAwR triggers;
- research/production/IP boundaries;
- development stages and measurable gates.
