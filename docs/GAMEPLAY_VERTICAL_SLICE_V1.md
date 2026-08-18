# Gameplay Vertical Slice V1

## Status

This is a **local/simulated player-experience slice** built on top of the locked Gameplay Engine and Evidence Foundation. It does not claim that Channel Sounding, IMU, tee sensors or cup sensors have been physically validated.

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

The implementation was developed against the merged Evidence Foundation. Existing Gameplay authority was not redesigned.

## What remains unverified

- first-time-player usability with real people;
- sunlight readability, outdoor display and audio hardware;
- physical tee/cup integration;
- real sensing-to-EvidenceEvent latency;
- physical Channel Sounding accuracy or update rate;
- one-hole 1,000-round soak.

Those remain in Issue #1 and Issue #12. This slice should not be used to mark physical UX or scoring-sensor gates as passed.
