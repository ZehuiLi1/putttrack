# Architecture Verification Matrix

All thresholds are candidate engineering gates. They must be confirmed against actual venue/game requirements before production release. Report P50/P90/P95, missing/no-fix rate and failure tails; mean error alone is insufficient.

## Phase 0 — Baseline and single-link bring-up

| Requirement | Method | Pass gate |
|---|---|---|
| Gameplay baseline | run existing unit tests/simulator | all tests pass; deterministic replay identical |
| Bbo <-> Bbo CS | Nordic official sample/config | repeatable IFFT/PBR and available phase/RTT outputs |
| Bbo <-> Nordic Tag | fixed 1 m/3 m | >=99% successful scheduled procedures in 30 min LOS; no unexplained reset |
| Structured logging | parser/replay test | all records have identity, boot, sequence, source time, config and units |
| Version record | build manifest | exact NCS/toolchain/board/firmware captured |

## Phase 1 — Single-link ranging

Conditions: 0.5/1/2/3/5/8/10 m, orientations, near-ground, body blockage, walls/corners, metal/course features, final enclosures where available.

| Metric | Gate |
|---|---|
| LOS P50 absolute range error | <=0.25 m target |
| LOS P90 | <=0.50 m |
| LOS P95 | <=0.80 m |
| Missing/outlier rate LOS | <=2% |
| NLOS detection/quality discrimination | >=90% recall for defined severe-error class, with reported precision |
| Orientation/path dataset | complete across declared matrix |

NLOS raw error is not required to meet LOS accuracy; the architecture must detect, down-weight or recover from it.

## Phase 2 — Static 2D localisation / Anchor decision

Compare 3, four perimeter, four+ground-centre, four+elevated reference, best-4-of-5 and robust weighted five.

| Metric | Gate |
|---|---|
| Representative static P50 | <=0.25 m target |
| Static P90 | <=0.50 m |
| Static P95 | <=0.80 m |
| No-fix rate | <1% |
| Maximum/tail | reported with heatmap, never hidden |
| Production fifth-Anchor retention | >=20% P95 improvement or >=50% no-fix reduction, or resolves critical blind region |

## Phase 3 — Dynamic rolling object

Trajectories: slow/fast straight, diagonal, wall rebound, obstacle/S route, ramp, stop/restart and pickup/reposition.

| Metric | Gate |
|---|---|
| Dynamic P50 | <=0.30 m target |
| Dynamic P90 | <=0.60 m; stretch <=0.50 m |
| Dynamic P95 | <=1.00 m |
| Trajectory RMSE | reported by route/condition |
| Live localisation latency | <=250 ms from source observation to track update |
| Reacquisition after bad ranges/outage | <=1 s target |
| Stationary drift | <=0.25 m over 10 s |
| False movement while stationary | <0.1% of evaluated windows |

Compare snapshot WLS, WLS+KF, asynchronous range EKF and optional adaptive/IMM variants.

## Phase 4 — Motion and semantic evidence

Dataset includes valid putt, weak/strong tap, rolling, slowing, wall/ball collision, pickup/carry, hand roll, drag, drop/bounce, ramp/rollback and cup sequence.

| Metric | Gate |
|---|---|
| Stroke sensitivity/recall | >=99% |
| False-stroke rate | <=0.1% of labelled non-stroke episodes |
| Pickup/carry F1 | >=0.98 target |
| Motion-state latency | <=100 ms for impact trigger; other states reported |
| Generic-state robustness | hold-out by day/ball/person/route |
| Hole-specific signature | research result only; no production authority |

## Phase 5 — Multi-ball and scheduler

Load: 4 players/hole, adjacent cells, 20/40/80 balls; one active player per ordinary hole.

| Metric | Gate |
|---|---|
| Active ball position update | >=5 Hz target under representative load |
| Confirmed event to HMI | <=500 ms P95 |
| Cross-ball/cross-hole score mutation | zero |
| Observation/evidence loss | zero silent loss; explicit gap records only |
| Zone Gateway/Edge CPU/memory | <60% steady under P95 load |
| Queue growth | bounded and drains after burst |
| Scheduler headroom | >=40% under representative P95 load |
| Next-hole handoff/READY | <=2 s target after valid presentation |
| Ball energy/update | measured for each schedule/config |

## Phase 6 — One complete gameplay hole

Run real/simulated assignment -> READY -> strokes -> features -> cup -> next player.

| Metric | Gate |
|---|---|
| 1,000-round soak | no unrecoverable state corruption |
| Score integrity | >=99.9% event correctness; every mutation traceable |
| Duplicate/replay | zero duplicate mutation |
| Cup false positive | zero in >=10,000 representative trials before removing guardrails |
| Cup false negative | <0.1% target with physical sensor/fusion, reported confidence |
| First-time player start | four-player group starts H1 without verbal training in usability test |
| Completion feedback | non-blocking; next legal arming not delayed by animation |
| WAN loss | round completes and syncs later |

## Phase 7 — Venue-scale simulation and fault injection

- 18 holes / 6 planning zones;
- 80-ball inventory;
- process/gateway/node restarts;
- one/two Anchor loss;
- bus faults;
- screen/WAN/database pressure;
- duplicate/late/out-of-order events;
- staged failed OTA.

Pass:

- no incorrect authoritative score;
- bounded recovery time documented per failure;
- queues/resources within budgets;
- degraded state/HMI/operator actions match `FAILURE_MODES.md`;
- no single noncritical node failure stops the whole venue.

## Phase 8 — Power and service life

Measure—not estimate from datasheet alone:

- sleep/advertisement;
- connection setup/maintenance;
- CS procedure/result transfer;
- IMU wake/active windows;
- OTA/service;
- temperature/battery pulse effects.

| Metric | Gate |
|---|---|
| Energy/procedure | recorded by configuration and antenna path |
| Average current workload profile | replayed from measured venue duty cycle |
| Minimum projected service life | >=2 years with conservative derating |
| Stretch service life | >=5 years |
| Low-battery prediction | service threshold provides sufficient replacement lead time |
| No brownout/reset | representative battery/temperature/radio burst tests |

## Phase 9 — Custom PCB/core

| Area | Gate |
|---|---|
| RF | sensitivity/TX/ranging compared with reference; agreed degradation and no new blind orientations |
| Balance | measured centre-of-mass/roll bias within product threshold |
| Impact | no resets/contact/solder/core migration across defined endurance sequence |
| Environment | water/UV/thermal/cleaning tests pass |
| Security | provisioning, signed boot/update, rollback/recovery pass |
| Manufacturing | identity/current/RF/IMU/balance calibration repeatable |
| BOM/supply | qualified primary/alternate parts and lifecycle review |
| Legal/regulatory | architecture-specific FTO/regulatory checkpoints completed |

## UWB decision gate

Run a same-course/camera-ground-truth UWB benchmark if CS misses representative dynamic/scalability/energy gates after architecture-level optimisation. Compare:

- P50/P90/P95 and NLOS tails;
- active update/latency;
- energy/update and service-life projection;
- ball volume/mass/RF complexity;
- Anchor/network count and multi-ball scalability;
- BOM/certification/maintenance.

Do not switch solely because UWB has a better datasheet figure; switch when total system evidence is superior for the locked gameplay.
