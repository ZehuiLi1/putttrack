# Gameplay Vertical Slice V1

## Status

This is a **local player-experience slice** built on top of the locked Gameplay
Engine and Evidence Foundation. The nRF54L15 Tag stationary telemetry and the
generic-motion candidate ingress are physically/software validated. The
hardware-neutral tee/cup observation policy and HTTP ingress are implemented
and software-tested; actual tee/cup mechanisms, Ball-to-tee correlation,
feature sensing and stroke confirmation remain physical gates.

The purpose is to prove that the player-facing flow can remain stable while real sensing work proceeds through Issue #1 and later localisation/evidence Issues.

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

The implementation was developed against the merged Evidence Foundation. Existing Gameplay authority was not redesigned.

## What remains unverified

- first-time-player usability with real people;
- sunlight readability, outdoor display and audio hardware;
- physical tee/cup mechanism and Ball-identity correlation;
- labelled impact/rolling/pickup distributions and calibrated confidence;
- real motion candidate + independent sensor to confirmed-event latency;
- physical Channel Sounding accuracy or update rate;
- one-hole 1,000-round soak.

Those remain in Issue #1 and Issue #12. This slice should not be used to mark physical UX or scoring-sensor gates as passed.
