# PuttTrack Gameplay Experience Constitution

## Purpose

PuttTrack should feel as frictionless as the best tech-enabled mini-golf experiences while remaining technically and legally its own system.

This document defines the player journey, hole interaction model, scoring philosophy, recovery behavior and operational constraints for the first real venue implementation.

The product goal is simple:

> A player should understand what to do without staff instruction, never need a pencil or manual score entry, receive immediate but non-blocking feedback, and trust that the game remembered what actually happened.

## 1. Current Puttshack experience: public evidence

Public Puttshack material and recent player reports consistently describe the following experience pattern:

1. Players book/register and have a player profile / screen name.
2. Each player receives an individually assigned smart golf ball.
3. At a hole, the assigned ball is placed at the designated start marker / tee area.
4. The system recognises the ball/player; the hole becomes ready and a green light indicates that play can begin.
5. A screen at the hole explains the challenge and shows player identity / scoring.
6. The smart ball and course technology automatically record strokes plus bonus/hazard interactions.
7. Players within a group can play in flexible order, but the hole is effectively played by one active player at a time.
8. Scoring is points-based rather than ordinary lowest-stroke-only mini golf. Fewer strokes earn more points, while interactive features add or remove points.
9. Real-time screen feedback makes hazards, bonuses and special routes visible to the group.
10. The final result is stored digitally and can be delivered to players after the game.

Puttshack also uses a deliberately social game-design pattern: bonuses and hazards create comeback opportunities so a weaker golfer can still remain competitive.

### Experience strengths worth retaining

- No manual scorecard.
- One physical ball is the player's identity during play.
- Fast automatic player recognition at each hole.
- Flexible play order inside the group.
- A very obvious ready state before a putt.
- Immediate hole-local feedback.
- Interactive risk/reward rather than pure stroke counting.
- Group leaderboard / social competition.
- Strong physical-digital integration.

### Friction we should improve

PuttTrack should deliberately avoid several common sources of friction visible in public descriptions/reviews of tech-enabled mini golf:

- Do not require every casual guest to create a full permanent account before playing.
- Do not require a player to wait through long full-screen animations before the next player can start.
- Do not make a single special final-hole action unexpectedly terminate the round.
- Do not depend on players noticing one color only; use icon/text/audio plus color.
- Do not require staff intervention for ordinary ball-recognition retries.
- Do not permit a stale or duplicate sensor event to alter a score twice.
- Do not let one missing sensor or uncertain localisation silently create an irreversible scoring result.

## 2. PuttTrack experience principles

### P1 — Guest first, account optional

A booking owner may prepare the group before arrival, but a casual guest only needs a display name.

Persistent membership, email history and rewards are opt-in after the game or during booking, not mandatory to start playing.

### P2 — One ball, one visible player identity

Server-side mapping:

```text
BALL_ID -> PLAYER_ID -> SESSION_ID
```

The ball stores no player profile or score authority.

Human-readable shell color / number should be shown on the player's card so accidental ball swaps are easy to correct.

### P3 — Any player may step up next

There is no forced turn order in the default social mode.

The first eligible assigned ball presented to the tee station becomes the active player.

Only one active ball/player is armed on a standard hole at a time.

### P4 — Ready must be unambiguous

A player should never wonder whether the system is listening.

Recommended cue stack:

- tee ring / light: neutral -> amber -> green;
- screen: player name + `READY`;
- short audio cue;
- icon as well as color.

### P5 — Feedback is immediate but non-blocking

Hazard / bonus / cup feedback should typically appear as a short toast / animation while the game state is already readying the next action.

Do not make a 5-10 second celebration animation block throughput.

### P6 — Physical play remains primary

Screens explain and celebrate the physical hole; they must not turn ordinary 18-hole play into a sequence of menus.

A player should normally touch no screen during a hole.

### P7 — Skill-based comeback mechanics

Prefer route choice, precision targets, risk/reward and combination bonuses over pure randomness.

A trailing player should have a plausible high-risk comeback route, but the leading player's skill must still matter.

### P8 — Scoring must be auditable

Every score mutation comes from an idempotent event with a source and timestamp.

Examples:

- `stroke.detected`
- `feature.bonus`
- `feature.hazard`
- `cup.confirmed`
- `operator.adjustment`

### P9 — Uncertain means unresolved, not guessed

