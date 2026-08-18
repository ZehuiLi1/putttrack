# Event and Evidence Contract

## 1. Pipeline

```text
Raw Observation
 -> Validated Measurement
 -> Evidence Candidate
 -> Confirmed Semantic Evidence
 -> Gameplay Event
 -> Score/State Mutation
 -> Presentation Notice
```

Only the Gameplay Engine mutates authoritative game state. Upstream layers cannot emit point values as truth.

## 2. Common envelope

Every event/observation uses:

```json
{
  "schema_version": "1.0",
  "event_id": "uuid-or-deterministic-idempotency-key",
  "event_type": "namespace.name",
  "source_device_id": "opaque-id",
  "source_boot_id": "opaque-id",
  "sequence": 1,
  "source_monotonic_ns": 0,
  "edge_received_ns": 0,
  "wall_time": "2026-08-18T00:00:00Z",
  "trace_id": "opaque-id",
  "correlation_id": "session-or-procedure-id",
  "venue_id": "venue-1",
  "zone_id": "Z01",
  "hole_id": "H01",
  "ball_id": "ball-001",
  "confidence": 0.0,
  "raw_evidence_refs": [],
  "payload": {}
}
```

Required fields vary by type, but identity, sequence, timestamp, schema and traceability are mandatory for authoritative evidence.

## 3. Measurement events

### `cs.range_observed`

Payload includes Anchor coordinates/version, estimator values, antenna path, channel/config digest, RSSI, quality flags, calibration version and procedure IDs.

### `ball.motion_observed`

Generic state plus optional raw-window reference; no hole-specific score meaning.

### `sensor.edge_observed`

Tee/cup/feature node state transition with debounce/config version and health.

### `track.updated`

Edge-derived position/velocity/covariance/confidence, Anchors used and algorithm version.

## 4. Evidence candidate/confirmation

Candidates are not score-authoritative. Fusion may confirm, reject, expire or route to review.

Examples:

- `tee.presentation_candidate`
- `stroke.candidate`
- `feature.crossing_candidate`
- `cup.entry_candidate`
- `pickup.candidate`

Confirmed semantic events consumed by Gameplay Engine:

- `tee.presented`
- `tee.cancelled`
- `stroke.confirmed`
- `feature.confirmed`
- `cup.confirmed`
- `pickup.detected`
- `operator.adjustment`

Recommended additions:

- `evidence.pending`
- `evidence.rejected`
- `hole.degraded`
- `ball.low_battery`
- `device.quarantined`
- `session.paused`
- `session.resumed`

These operational events do not automatically change score unless Gameplay policy explicitly handles them.

## 5. Idempotency

- Globally unique `event_id` per authoritative event.
- Deterministic IDs may be derived from source device/boot/sequence/type when retransmission is expected.
- Gateway/Edge replay preserves IDs.
- Gameplay Engine rejects already-seen event IDs.
- Feature rules also enforce logical trigger limits, protecting against two distinct packets representing the same physical one-shot feature.

## 6. Late and out-of-order policy

### Measurements

May be inserted into a short bounded reorder window. Dynamic tracker can process source-time observations while they remain inside the allowed lag; later data is stored for audit but does not rewrite a completed score silently.

### Semantic evidence

- Before a player's hole completion: may be accepted according to event-state rules.
- After completion: route to review unless explicitly defined as a safe correction event.
- After round finalization: only audited operator/reconciliation commands may change the official result.

## 7. Retry and replay

- Transport retry never creates a new logical event ID.
- Gateway replay declares replay range and original source times.
- Edge acknowledgement is explicit and durable.
- Cloud sync uses separate idempotency keys and does not replay local gameplay commands back into an active round.

## 8. Evidence policy examples

### Tee

```text
assigned authenticated ball
+ tee presence true
+ hole available
+ local cell confidence
=> tee.presented
```

### Stroke

```text
generic impact
+ valid post-impact displacement/rolling evidence
+ active READY/PLAYING player
=> stroke.confirmed
```

### Narrow bonus gate

```text
physical beam/switch edge
+ active ball trajectory/time agreement
=> feature.confirmed
```

### Cup

```text
physical cup event
+ cup-zone proximity
+ compatible drop/impact/rest evidence
=> cup.confirmed
```

If independent evidence disagrees, emit `evidence.pending` and invoke retry/review policy rather than score.

## 9. Audit requirements

Every score mutation records:

- semantic event ID;
- source/fusion policy version;
- course/rule version;
- actor for operator actions;
- raw evidence references;
- before/after state digest;
- timestamp and trace.

The result must be reconstructable without presentation logs.
