# One-Hole Player UX Dry Run

## Purpose

Validate the locked player journey before real RF hardware is available. This is a **human-factors dry run**, not a sensing-performance test.

Use the merged one-hole local application with ordinary balls and developer-triggered semantic events. Do not coach participants unless the protocol says to intervene.

## Setup

- one laptop/monitor running `PYTHONPATH=src python tools/run_hole_demo.py`;
- four visibly different ordinary balls or labelled substitutes;
- one mocked Tee/Start area;
- one mocked Cup area;
- optional speaker for proposed READY/bonus cues;
- one observer who does not explain the flow initially;
- printed observer sheet / `observations.csv`.

## Participants

Recommended first pass:

- 4 people who have not seen the PuttTrack design;
- preferably mixed familiarity with mini golf;
- no account creation requirement;
- use display names only.

This is not formal usability research requiring statistical claims. It is an engineering dry run to find obvious friction before hardware integration.

## Script

### 1. Check-in

Tell the group only:

> “You are here to play this mini-golf hole. Start when you think you are ready.”

Observe whether they can:

- find the check-in screen;
- enter names;
- understand assigned ball colour/number;
- identify which physical ball belongs to each person.

Do not explain every UI element.

### 2. Tee presentation

Let any unfinished player choose to go first.

Observer triggers the simulated tee event when that player's physical ball reaches the mocked Tee Zone.

Check whether participants understand:

```text
neutral / available
-> DETECTED / CHECKING
-> READY
```

Record:

- whether READY is visually obvious;
- whether they wait for READY without staff instruction;
- whether the non-colour cue/text is sufficient;
- whether sound would help.

### 3. Play

For each stroke, operator triggers the simulated confirmed semantic event.

Optional feature triggers:

- Precision Gate +25;
- Hazard/negative feature if configured.

Observe whether feedback is noticed without interrupting play.

### 4. Cup / next player

Trigger cup confirmation when the ball reaches the mocked Cup.

Observe:

- whether completion is clear;
- whether celebration/score feedback is too long;
- whether the next player naturally presents their ball;
- whether participants understand that fixed turn order is not required.

### 5. Wrong-ball recovery

At least once, intentionally have a participant present another player's assigned ball.

Record whether the message tells them exactly:

- whose ball was detected;
- which ball they should use;
- what to do next;
- whether staff help is needed.

### 6. Simulated fault

Optionally simulate one ambiguous/unavailable state and ask participants what they think the system expects next.

Do not mutate score from uncertain evidence.

## Metrics to record

For each participant/group:

- time from arrival to assigned balls;
- number of staff explanations before first READY;
- wrong-ball recovery time;
- number of screen touches attempted during normal play;
- whether READY was understood first time;
- whether bonus/hazard feedback was noticed;
- whether next-player flow was obvious;
- any phrase/icon/state that caused hesitation;
- total staff interventions.

Primary qualitative gate:

> Four first-time players can begin Hole 1 without verbal staff training beyond the initial neutral instruction.

## Observer rules

- do not rescue participants immediately;
- record first confusion before explaining;
- distinguish UI confusion from missing physical hardware;
- do not interpret simulated event latency as RF latency;
- do not mark Issue #3 complete until physical Tee/Cup and outdoor HMI gates also pass.

## After each group

Ask only a few short questions:

1. How did you know it was your turn / safe to hit?
2. Was anything unclear about your assigned ball?
3. Did the score/bonus feedback interrupt you or help you?
4. If the wrong ball was used, did the recovery instruction make sense?
5. What would you change before playing another hole?

## Output

Store observations outside production logs, then summarize actionable findings in Issue #3. Avoid collecting unnecessary personal information.