If a scoring-critical event is uncertain, the system should hold it as pending evidence, continue safe play where possible, and request automatic retry or operator review instead of inventing a result.

## 3. Venue session journey

### Stage A — Booking / pre-arrival

Default products:

- Quick Play: 9 holes.
- Full Adventure: 18 holes.
- Later: Team Battle / event packages.

Booking owner selects party size and time. Player names may be entered before arrival but are not required.

### Stage B — Arrival / check-in

1. Scan booking QR or enter booking code.
2. Confirm party size.
3. Add player display names / optional avatars.
4. Optional account / loyalty login; skip is always available for ordinary play.
5. System assigns balls server-side.
6. Screen shows each player:
   - display name;
   - ball color / number;
   - optional team.
7. Collect putters and balls.

Target: a normal four-player group should be able to complete this without staff assistance.

### Stage C — Course entry

The group receives a clear course assignment and first-hole direction.

The first hole doubles as a tutorial:

- place your ball in the illuminated tee zone;
- wait for your name + green `READY`;
- putt normally;
- the system handles the rest.

No long tutorial video should be required.

## 4. Hole interaction loop

### 4.1 Group arrival

Screen shows, in one glance:

```text
HOLE 06  •  RISK RIDGE
Aim: reach the cup in as few strokes as possible.
Optional: Precision Gate +25
Risk lane: +50 / Hazard -30

Players complete: 1 / 4
```

Instructions should fit on one screen and be understood in roughly five seconds.

### 4.2 Player arming

Any unfinished player's assigned ball enters the tee / start zone.

System checks:

1. ball belongs to the current session;
2. player has not already completed this hole;
3. no other player is currently active;
4. hole is healthy enough to score;
5. required start / lane safety conditions are satisfied.

Then:

```text
AMBER:  ZE HUI detected
GREEN:  ZE HUI — READY
```

A player can remove the ball before the first stroke to cancel arming without penalty.

### 4.3 Active play

After the first valid impact:

```text
ARMED -> PLAYING
```

The system records strokes automatically.

The player continues from wherever the ball stops; the ball does not return to the tee after every stroke.

During the run:

- bonus trigger -> short positive cue and score delta;
- hazard trigger -> short warning cue and score delta;
- uncertain trigger -> pending evidence, no duplicate score mutation;
- pickup / carry -> warning / recovery policy, not automatically a scored stroke unless the game rule explicitly says so.

### 4.4 Cup / completion

Recommended first-production evidence:

```text
position near cup
+ generic ball motion consistent with completion
+ physical cup sensor
=> CUP_CONFIRMED
```

When confirmed:

1. freeze that player's hole score;
2. show a <= 2 second result card;
3. release the hole for the next unfinished player;
4. keep the group leaderboard visible without blocking the next arming event.

### 4.5 Hole complete

When all players finish:

- show hole leaderboard for ~3-5 seconds;
- highlight one interesting result (best route / comeback / precision bonus);
- show a very obvious direction to the next hole;
- advance automatically.

## 5. 18-hole pacing model

The course should be designed as two complete 9-hole acts so the venue can sell either 9-hole or 18-hole sessions without changing the physical infrastructure.

### Act 1 — Learn and compete

- Holes 1-3: simple onboarding + obvious bonus mechanics.
- Holes 4-6: route choice / risk-reward.
- Holes 7-8: combination challenges.
- Hole 9: first-act finale and summary.

### Act 2 — Master and surprise

- Holes 10-12: new physical mechanics.
- Holes 13-16: more deliberate strategy / chained bonuses.
- Hole 17: high-skill setup.
- Hole 18: full finale, but still a normal complete hole — not an unexpected one-shot game terminator.

## 6. Launch game modes

### Mode A — Points Adventure (launch default)

Highest score wins.

Per-hole score consists of:

```text
completion score based on stroke count
+ skill bonuses
- hazards
+ optional route / combo modifiers
```

The exact score curve is configuration data, not firmware logic.

### Mode B — Classic (launch or shortly after)

Lowest total strokes wins.

Interactive features may still provide visual effects but do not need to affect the competitive score.

This mode makes the same hardware useful to traditional mini-golf customers.

### Later modes

- Team Battle.
- Family / reduced-penalty mode.
- Time Attack only after throughput and safety behavior are validated.
- Seasonal rule packs.

## 7. Scoring design

