# Player and Operator HMI Architecture

## 1. Player journey

```text
Check-in -> Ball assignment -> Course direction
 -> Hole AVAILABLE
 -> ball presented
 -> DETECTED / CHECKING
 -> READY
 -> PLAYING
 -> short event feedback
 -> player COMPLETE
 -> next player / next hole
```

Normal play is zero-touch after check-in.

## 2. HMI surfaces

### Check-in / assignment

- scan booking QR/code or create local guest session;
- display name only for guest play;
- optional account/loyalty linking;
- show player name + ball colour/number/marker;
- confirm all assigned balls before course entry.

### Hole display

One-glance content:

- hole number/title;
- instruction and risk/reward feature summary;
- current active/ready player;
- group completion count;
- live score/ranking at a suitable level;
- fault/retry and next-hole direction.

### Tee cue stack

Never rely on colour only:

| State | Light | Text/icon | Audio |
|---|---|---|---|
| Available | neutral/white | Place your ball | none |
| Detected/checking | amber | Player name + checking | optional soft cue |
| Ready | green | Player name + READY | short distinct chime |
| Playing | active accent | strokes/live status | event cues only |
| Fault/retry | red/amber pattern | specific recovery action | attention cue |

### Feedback

- bonus/hazard/stroke: compact toast/animation, target <=500 ms after confirmed evidence;
- cup: <=2 s player result card while system can prepare next legal arming;
- group hole summary: approximately 3–5 s, skippable/non-blocking internally;
- final result: champion plus skill/comeback/precision highlights and optional QR.

## 3. Recovery language

Examples:

- Wrong ball: `Orange 12 belongs to Sam. Your ball is Blue 07.`
- Recognition retry: `Keep the ball in the start circle while we check it.`
- Hole degraded: `This feature is temporarily unavailable. Normal strokes and cup scoring still work.`
- Operator required: show a clear waiting state, not a numeric error code.

## 4. Outdoor hardware requirements

- sunlight-readable brightness and anti-glare cover;
- IP65 or better, UV/heat suitable for Brisbane;
- vandal-resistant mounting and protected connectors;
- night dimming and controlled audio level;
- readable at group standing distance;
- accessible text/icon size and no colour-only dependency;
- local indicator/audio remains useful if screen fails.

Hole displays should use PoE Ethernet where practical. They subscribe to presentation state and cannot write gameplay state directly.

## 5. Operator HMI

Separate from player UI:

- venue/zone/hole health map;
- ball battery/assignment/service status;
- pending/uncertain evidence queue;
- event replay and raw evidence links;
- explicit pause/resume/quarantine;
- score correction with reason and actor;
- device firmware/config rollout;
- replacement/calibration workflow.

Operator actions become signed/audited domain commands/events.

## 6. Presentation contract

Presentation receives versioned snapshots and notices:

- session/hole state;
- active player/ball alias;
- READY/checking/fault state;
- score/ranking projection;
- short event notices;
- next-hole routing;
- health/degraded flags.

A screen refresh/reconnect reconstructs state from the current projection and does not replay score mutations.
