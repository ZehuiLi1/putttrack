# Architecture Convergence Audit

## Repository baseline

- Base branch: `main`
- Audited base SHA: `8f7cbd28e75f0581f55b4ffb2dc56ff949a74c30`
- Accepted Architecture PR head reviewed: `234f8f9c61477bbe8483fd11c732e4d4ae2d54a2`
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

## Architecture acceptance verification

Acceptance was performed against PR #5 head `234f8f9c61477bbe8483fd11c732e4d4ae2d54a2`.

### Consistency checks

- `PRODUCT_LOGIC_LOCK.md` and `ARCHITECTURE_CONSTITUTION.md`: no authority or player-flow conflict found.
- Supporting architecture views and ADR-001 through ADR-012: consistent with the Constitution.
- `KEEP_CHANGE_DEFER_REJECT.md`: consistent with the Constitution and ADRs.
- `VERIFICATION_MATRIX.md`, `IMPLEMENTATION_ROADMAP.md` and Issues #1, #3, #6–#13: dependency order and exit gates are aligned.
- PR file comparison confirms no changes to `src/putttrack/gameplay/`, `simulator/` or `tests/`; the architecture PR is documentation/README-only.
- Relative Markdown targets in README, architecture index, ADR index and Bbo hardware evidence register were checked against the PR tree; no missing internal target was found.
- GitHub reported the PR mergeable and there were no submitted reviews or unresolved review threads.

### Executed baseline

Environment:

```text
Python 3.13.5
PYTHONPATH=src
```

Commands:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python simulator/demo_gameplay.py
```

Result:

```text
7 tests run
7 passed
simulator exit code 0
```

The test workspace was reconstructed from the exact unchanged gameplay/source files at `main@8f7cbd28e75f0581f55b4ffb2dc56ff949a74c30`; the PR comparison proves those files are byte-identical on the Architecture PR. The container still could not resolve `github.com`, so repository cloning itself was unavailable, but source identity and PR scope were verified through the GitHub API.

### Acceptance result

**ACCEPT.** No architecture blocker was found. PR #5 is suitable to become the technical source of truth, subject to normal merge and subsequent exact-head verifier implementation in Issue #6.

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
