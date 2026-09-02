# Physical tee/cup ingress — no-CS prototype

**Status:** software path implemented and tested; physical sensors not yet selected
or installed

**Effective:** 2026-09-03

## Purpose

This is the hardware-neutral boundary between a future tee/cup sensor node and
the existing one-hole Gameplay Engine. It deliberately does not select an
ESP32, XIAO, field bus or sensor mechanism. A future node only needs to produce
the canonical `PhysicalSensorObservation` envelope; changing its MCU or
transport must not change scoring rules.

```text
switch / beam / presence mechanism
 -> sensor-node electrical debounce
 -> sensor.edge_observed
 -> ordering + health + identity + game-context policy
 -> observed / pending / rejected / confirmed EvidenceEvent
 -> unchanged Gameplay Engine
```

The implementation is in
`src/putttrack/evidence/physical_policy.py`. Local development ingress is
`POST /api/evidence/physical`.

## Required observation contract

The request body is the normal serialized `PhysicalSensorObservation`. At
minimum, the physical boundary requires:

```json
{
  "record_type": "physical_sensor_observation",
  "schema_version": "1.0",
  "event_id": "tee-boot17-1042",
  "event_type": "sensor.edge_observed",
  "source_device_id": "tee-H01",
  "source_boot_id": "boot-17",
  "sequence": 1042,
  "source_monotonic_ns": 3812000000,
  "edge_received_ns": 9213812000000,
  "trace_id": "trace-tee-1042",
  "hole_id": "H01",
  "ball_id": "ball-007",
  "sensor_id": "tee-presence-H01",
  "sensor_kind": "tee_presence",
  "transition": "occupied",
  "value": true,
  "health": "ok",
  "debounce_version": "tee-debounce-v1"
}
```

`event_id` identifies the logical edge and must be reused on retry. Sequence and
monotonic time restart only when `source_boot_id` changes. The node reports its
actual health and debounce implementation; Venue Edge does not pretend that a
raw bouncing GPIO edge is clean.

## V0 authority rules

### Tee

`tee_presence/occupied` becomes `tee.presented` only when:

- the event belongs to the current hole;
- sensor health is `ok` and `debounce_version` is present;
- source ordering has no duplicate sequence, gap, out-of-order packet or clock
  regression;
- `ball_id` is already assigned to the current session;
- the hole is not occupied by another Ball.

The tee mechanism alone does not normally know Ball identity. The `ball_id` in
this envelope therefore means that an upstream adapter has already correlated
the tee edge with the assigned BLE Ball. A plain switch with a guessed identity
must not call this endpoint as authoritative evidence.

`tee_presence/vacant` is retained as an observation but does not automatically
cancel READY. That avoids a race where the legitimate first stroke and the
ball-leaving-tee edge arrive in different orders.

### Cup

A single cup edge cannot finish a hole. The no-CS V0 policy requires:

1. `cup_entry/entered`; then
2. `cup_presence/occupied` within 3 seconds;
3. the same currently active Ball and hole throughout the sequence; and
4. the active player already in `PLAYING`, which means at least one independent
   `stroke.confirmed` has reached Gameplay.

Only that sequence emits `cup.confirmed`. The semantic event references both
raw physical event IDs. Presence without entry remains `pending`; an expired or
cross-Ball sequence is rejected. `vacant` clears any pending cup candidate.

For the first rig this implies two independently meaningful mechanical/optical
observations, for example an entry beam plus retained-ball occupancy. It does
not require two MCUs: one node may report two separately identified sensors.

This V0 two-stage mechanism is a prototype substitute for unavailable CS
proximity. Production ADR-009 still requires measured false-positive/negative
evidence and may add motion or spatial agreement before the operator guardrail
is removed.

## Response and failure behavior

The endpoint returns HTTP 202 because receipt is separate from authority:

```json
{
  "ok": true,
  "decision": {
    "status": "pending",
    "candidate_type": "cup.entry_candidate",
    "reason": "cup_presence_confirmation_required",
    "authority_granted": false
  },
  "state": {}
}
```

Statuses are:

- `accepted`: a confirmed semantic event was emitted and Gameplay processed it;
- `pending`: valid evidence is waiting for its independent partner;
- `observed`: valid state useful for audit but intentionally non-authoritative;
- `rejected`: invalid ordering, health, identity, transition or game context.

Exact event-ID retries return the cached decision and cannot double-score.
Malformed records are rejected at the typed contract boundary. Every decision
is appended to the local round audit when auditing is enabled.

## What is proven now

Automated tests prove:

- assigned tee presence reaches READY;
- foreign/missing Ball identity, unhealthy nodes and absent debounce version
  fail closed;
- a cup presence edge alone cannot complete a hole;
- entry plus timely occupancy completes a player only after an independently
  confirmed stroke;
- duplicate, gap and replay handling are deterministic and idempotent;
- the full path works through the HTTP ingress and the existing Gameplay Engine.

This is software evidence only. It does not prove a sensor mechanism outdoors,
Ball identity correlation, debounce timing, latency, wiring, power, weather
resistance or false-positive rate.

## Next physical gate

When the ball/core work is ready, build the smallest bench rig that can emit:

- tee occupied/vacant plus an independently correlated assigned Ball ID;
- cup entry plus cup occupancy/vacancy;
- stable boot ID, sequence, monotonic time, health and debounce version.

Capture raw switch/beam timing before fixing debounce constants. Then run
stuck-high, missing-node, bounce, retry, reordered-packet, wrong-Ball and
rapid-two-ball fault cases before mounting anything on a course. Gateway/MCU
selection follows the measured I/O, transport distance and power requirements.
