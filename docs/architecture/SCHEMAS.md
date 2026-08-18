# Canonical Schema Examples

These examples define stable boundaries; implementation language and transport may differ.

## Range observation

```json
{
  "schema_version": "1.0",
  "event_id": "rng-...",
  "source_device_id": "anchor-A",
  "source_boot_id": "boot-...",
  "sequence": 123,
  "source_monotonic_ns": 1000000,
  "edge_received_ns": 1002200,
  "trace_id": "trace-...",
  "zone_id": "Z01",
  "hole_id": "H01",
  "rf_cell_id": "C01",
  "ball_id": "ball-001",
  "anchor_id": "anchor-A",
  "procedure_id": "cs-...",
  "antenna_path": 0,
  "distance_ifft_m": 2.31,
  "distance_phase_m": 2.28,
  "distance_rtt_m": 3.1,
  "rssi_dbm": -54,
  "quality": {},
  "calibration_version": "cal-7",
  "firmware_version": "1.2.0"
}
```

## Motion observation

```json
{
  "schema_version": "1.0",
  "event_id": "mot-...",
  "source_device_id": "ball-001",
  "source_boot_id": "boot-...",
  "sequence": 77,
  "source_monotonic_ns": 1000000,
  "ball_id": "ball-001",
  "motion_state": "ROLLING",
  "confidence": 0.94,
  "raw_window_ref": "research://run/imu/77",
  "battery": {"voltage_v": 2.91, "service_state": "ok"},
  "model_version": "motion-0.3"
}
```

## Track update

```json
{
  "schema_version": "1.0",
  "event_id": "trk-...",
  "source_monotonic_ns": 1000000,
  "edge_time_ns": 1002500,
  "ball_id": "ball-001",
  "hole_id": "H01",
  "position_m": [2.1, 4.2],
  "velocity_mps": [0.5, 0.1],
  "covariance": [[0.04, 0.0], [0.0, 0.06]],
  "confidence": 0.91,
  "track_state": "TRACKING",
  "anchors_recent": ["A", "B", "C", "D"],
  "algorithm_version": "range-ekf-0.1"
}
```

## Physical sensor observation

```json
{
  "schema_version": "1.0",
  "event_id": "sns-...",
  "source_device_id": "cup-H01",
  "source_boot_id": "boot-...",
  "sequence": 12,
  "source_monotonic_ns": 1000000,
  "hole_id": "H01",
  "sensor_id": "cup-H01",
  "transition": "ball_passage",
  "debounce_version": "cup-2",
  "health": "ok"
}
```

## Confirmed semantic evidence

```json
{
  "schema_version": "1.0",
  "event_id": "evd-...",
  "event_type": "cup.confirmed",
  "edge_time_ns": 1005000,
  "trace_id": "trace-...",
  "session_id": "session-1",
  "player_id": "player-1",
  "ball_id": "ball-001",
  "hole_id": "H01",
  "confidence": 0.999,
  "fusion_policy_version": "cup-policy-1",
  "raw_evidence_refs": ["trk-...", "mot-...", "sns-..."],
  "metadata": {}
}
```

## Operator adjustment

```json
{
  "schema_version": "1.0",
  "event_id": "op-...",
  "event_type": "operator.adjustment",
  "session_id": "session-1",
  "player_id": "player-1",
  "ball_id": "ball-001",
  "hole_id": "H01",
  "actor_id": "staff-7",
  "reason": "cup sensor failed; video and physical inspection confirmed completion",
  "points_delta": 0,
  "stroke_delta": 0,
  "command": "confirm_cup",
  "raw_evidence_refs": [],
  "wall_time": "2026-08-18T00:00:00Z"
}
```

## Compatibility rules

- additive optional fields are backward-compatible within a major schema version;
- meaning/unit changes require a new schema version;
- unknown mandatory version is rejected/quarantined;
- every persisted event retains original payload and parsed normalized form;
- field devices and Gateways negotiate capability/config before active scheduling.
