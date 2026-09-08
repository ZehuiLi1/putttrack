# Gameplay Vertical Slice V1

## Status

This is a **local player-experience slice** built on top of the locked Gameplay
Engine and Evidence Foundation. The nRF54L15 Tag stationary telemetry and the
generic-motion candidate ingress are physically/software validated. The
hardware-neutral tee/cup observation policy and HTTP ingress are implemented
and software-tested.

**As of 2026-09-09, the prototype hardware required for the first real vertical
slice is prepared: NFC Tee + Smart Ball + IMU + optical Cup.** The project has
therefore moved from hardware preparation into physical system integration.
This is not yet a Physical pass: Ball-to-tee correlation, physical stroke
confirmation, real Cup completion and whole-hole automatic play still require
integrated evidence.

The purpose is to prove that the player-facing flow can remain stable while real sensing work proceeds through Issue #1 and later localisation/evidence Issues.

## Current physical milestone

The immediate V1 path is deliberately restricted to the smallest automatic hole:

```text
NFC Tee
  -> Ball identity / presence
  -> BLE session + hole ARM
  -> Ball ACK
  -> READY
  -> IMU-based stroke confirmation
  -> stroke count
  -> optical Cup confirmation
  -> HOLE COMPLETE
```

For this milestone, Channel Sounding, spatial localisation, bonus/hazard zones,
custom production Ball PCB and multi-hole scaling are explicitly outside the
critical path. They should only be reopened after this simple one-hole chain has
been demonstrated reliably under real play.

## Player flow

```text
/checkin
  -> guest display names
  -> optional booking code / account IDs
  -> server-side Ball assignment
  -> human-readable Ball label
  -> hole screen
  -> Ball DETECTED / CHECKING (amber)
  -> authoritative tee.presented
  -> READY (green)
  -> stroke / feature / pickup / cup semantic events
  -> deterministic Gameplay Engine
  -> local leaderboard and non-blocking SSE feedback
```

Normal player play remains zero-touch. The hole page contains developer simulation controls under a collapsed `Simulation controls` section only so the UI can be exercised before physical evidence is available.

## Authority boundary

The new venue layer does **not** teach Gameplay Engine about Bluetooth Channel Sounding, Nordic hardware, UWB or cameras.

`LocalRoundRuntime.process_evidence()` uses the existing sensor-independent `EvidenceToGameplayAdapter`:

```text
CS / IMU / physical sensor / UWB / camera (future)
        -> EvidenceEvent
        -> EvidenceToGameplayAdapter
        -> existing GameplayEvent
        -> GameplayEngine
        -> presentation
```

The simulated HTTP endpoints generate the same Gameplay events only for development.

The no-CS motion path now ends one layer earlier by design:

```text
physical Tag window
 -> canonical MotionObservation
 -> NoCsMotionCandidatePolicy
 -> motion.stationary / stroke.candidate / pickup.candidate / ...
 -> observed, pending or rejected + operational audit
 -> no score mutation
```

An impact observation can therefore reach the live one-hole runtime and screen
as `evidence_pending`, but this policy is structurally unable to emit
`stroke.confirmed`, `feature.confirmed` or `cup.confirmed`. Independent evidence
and a later measured fusion policy are required.

The physical-input path is separately fail-closed:

```text
debounced tee edge + assigned BLE Ball context
 -> tee.presented -> READY

cup entry edge + cup occupancy edge within 3 s
 + same active PLAYING Ball (independent stroke already confirmed)
 -> cup.confirmed
```

One cup edge, a foreign Ball, unhealthy sensor, undeclared debounce, sequence
gap or out-of-order packet cannot mutate Gameplay state.

## Components

- `src/putttrack/venue/course.py`
  - strict JSON course/rule loader;
  - duplicate hole/feature validation;
  - configurable score curve and feature rules.
- `src/putttrack/venue/session.py`
  - guest-first check-in;
  - booking/session lookup;
  - optional account linking;
  - unique smart-ball allocation;
  - public human-readable Ball labels.
- `src/putttrack/venue/runtime.py`
  - existing Gameplay Engine wrapper;
  - non-authoritative DETECTED/CHECKING presentation cue;
  - READY/PLAYING presentation state;
  - in-process presentation broker;
  - append-only local operational audit.
- `src/putttrack/evidence/motion_policy.py`
  - generic state-to-candidate routing;
  - active/assigned Ball isolation;
  - fail-closed no-score authority boundary;
  - idempotent runtime decision handling.
- `src/putttrack/evidence/physical_policy.py`
  - tee identity/context authority gate;
  - two-stage cup confirmation window;
  - node health/debounce and source-order enforcement;
  - deterministic semantic IDs and idempotent decisions.
- `src/putttrack/venue/web.py`
  - standard-library local HTTP server;
  - tee screen and check-in pages;
  - SSE presentation feed;
  - simulated semantic-event endpoints;
  - audited operator-adjustment endpoint.
- `configs/course/demo_one_hole.json`
  - first configurable Points Adventure demo hole.
