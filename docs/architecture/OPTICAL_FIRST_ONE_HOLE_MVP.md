# Optical-First One-Hole MVP

**Status:** Current build target  
**Date:** 2026-08-25

## 1. Objective

Build one complete interactive mini-golf hole that works with an ordinary ball and demonstrates automatic sensing, route recognition, rewards/penalties, cup confirmation and score feedback before the smart-ball programme is complete.

The first physical target is a static **Challenge Roulette** hole: one tee, a curved approach, a fixed LED roulette/challenge hub, four route/zone outcomes, one final green and one final cup. The centre feature is not motorised in V0.

## 2. V0 gameplay flow

```text
BALL ON TEE
    |
    v
READY
    |
tee clears + launch beam confirms passage
    |
    v
SHOT STARTED
    |
    +----> SAFE / ZONE A
    +----> BONUS / ZONE B
    +----> JACKPOT / ZONE C
    +----> HAZARD / ZONE D
    |
    v
FINAL APPROACH
    |
upper cup beam -> lower cup beam
    |
    v
HOLE COMPLETE
```

The route labels are configuration, not firmware constants. A simpler first build may label the four middle inputs `ZONE_A..ZONE_D` and add reward semantics later.

## 3. Eight-DI input map

| DI | Physical location | Semantic use |
|---|---|---|
| DI1 | Tee ball position | `tee.presented` / `BALL_PRESENT` |
| DI2 | 100–200 mm in front of tee | launch confirmation; prevents a lifted ball being scored as a shot |
| DI3 | Route/zone A | safe/zone event |
| DI4 | Route/zone B | bonus/zone event |
| DI5 | Route/zone C | jackpot/zone event |
| DI6 | Route/zone D | hazard/final-approach event |
| DI7 | Upper cup/return chute | cup-entry candidate |
| DI8 | Lower cup/return chute | confirms downward cup passage after DI7 |

The first build intentionally uses exactly eight digital inputs so the existing Waveshare ESP32-S3 PoE/Ethernet 8DI/8DO controller can be used without an I/O expander.

## 4. Sensor rules

Use industrial modulated through-beam photoelectric sensors for the outdoor course, preferably:

- 10–30 V DC / nominal 24 V installation;
- NPN output compatible with the isolated DI interface;
- IP65 minimum, IP67 where exposed;
- fast response suitable for a golf ball crossing the beam;
- transmitter/receiver physically recessed behind protected optical windows in the course sidewalls.

Do not make human-veto beams mandatory in the first build. First use:

1. state-machine context;
2. pulse duration;
3. legal event ordering;
4. duplicate suppression.

Add high veto beams only where real field data shows a meaningful false-trigger problem.

## 5. Tee logic

DI1 alone does not confirm a stroke.

```text
DI1 blocked        -> BALL_PRESENT / READY candidate
DI1 becomes clear  -> ball removed or launched
DI2 then triggers  -> BALL_LAUNCHED / shot candidate
DI1 clears without DI2 -> cancel / pickup, not a stroke
```

V0 may rely on active-player order for stroke ownership. V1 smart-ball IMU can later strengthen stroke confirmation without changing the optical interface.

## 6. Route/zone logic

DI3–DI6 are discrete spatial evidence, not continuous localisation.

The controller/server keeps a coarse state such as:

```text
hole_id = 01
active_player = P2
current_zone = BONUS
shot_state = PLAYING
```

The first valid route event after launch may lock the route result for that shot so repeated beam interruptions cannot repeatedly award points.

Suggested initial reward configuration:

| Route | Example result |
|---|---:|
| SAFE | 0 |
| BONUS | +30 or +50 |
| JACKPOT | +80 / x2 mode |
| HAZARD | -20 or -30 |

Reward values live in course/game configuration on Venue Edge.

## 7. Cup logic

Cup completion requires ordered physical evidence:

```text
DI7 upper beam
   -> DI8 lower beam
   -> within configured timing window
   -> cup.confirmed
```

DI8 -> DI7 is not normal entry. A single beam interruption is not sufficient for authoritative completion.

A later Hole NFC read zone may identify the smart ball in the return chute, but NFC is not required for V0 cup detection.

## 8. Controller

### V0 controller

Use the existing **Waveshare ESP32-S3 PoE/Ethernet 8DI/8DO** unit.

Responsibilities:

- read/debounce eight DI channels;
- timestamp edges/events;
- apply simple ordered-pattern rules;
- detect sensor faults where possible;
- publish semantic events to Venue Edge;
- drive simple local feedback through DO where useful;
- buffer/retry short network interruptions.

It does not own authoritative score.

### Output allocation example

| DO | V0 use |
|---|---|
| DO1 | Tee READY cue |
| DO2 | Safe feedback trigger |
| DO3 | Bonus feedback trigger |
| DO4 | Jackpot feedback trigger |
| DO5 | Hazard feedback trigger |
| DO6 | Cup/finish feedback |
| DO7 | audio/effect trigger |
| DO8 | spare |

Complex RGB/DMX/Art-Net lighting should later move to a dedicated lighting controller. The hole controller should send semantic triggers rather than directly encode long animations.

## 9. Networking and expansion

V0:

```text
24 V optical sensors
       |
       v
Waveshare 8DI/8DO
       |
Ethernet / PoE
       |
       v
Local Venue Edge
```

When more than eight inputs are needed:

```text
Waveshare controller
       |
protected RS-485 / Modbus RTU
       |
remote 8/16-DI or DI/DO module(s)
```

RS-485 is the default expansion path for simple field I/O. CAN remains available for future intelligent motor/actuator nodes where asynchronous arbitration is useful.

## 10. Venue Edge event model

The field controller sends semantic evidence, for example:

```text
tee.presented
tee.launch_confirmed
zone.entered
feature.confirmed
cup.entry_candidate
cup.confirmed
sensor.fault
```

Events include at minimum:

- `event_id`;
- source/controller ID;
- sensor ID;
- timestamp;
- hole ID;
- active session/player where known;
- event type;
- sequence number;
- payload/diagnostics.

The Gameplay Engine remains deterministic and idempotent. Duplicate sensor packets must not duplicate score mutations.

## 11. V0 identity rule

Ordinary balls have no electronic identity.

For a normal single-lane hole, V0 therefore assumes one active player/ball at a time. Accepted optical events belong to the active player/session. This is a deliberate MVP rule, not a permanent limitation.

## 12. Upgrade path

### V1 smart ball

Add nRF54L15 smart ball capabilities without replacing optical sensors:

- NFC/NFCT for tee wake and deterministic Ball ID/session association;
- BLE for Ball ID/health/battery/state transport;
- IMU for impact, rolling, stationary and pickup states;
- optional Hole NFC identity read in the return path.

### V2 Channel Sounding

Add CS only where it creates value:

- continuous trajectory UI;
- shot-path analytics;
- multi-ball event association;
- lost-ball/coarse-position assistance;
- advanced position-based game mechanics.

Core route/cup scoring continues to work if CS is disabled.

## 13. First acceptance test

A successful one-hole demo should let a user with a normal ball:

1. place the ball on the tee and receive READY feedback;
2. strike the ball and obtain a launch event rather than a pickup event;
3. enter one of the four configured zones/routes;
4. receive immediate matching visual/audio reward or penalty;
5. enter the cup and produce the ordered DI7 -> DI8 confirmation;
6. see the correct score/state on the local UI;
7. replay the event log and reproduce the same result.

Only after this vertical slice is stable should additional optical channels, smart-ball identity, IMU or CS become dependencies for the next stage.
