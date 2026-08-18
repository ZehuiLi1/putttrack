# System Context and Authority Boundaries

## 1. Purpose

This document defines who and what can assert truth in PuttTrack. It is intentionally independent of a particular RF implementation.

## 2. Context diagram

```text
Players / Guests
       |
       v
Check-in & Ball Assignment ---- Booking / optional account cloud
       |
       v
Assigned Smart Balls
       |
       v
Hole HMI <------ Presentation Hub <------ Gameplay Engine
                                           ^
                                           |
                                      Semantic Evidence
                                           ^
                                           |
Smart Ball -- RF/IMU --> Anchors / Sensors --> Zone Gateway
                                           |
                                           v
                                       Venue Edge
                                           |
                               Operator / Maintainer Console
                                           |
                                      queued Cloud Sync
```

## 3. Actors

### Player

May present an assigned ball, make strokes and physically interact with course features. A player cannot directly mutate score through the screen.

### Booking owner / guest

May create or join a session. A persistent account is optional; a display name is sufficient for casual play.

### Operator

May pause a hole, quarantine a device and issue explicit audited score corrections. Operator tools cannot edit authoritative tables silently.

### Maintainer

May provision, diagnose and update hardware under a separate maintenance role. Maintenance actions are disabled or constrained during active play.

### Cloud services

May provide booking, optional identity, loyalty, analytics, release metadata and remote support. They are not the live venue score authority.

## 4. Trust and authority zones

| Zone | Trust level | Main contents | May authoritatively decide |
|---|---|---|---|
| Smart Ball | Untrusted observation source until authenticated | BALL_ID, motion, health, CS reflector | Its own device health and source data only |
| Anchor | Authenticated measurement source | CS observations and diagnostics | Per-link observation, never position/score |
| Zone Gateway | Trusted field coordinator | schedule, timestamps, sensor records, buffers | Field sequencing and transport status |
| Venue Edge | Primary authority | registry, sessions, localisation, evidence, gameplay, audit | Player assignment, semantic evidence acceptance, score |
| Presentation | Read-only projection | screens, audio, leaderboard | Nothing authoritative |
| Operator | Privileged command source | review/correction commands | Only explicit audited actions allowed by policy |
| Cloud | Eventually consistent external plane | bookings, optional identity/history, fleet | Cloud-owned records, not current local round state |

## 5. Canonical authorities

- `BALL_ID`: Device Registry on Venue Edge, backed by manufacturing provisioning.
- `PLAYER_ID`, `SESSION_ID`, assignment: Session Manager on Venue Edge.
- Course geometry and rules: versioned Course Configuration on Venue Edge.
- Raw observation: originating authenticated device plus immutable receive record.
- Calibrated range/track: Localisation module.
- Semantic evidence: Evidence Fusion.
- Score/game state: Gameplay Engine and append-only gameplay event log.
- HMI state: derived projection; never source of truth.
- Cross-venue history/rewards: Cloud after local completion sync.

## 6. Safety and score boundary

PuttTrack is an entertainment scoring system, not the venue life-safety controller. E-stop, machinery interlocks and electrical protection remain independent of gameplay software.

For score integrity:

```text
uncertain observation
  -> pending / retry / review
  -> never silent score mutation
```

## 7. Offline behaviour

The venue Edge must continue to:

- identify assigned balls;
- schedule local hardware;
- localise and track;
- confirm evidence;
- score and display;
- store audit records;
- support operator recovery.

WAN loss only delays cloud-owned functions and synchronization.
