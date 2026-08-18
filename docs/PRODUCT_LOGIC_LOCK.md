# PuttTrack Product Logic Lock

## Status

**Locked product behavior for architecture review.**

This document defines the player-facing behavior and game-authority boundaries that future architecture work must preserve unless there is strong evidence that a change materially improves the real venue experience.

It does **not** freeze the final RF topology, anchor count, gateway hardware, service decomposition, database choice, deployment model, or final custom-ball PCB.

---

## 1. Product Promise

PuttTrack should make the technology disappear.

A first-time player should be able to:

1. arrive with a booking or guest session;
2. receive a clearly identifiable assigned smart ball;
3. walk to a hole;
4. place the ball in the start/tee zone;
5. see their own name and an unmistakable READY cue;
6. play normal physical mini golf without touching a screen;
7. receive immediate bonus/hazard/stroke feedback;
8. have the cup/completion recorded automatically;
9. move to the next hole with no manual score entry;
10. receive a final digital result/leaderboard.

The system must feel at least as frictionless as current technology-enabled mini golf while improving self-recovery, pacing, accessibility and 18-hole continuity.

---

## 2. Locked Player Journey

### 2.1 Check-in

- Booking owner can identify the session with QR/code.
- Persistent player account is optional for ordinary play.
- Casual player needs only a display name.
- Account / loyalty linking can happen before or after play without blocking the start of a casual round.

### 2.2 Ball assignment

Canonical mapping is server-side:

```text
BALL_ID -> PLAYER_ID -> SESSION_ID
```

- One active assigned ball per player during normal play.
- Ball shell has a human-readable color/number/marker for physical recovery.
- Ball firmware does not own player profile, score, hole identity or game rules.

### 2.3 Course entry

- 9-hole and 18-hole products use the same underlying course/game platform.
- Hole 1 teaches the interaction through play rather than a long tutorial.
- Group should not require staff narration under normal conditions.

---

## 3. Locked Hole Interaction Loop

### 3.1 Flexible social order

Default mode does **not** force a fixed player order.

Any unfinished player in the current group may present their assigned ball next.

### 3.2 One active standard lane

For a normal single-lane hole:

- only one player/ball is armed at a time;
- other assigned balls cannot mutate that active player's score;
- future special multiplayer holes may define a different concurrency contract explicitly.

### 3.3 Tee/start arming

Canonical human-facing states:

```text
AVAILABLE
  -> DETECTED / CHECKING
  -> READY
  -> PLAYING
  -> COMPLETE
```

Recommended cue stack:

- visible light/ring state;
- text + player name;
- icon;
- short audio cue;
- never rely on color alone.

Removing the ball before the first confirmed stroke may cancel arming without penalty.

### 3.4 Physical play remains primary

After READY:

- player should normally touch no screen;
- player continues from the ball's actual resting position;
- no return-to-tee workflow between ordinary strokes;
- ordinary score recording is automatic.

### 3.5 Feedback must be non-blocking

Bonus/hazard/stroke/cup feedback should be immediate but short.

A celebration animation must not hold the internal game state hostage or prevent the next legal arming transition.

Target presentation latency after confirmed evidence: **<= 500 ms** for ordinary bonus/hazard feedback.

---

## 4. Locked Evidence-to-Game Boundary

Gameplay logic must not depend directly on a specific tracking technology.

Canonical pipeline:

```text
raw sensors / RF / vision
        -> measurement processing
        -> evidence fusion
        -> confirmed gameplay evidence
        -> Gameplay Engine
        -> score/state
        -> presentation
```

The Gameplay Engine consumes semantic evidence such as:

- `tee.presented`
- `tee.cancelled`
- `stroke.confirmed`
- `feature.confirmed`
- `cup.confirmed`
- `pickup.detected`
- `operator.adjustment`

The engine must not know whether a confirmation came from Channel Sounding, IMU, optical sensors, cup sensors, camera, UWB, or a future sensing technology.

---

## 5. Locked Scoring Principles

### 5.1 Automatic, deterministic, auditable

Every score mutation:

- comes from an explicit event;
- has a unique event ID;
- is idempotent;
- records source and timestamp;
- can be reproduced from evidence/audit history.

Duplicate sensor packets must never double-score.

### 5.2 Points Adventure is the first default mode

Base completion score rewards fewer strokes.

