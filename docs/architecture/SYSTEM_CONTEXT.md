# System Context and Authority Boundaries

## 1. Purpose

This document defines who and what can assert truth in PuttTrack. It is intentionally independent of a particular sensing technology.

The current staged architecture starts with ordinary-ball optical sensing and later adds smart-ball identity/motion and optional Channel Sounding.

## 2. Context diagram

```text
Players / Guests
       |
       v
Check-in / Active Player ---------------- Booking / optional account cloud
       |
       v
Physical Hole
tee / route / cup optical sensors
       |
       v
Hole / Zone Controller -------- future NFC/BLE smart-ball adapters
       |
       v
Semantic Evidence
       |
       v
Venue Edge / Gameplay Engine
       |
       +------> Presentation Hub / Hole HMI
       +------> Operator / Maintainer Console
       +------> queued Cloud Sync

Optional later inputs:
Smart Ball -> NFC/BLE/IMU evidence
CS subsystem -> trajectory/range evidence
```

## 3. Actors

### Player

May place/strike a normal or assigned smart ball and physically interact with course features. A player cannot directly mutate score through the screen.

### Booking owner / guest

May create or join a session. A persistent account is optional; a display name is sufficient for casual play.

### Operator

May pause a hole, quarantine a device and issue explicit audited corrections. Operator tools cannot edit authoritative state silently.

### Maintainer

May provision, diagnose and update hardware under a separate maintenance role. Maintenance actions are disabled or constrained during active play.

### Cloud services

May provide booking, optional identity, loyalty, analytics, release metadata and remote support. They are not the live venue score authority.

## 4. Trust and authority zones

| Zone | Trust level | Main contents | May authoritatively decide |
|---|---|---|---|
| Optical field sensors | Observation source | tee/route/cup beam state | raw physical observation only |
| Hole/Zone Controller | Trusted field coordinator | input timing, ordered patterns, health, buffers | field sequencing/semantic candidate, never final score |
| Smart Ball V1 | Authenticated observation/identity source | Ball ID, NFC/BLE state, motion, health | its own identity/source data only |
| CS subsystem V2 | Optional measurement source | range/track diagnostics | optional spatial estimate, never score by itself |
| Venue Edge | Primary authority | sessions, evidence acceptance, gameplay, score, audit | active player/ball association, semantic evidence acceptance, score |
| Presentation | Read-only projection | screens, audio, leaderboard | nothing authoritative |
| Operator | Privileged command source | review/correction commands | only explicit audited actions allowed by policy |
| Cloud | Eventually consistent external plane | bookings, optional identity/history, fleet | cloud-owned records, not current local round state |

## 5. Canonical authorities

- `PLAYER_ID`, `SESSION_ID`, active turn: Session Manager on Venue Edge.
- V0 ordinary-ball identity: implicit current active player/ball; `ball_id` may be null.
- V1 `BALL_ID`: Device Registry on Venue Edge, backed by provisioning/NFC/BLE evidence.
- Course zones, routes and rules: versioned Course Configuration on Venue Edge.
- Raw physical observation: originating sensor/controller plus immutable receive record.
- Generic ball motion state: smart-ball observation, accepted/used according to evidence policy.
- Optional calibrated CS track: localisation module when CS is enabled.
- Semantic evidence: Evidence/Evidence-Fusion boundary.
- Score/game state: Gameplay Engine and append-only gameplay event log.
- HMI state: derived projection; never source of truth.
- Cross-venue history/rewards: cloud after local completion sync.

## 6. Safety and score boundary

PuttTrack is an entertainment scoring system, not the venue life-safety controller. E-stop, machinery interlocks and electrical protection remain independent of gameplay software.

For score integrity:

```text
uncertain observation
  -> pending / retry / reject / review
  -> never silent score mutation
```

The first V0 design intentionally uses ordered physical evidence for launch/cup events rather than a single uncertain localisation point.

## 7. Offline behaviour

Venue Edge must continue to:

- run active-player/session state;
- accept optical field events;
- confirm/reject semantic evidence;
- score and display;
- store audit records;
- support operator recovery.

Smart-ball BLE/NFC and optional CS may degrade independently. WAN loss only delays cloud-owned functions and synchronization.
