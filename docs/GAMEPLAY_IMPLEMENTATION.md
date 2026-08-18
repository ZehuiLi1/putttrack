# Gameplay Engine V1 — Implementation Contract

## Scope

The first gameplay engine implements the **Points Adventure** core needed to connect real sensor evidence to a comfortable social mini-golf experience.

It intentionally does not know how Channel Sounding, IMU classification, optical gates or cup sensors work internally.

Its input is confirmed evidence. Its output is deterministic game state and presentation data.

## Architecture

```text
nRF54L15 / CS / IMU / physical sensors
              |
              v
        evidence fusion
              |
              v
       confirmed events
              |
              v
       GameplayEngine
        /     |      \
       /      |       \
 scoring   state     audit
       \      |       /
        \     |      /
        presentation
              |
       tee screen / kiosk
```

## Confirmed event types

### `tee.presented`

An assigned ball is physically presented to the current hole's start station.

Behavior:

- any unfinished player may be first;
- only one player is armed at a time;
- the event does not itself count as a stroke;
- removing the ball before a stroke may cancel arming.

### `stroke.confirmed`

Upstream fusion has decided that a real stroke occurred.

The engine increments the active player's stroke counter exactly once.

### `feature.confirmed`

A configured bonus / hazard / route feature has been confirmed.

Each feature has a configurable score delta and maximum trigger count.

### `cup.confirmed`

Upstream evidence has confirmed hole completion.

For the first production version this should normally be created from a conservative combination of cup-zone position, ball motion and the physical cup sensor rather than a single weak observation.

### `pickup.detected`

Creates a player warning but does not directly mutate score. The policy for replacement / penalty can be added at a higher rule layer once field data exists.

### `operator.adjustment`

Explicit score correction with a reason. This is an audit event, not a hidden database edit.

## Idempotency

Every evidence event must have a globally unique `event_id` within a round.

The engine stores processed IDs and ignores exact duplicates. Feature rules also enforce their own trigger limits so two different packets describing the same one-shot bonus cannot award it repeatedly.

## Player order

Default social play is flexible:

```text
Players on H05:
Alex     incomplete
Sam      incomplete
Mia      incomplete
Chris    incomplete

Sam presents assigned ball first
        -> Sam READY
        -> Sam plays to cup
        -> Sam COMPLETE

Mia may now present her ball next.
```

The screen order is not a forced turn order.

## Hole progression

A group advances only after every player has completed the current hole.

The final hole behaves like a normal hole. There is no hidden one-shot rule and no special ball action that unexpectedly terminates the session.

## Default score curve

The initial example curve is PuttTrack-specific configuration:

```text
1 stroke   100
2           80
3           65
4           55
5           45
6           35
7           30
8+          25
```

This is not intended to be permanent product balancing. The real 18-hole course should be play-tested and tuned with telemetry.

## Ranking tie-break order

1. points;
2. skill-bonus points;
3. fewer strokes;
4. fewer hazard penalties;
5. shorter active-play time.

Speed is intentionally last so players are not encouraged to rush unsafely just to win a tie.

## Presentation API

`GameplayEngine.presentation()` returns a UI-safe view containing:

- current hole number / title / instruction;
- active player's display name and ball ID;
- every player's current-hole state;
- live ranking.

The hole UI should use this view rather than reading database tables directly.

## Evidence snapshot

`GameplayEngine.evidence_snapshot()` produces a serializable diagnostic snapshot for:

- dispute review;
- simulator tests;
- field diagnostics;
- replay tooling;
- future audit reports.

## What V1 deliberately does not implement yet

- sensor-fusion thresholds;
- CS localisation;
- generic IMU classifier;
- classic lowest-strokes mode;
- team scoring;
- congestion / group dispatch;
- seasonal challenge rules;
- cloud accounts / loyalty;
- operator UI;
- physical tee-screen rendering.

Those systems should call or consume this engine rather than being merged into it.

## Run the simulator

```bash
PYTHONPATH=src python simulator/demo_gameplay.py
```

## Run tests

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

## Next implementation slice

1. session/check-in service and server-side ball assignment;
2. JSON course/rule loader;
3. evidence-fusion interface from CS / IMU / cup sensor;
4. WebSocket presentation feed for a tee-screen prototype;
5. operator correction/audit store;
6. 18-hole simulator with congestion telemetry.
