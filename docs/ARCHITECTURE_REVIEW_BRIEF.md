# PuttTrack Architecture Review Brief

## Purpose

This brief is the handoff for a full system-architecture review after the player experience and gameplay authority boundaries have been locked.

The reviewer should **not** simply continue the current draft architecture. Treat the repository as evidence and constraints, then independently derive the most appropriate end-to-end architecture.

---

## Read First

Use the following as the canonical review order:

1. `docs/PRODUCT_LOGIC_LOCK.md` — locked product/player behavior and authority boundaries.
2. `docs/GAMEPLAY_EXPERIENCE.md` — detailed player journey and venue UX.
3. `docs/GAMEPLAY_IMPLEMENTATION.md` — current deterministic gameplay-engine event contract.
4. `docs/ARCHITECTURE.md` — current technical hypothesis, not untouchable truth.
5. `docs/EXPERIMENT_PLAN.md` — empirical validation plan.
6. `docs/PATENT_RESEARCH.md` — public prior-art/patent research and current design-around constraints.
7. `README.md` — current project summary.
8. `src/putttrack/gameplay/` — implemented gameplay state machine on the gameplay branch/main after merge.

---

## Locked Requirements the Architecture Must Preserve

- Guest-first play; permanent account optional.
- One assigned smart ball per player.
- Server-side `BALL_ID -> PLAYER_ID -> SESSION_ID` authority.
- Flexible play order within a group.
- One active ball/player on an ordinary single-lane hole.
- Automatic recognition and an unmistakable DETECTED -> READY interaction.
- No normal screen interaction required during physical play.
- Automatic stroke / feature / cup scoring.
- Non-blocking feedback.
- Deterministic and idempotent score transitions.
- Uncertain scoring evidence fails conservatively.
- Normal final-hole completion.
- Local venue scoring must survive Internet loss.
- Game rules must be independent of the underlying sensing technology.
- Production scoring must not rely on a hole-specific movement-signature model unless future legal/FTO review explicitly clears it.

---

## Current Technical Hypothesis — Challenge It

The current hypothesis is:

- moving prototype: Nordic nRF54L15 Tag;
- primary ranging: Bluetooth Channel Sounding;
- Ball: CS Reflector + generic IMU/motion node;
- fixed Anchors: CS Initiators;
- research geometry: 4 perimeter + 1 centre/reference anchor;
- current research Anchor candidate: Bbo nRF54L15 boards;
- calibration + robust/weighted multilateration;
- adaptive EKF / optional IMM;
- camera used as research/calibration ground truth, not required runtime positioning;
- physical cup sensor retained for first-production completion authority;
- optional ML for range-bias / measurement-confidence estimation rather than opaque end-to-end scoring;
- UWB kept as benchmark/Plan B if CS cannot satisfy field performance;
- movement-signature methods are a parallel research benchmark, not the production scoring authority.

The reviewer should identify which parts should be kept, changed, delayed or rejected.

---

## Required Architecture Questions

### A. Smart Ball

Define:

- MCU/radio architecture;
- battery/PMIC architecture;
- IMU/wake sensor strategy;
- antenna strategy;
- firmware state machine;
- CS role and connection management;
- BLE control/health interface;
- OTA/recovery strategy;
- data buffering boundaries;
- mechanical, balance and impact implications;
- prototype -> EVT -> production evolution.

### B. Anchor / RF Cell

Define:

- role of each anchor;
- production anchor count and geometry decision process;
- antenna/height/orientation strategy;
- scheduling ownership;
- synchronization requirements;
- local backhaul;
- power architecture;
- diagnostics;
- OTA/recovery;
- degraded operation when anchors fail.

### C. Hole / Zone Gateway

Decide whether a dedicated gateway is needed per hole, per several holes, or not at all.

Define responsibility for:

- CS scheduling;
- ball/anchor connection lifecycle;
- sensor I/O;
- clock/time synchronization;
- local buffering;
- physical feature/cup sensors;
- upstream protocol;
- offline behavior.

### D. Venue Edge

Define authoritative local components for:

- device registry;
- session/ball assignment;
- measurement ingestion;
- localisation;
- motion classification;
- evidence fusion;
- gameplay engine;
- scoring/event audit;
- tee-screen presentation;
- operator/admin tools;
- health monitoring;
- local persistence;
- replay/evidence;
- update management.

Prefer the simplest architecture that can safely support the expected venue scale.

### E. Cloud

Define what genuinely belongs in cloud rather than the local venue:

- bookings/account integration;
- loyalty/history;
- fleet analytics;
- remote support;
- software/config release control;
- cross-venue leaderboards/challenges;
- backup/sync.

The game must not fail merely because WAN connectivity is unavailable.

### F. Player-Facing HMI

Define:

- check-in flow;
- ball-assignment station;
- tee/start indicator;
- hole display;
- audio cues;
- accessibility / sunlight / outdoor operation;
- leaderboard behavior;
- wrong-ball / sensor-fault recovery;
- next-hole routing;
- operator override without confusing players.

### G. Multi-Ball / Venue Scale

Model realistic concurrency rather than only a one-ball lab demo.

Study at least:

- 4 players on one hole;
- multiple neighbouring holes active simultaneously;
- 20 / 40 / 80 balls present in the venue;
- connected Channel Sounding connection/scheduling limits;
- RF-cell isolation / anchor sharing;
- adaptive ranging update rates;
- stationary vs active-ball scheduling;
- handoff between holes/zones;
- connectionless/PAwR research as a future option, not an assumed production feature unless justified.

### H. Reliability / Safety / Operations

Define failure behavior for:

- one or more anchor loss;
- ball battery low/dead;
- wrong ball;
- duplicate packets;
- late/out-of-order events;
- cup sensor failure;
- localisation confidence collapse;
- gateway/edge restart;
- WAN loss;
- display failure;
- firmware-version mismatch;
- manual correction/audit.

### I. Data / Timing

Define canonical schemas and clock domains for:

- raw CS observations;
- per-anchor range estimates;
- IMU samples/states;
- physical sensor events;
- localisation tracks;
- fused gameplay evidence;
- gameplay events;
- presentation events;
- audit/evidence records.

Include synchronization strategy for research camera ground truth.

### J. IP / Research Boundaries

Preserve an explicit separation between:

1. production spatial-first/generic-motion architecture;
2. offline/research movement-signature benchmark;
3. future hybrid concepts that require a fresh FTO/legal review before commercial adoption.

Do not claim freedom to operate from architecture differences alone.

---

## Required Deliverables From the Architecture Pass

The review should result in repository-ready artifacts, not just prose chat:

1. **Architecture Constitution** — source of truth for system responsibilities and authority boundaries.
2. **System Context Diagram** — player, ball, hole hardware, venue edge, cloud, operator.
3. **Hardware Topology** — smart ball, anchors, gateway, sensors, PoE/Ethernet/low-voltage wiring.
4. **Software Component Architecture** — modules/services and ownership of each state/data object.
5. **Canonical Data Flow** — from RF/IMU observation to final score and display feedback.
6. **State Machines** — ball, anchor/gateway, gameplay/hole, session, fault/recovery.
7. **Event/Data Schemas** — stable contract boundaries.
8. **Multi-Ball Scheduling Model** — expected connection/ranging load and degradation strategy.
9. **Offline/Failure Model** — authoritative behavior when components fail.
10. **Security Model** — device identity, OTA signing, local/admin authorization, cloud trust boundary.
11. **Deployment Model** — 1-hole prototype, pilot, full 18-hole venue.
12. **BOM/Build Stages** — research hardware vs custom EVT/DVT/production hardware.
13. **Verification Matrix** — architecture requirements mapped to measurable tests.
14. **Decision Records** — explicit Keep / Change / Defer decisions against the current hypotheses.
15. **Implementation Roadmap** — ordered work packages and dependencies, not a flat backlog.

---

## Review Standard

The architecture should optimize jointly for:

- player friction;
- scoring integrity;
- RF/positioning performance;
- multi-ball scalability;
- fault recovery;
- field maintainability;
- outdoor installation practicality;
- battery life;
- BOM / installation cost;
- research usefulness;
- IP/design-around discipline;
- ability to evolve without rewriting the game layer.

Do not add complexity without identifying the failure mode or product benefit it solves.