Additional course features may create:

- skill bonus;
- precision bonus;
- risk/reward route;
- hazard penalty;
- combo/multiplier;
- comeback opportunity.

Comeback mechanics should be skill/risk based rather than pure randomness.

### 5.3 Game rules are server/course configuration

Hole-specific score curves, features, labels and routes belong in course configuration rather than ball firmware.

### 5.4 Ranking does not reward unsafe rushing

Default tie-break preference:

1. total points;
2. skill/bonus points;
3. fewer strokes;
4. fewer hazard penalties;
5. active-play time only as a late tie-break.

---

## 6. Locked Completion / Cup Behavior

The final scoring authority must be conservative.

For the first production design, cup completion should normally be created by evidence fusion using multiple independent signals, for example:

```text
spatial evidence near/in cup
+ generic ball-motion evidence
+ physical cup sensor
=> cup.confirmed
```

A single uncertain localisation point must not silently complete a hole.

The final hole behaves like a normal complete hole. There is no hidden one-shot or special termination mechanic merely because it is the last hole.

---

## 7. Locked Recovery Philosophy

### 7.1 Uncertain means unresolved

If scoring-critical evidence is uncertain:

- do not invent a score;
- retry automatically when possible;
- hold the event pending if safe;
- provide operator review only when automatic recovery fails.

### 7.2 Human-readable recovery

Examples:

- wrong assigned ball -> show whose ball it is and which ball the player needs;
- recognition retry -> tell player to keep the ball in the start zone;
- hole unavailable -> clear fault/recovery instruction;
- operator adjustment -> explicit reason, never hidden DB mutation.

### 7.3 Graceful degradation

The architecture should support reduced-confidence operation where safe, but scoring-critical uncertainty must fail conservatively.

---

## 8. Locked 9/18-Hole Experience Structure

The venue should support both 9-hole and 18-hole products without creating two unrelated software systems.

Recommended 18-hole pacing:

### Act 1 — Holes 1-9

- H1-H3: learn the system and simple mechanics;
- H4-H6: route choice / risk-reward;
- H7-H8: combinations / richer interaction;
- H9: first-act finale / summary.

### Act 2 — Holes 10-18

- deeper use of known mechanics;
- higher-skill route choices;
- group/team variants where suitable;
- H17-H18 as climax;
- H18 still completes through the normal authoritative hole-completion flow.

---

## 9. Locked Separation of Authorities

### Ball

Owns physical identity and sensing only.

Must not be the authoritative store for:

- player profile;
- score;
- current hole rules;
- final localisation;
- game outcome.

### Measurement / fusion layer

Owns interpretation of RF/IMU/physical evidence and produces confidence-aware semantic events.

### Gameplay Engine

Owns deterministic game state and scoring transitions.

### Presentation

Owns what the player sees/hears, but cannot directly change authoritative score state.

### Operator tools

May correct results only through explicit audited commands/events.

### Cloud

May own identity/history/analytics/rewards, but local venue play should not require continuous Internet access to score a round safely.

---

## 10. Product Behavior That Is Explicitly Not Locked Yet

Architecture reviewers are encouraged to challenge and optimise:

- 3 vs 4 vs 5 production anchors;
- centre/reference anchor placement;
- connected vs future connectionless Channel Sounding scheduling;
- exact Gateway-per-hole / Gateway-per-zone topology;
- RS-485 vs Ethernet/PoE details;
- Edge PC vs distributed compute placement;
- modular monolith vs eventual service split;
- database / event-store technology;
- exact HMI hardware and display size;
- exact tee-presence sensing method;
- cup-sensor technology;
- final smart-ball battery / PMIC / IMU choice;
- final radio/antenna topology;
- UWB fallback/hybrid criteria;
- multi-ball scheduling and venue RF-cell boundaries;
- OTA implementation;
- cloud provider and external account/reward systems.

These are engineering decisions to be derived from the locked player experience, reliability requirements, patent constraints, experiments and commercial operating model.

---

## 11. Architecture Review Rule

Any proposed system architecture should be evaluated against one question first:

> Does this make the locked player journey simpler, faster, more reliable and easier to operate at an 18-hole venue?

Technology that does not improve player experience, scoring integrity, operational reliability, research value or total cost of ownership should not be added merely because it is technically interesting.