Do not clone another venue's point table. PuttTrack scoring should be its own configurable rule pack.

Initial Points Adventure example:

| Strokes | Completion points |
|---:|---:|
| 1 | 100 |
| 2 | 80 |
| 3 | 65 |
| 4 | 55 |
| 5 | 45 |
| 6 | 35 |
| 7 | 30 |
| 8+ | 25 |

Feature examples:

- Precision Gate: +20 to +30.
- Risk Route completion: +40 to +60.
- Small hazard: -10 to -20.
- Major hazard: -25 to -35.
- Optional combo: extra reward only after two independent skill conditions.

Product balancing rule: one lucky feature should not erase several holes of clearly better play.

## 8. Tie breaking

Suggested PuttTrack order:

1. total points;
2. more skill-bonus points;
3. fewer total strokes;
4. fewer hazard penalties;
5. lower active-play time.

This favors game performance before speed and avoids encouraging unsafe rushing.

## 9. Screen / HMI strategy

For an outdoor 18-hole venue, a giant indoor-style display at every hole may be unnecessarily expensive. The minimum good experience is:

- one weather-resistant, sunlight-readable tee display per hole;
- RGB / icon-ready tee lighting;
- local audio cue or nearby zone speaker;
- large leaderboard / welcome displays at reception, hole 9/10 transition and finish.

The tee display is authoritative for:

- current hole challenge;
- detected player;
- ready / wait / recover state;
- stroke count;
- short feature feedback;
- group progress;
- next-hole direction.

It is not an operator control panel during ordinary customer play.

## 10. Recovery UX

### Ball not recognised

Automatic flow:

1. `Hold ball in the tee zone`.
2. retry identity / ranging.
3. show expected ball color / number.
4. if a different assigned ball is detected, tell the players exactly whose ball it is.
5. only then offer `Need help?`.

### Duplicate / conflicting event

No score mutation until idempotency / confidence checks resolve it.

### Anchor degraded

Continue with a degraded positioning solution if confidence remains acceptable. UI does not expose RF details to players.

### Cup sensor disagreement

Hold `completion pending`, retry briefly and allow an operator evidence correction. Never silently award or remove a hole completion.

## 11. Queue and throughput

Default recommended social group: 2-4 players.

Larger event groups should be split into course groups rather than placing six or more people on every ordinary hole by default.

The edge system should maintain:

- group-at-hole state;
- hole occupancy;
- hole duration;
- downstream congestion;
- fault / assistance status.

Future dynamic dispatch can use actual telemetry rather than only fixed tee-time spacing.

When a group must wait, the screen may show short non-blocking social content / leaderboard information, but never require a mini-game to continue the round.

## 12. End-of-game experience

After the final player completes the final hole:

1. lock official round results;
2. show winner / team result;
3. show 2-4 memorable awards, e.g.:
   - Precision King/Queen;
   - Risk Taker;
   - Cleanest Round;
   - Biggest Comeback;
4. display QR for full result / replay summary;
5. optional email / account save;
6. optional loyalty / next-game offer;
7. return balls through a clear collection point.

Persistent account creation can happen here without blocking the initial game.

## 13. Gameplay architecture boundary

The player experience must remain independent from the ranging implementation.

```text
Sensors / CS / IMU
        -> evidence events
        -> gameplay engine
        -> scoring events
        -> presentation model
        -> tee screen / kiosk / mobile / admin
```

A future UWB or improved CS implementation must not require rewriting scoring or UX logic.

## 14. Launch acceptance criteria

Before calling the gameplay system venue-ready:

- assigned ball recognition succeeds without staff intervention in >= 99.5% of normal tee presentations;
- duplicate sensor packets cannot double-score;
- ordinary bonus/hazard feedback appears within a target <= 500 ms of confirmed event receipt;
- next player can arm while the previous player's completion animation is still finishing visually;
- no customer-facing workflow requires internet connectivity for local scoring;
- a failed anchor does not automatically destroy the round;
- cup completion has an explicit evidence/recovery path;
- all manual score adjustments create an audit event;
- a four-player group can understand Hole 1 without staff verbal training in normal conditions.

## Current product decision

Build the launch experience around **frictionless automatic play**, not around showcasing the underlying tracking technology.

The customer should remember the moment the course reacted to their shot, not the fact that Bluetooth Channel Sounding was running underneath it.