- `tools/run_hole_demo.py`
  - local launcher.

## Run

```bash
PYTHONPATH=src python tools/run_hole_demo.py
```

Then open:

```text
http://127.0.0.1:8080/checkin
```

The operational audit is written below `runs/venue_demo/<session_id>/round_audit.jsonl` and is local/WAN-independent.

## HTTP surface

Player-facing/read paths:

- `GET /`
- `GET /checkin`
- `GET /api/state`
- `GET /api/session?code=<booking-or-session-id>`
- `GET /events` (SSE; browser reconnects using `Last-Event-ID`)

Development/simulation paths:

- `POST /api/checkin`
- `POST /api/sim/tee`
- `POST /api/sim/stroke`
- `POST /api/sim/feature`
- `POST /api/sim/cup`
- `POST /api/sim/pickup`
- `POST /api/operator/adjust`

Canonical non-authoritative evidence ingress:

- `POST /api/evidence/motion` — accepts a typed `motion_observation`, returns
  HTTP 202 with an observed/pending/rejected policy decision.

Canonical physical evidence ingress:

- `POST /api/evidence/physical` — accepts a typed
  `physical_sensor_observation`, returns HTTP 202 with an
  accepted/pending/observed/rejected policy decision. `accepted` means the
  resulting semantic event was processed by Gameplay.

The `/api/sim/*` surface is **not** a production sensor API; it is an evidence simulator for this slice.

## Tests

`tests/test_venue_vertical_slice.py` covers:

- course-rule validation;
- guest-first check-in;
- Ball capacity and unique assignment;
- booking lookup;
- flexible player order;
- DETECTED/CHECKING -> READY presentation;
- foreign Ball self-recovery event;
- duplicate Gameplay event idempotency;
- local audit persistence;
- complete HTTP flow from check-in through stroke, feature and cup.
- canonical motion HTTP ingress;
- impact remains pending with zero stroke mutation;
- duplicate, foreign and inactive-Ball motion isolation.
- physical tee to READY and two-stage cup to player completion;
- physical ingress over HTTP;
- unhealthy, missing-debounce, wrong-Ball, sequence-gap, duplicate and expired
  cup sequences fail closed;
- identical physical input sequences replay to identical decisions.

`tools/soak_no_cs_hole.py` extends these checks across fresh sessions. The
2026-09-03 baseline completed 1,000 four-player rounds with 20,000 injected
faults and zero score/state invariant failures. See
[`verification/NO_CS_ONE_HOLE_SOAK.md`](verification/NO_CS_ONE_HOLE_SOAK.md).

The implementation was developed against the merged Evidence Foundation. Existing Gameplay authority was not redesigned.

## Next physical validation sequence

1. Connect the real NFC Tee, Smart Ball/IMU and optical Cup to the canonical
   evidence path without changing Gameplay authority.
2. Run 20 repeated bench cycles:
   `Ball present -> READY -> stroke -> optional second stroke -> Cup -> complete -> reset`.
3. Fix only integration failures exposed by those cycles: duplicate events,
   stale sessions, wrong-Ball acceptance, missing reset, event ordering or
   excessive latency.
4. Move the same setup onto one real mini-golf lane and test normal/gentle/hard
   putts, wall/rail collisions, repeated collisions, pickup/replacement and real
   Cup entry.
5. Preserve one common timestamped log across Tee, Ball/IMU and Cup, including
   session ID, hole ID, Ball ID, event ID/sequence, stroke count and latency.
   Preserve raw IMU windows around disputed events.
6. Run 30 consecutive real automatic rounds with no manual score intervention.

## Physical acceptance targets

These are next-test engineering targets, not measured claims:

- Tee: >=49/50 correct installed Ball presentations, zero wrong-Ball or duplicate-session acceptance;
- Stroke: >=98/100 real putts correctly counted in the first integrated pass,
  while rail/wall collisions and pickup/replacement do not create extra strokes;
- Cup: target 100/100 real entries detected in the formal Cup test;
- Whole hole: 30 consecutive real rounds from Tee presentation through
  `HOLE_COMPLETE` without manual score intervention.

Passing this gate upgrades PuttTrack from a set of validated components plus a
software vertical slice to a **working physical one-hole system prototype**.

## What remains unverified

- first-time-player usability with real people;
- sunlight readability, outdoor display and audio hardware;
- integrated physical Ball-to-tee correlation under real installed conditions;
- real stroke confirmation accuracy across putts, collisions and pickup/replacement;
- real Cup completion reliability and end-to-end latency;
- labelled impact/rolling/pickup distributions and calibrated confidence;
- physical Channel Sounding accuracy or update rate;
- physical one-hole soak.

The last item means a **physical** mechanism/human-play soak. The software-only
1,000-round fault-injection gate has passed.

Those remain in Issue #1 and Issue #12. This slice should not be used to mark physical UX or scoring-sensor gates as passed until the real one-hole acceptance sequence above is completed.
