# Canonical Data Model and Authority

## 1. Authority table

| Data | Authoritative owner | Producer | Persistence / retention | Replay |
|---|---|---|---|---|
| BALL_ID/device record | Device Registry | provisioning/service | long-term operational | registry revisions |
| Player / guest | Session Manager | check-in/cloud cache | session + optional account link | session events |
| Session/assignment | Session Manager | local Edge | authoritative local | append-only assignment events |
| Hole/course geometry | Course Configuration | release/operator | versioned long-term | config version/hash |
| Raw CS observation | source Anchor/Gateway record | Anchor | short production; research archive | raw reference/sequence |
| Range estimate | Localisation ingestion | Anchor/algorithm | short/incident/research | observation stream |
| IMU sample/window | Ball source record | Ball | research/incident; selective production | sequence + raw reference |
| Radio reception | Receiver source record | Gateway/Anchor | short/session/research | receiver boot/sequence + Ball packet key |
| Motion state | Motion module | Ball/Edge | session evidence | derived from raw/model version |
| Physical sensor event | Sensor/Gateway record | tee/cup/feature node | session/audit | event sequence |
| Position/trajectory | Localisation module | Edge | session summary + incident window | observations + algorithm version |
| Semantic evidence | Evidence Fusion | Edge | append-only authoritative evidence log | direct replay |
| Stroke/feature/cup | Gameplay event log | Gameplay Engine | long-term round audit | deterministic replay |
| Score/leaderboard | Gameplay projection | derived | materialized + completed result | rebuild from events |
| HMI notice | Presentation projection | Presentation Hub | ephemeral / selected audit | rebuild current state |
| Cloud result/history | Cloud after sync | Edge sync | cloud policy | local ID/revision |

## 2. Identity hierarchy

```text
DEVICE_ID
  -> BALL_ID / ANCHOR_ID / GATEWAY_ID / SENSOR_ID

SESSION_ID
  -> PLAYER_ID
  -> BALL_ASSIGNMENT_ID

VENUE_ID
  -> ZONE_ID
  -> HOLE_ID
  -> RF_CELL_ID
  -> FEATURE_ID
```

IDs are opaque and immutable. Human labels/colours/numbers are attributes, not primary keys.

## 3. Versioning

Every authoritative record references relevant versions:

- schema version;
- firmware/hardware revision;
- course/rule version;
- calibration version;
- localisation/evidence model version;
- security/key epoch where appropriate.

A completed round is reproducible with the versions active during that round.

## 4. Storage split

### Operational database

Relational state/events for devices, sessions, assignments, evidence, gameplay, audit, health and cloud queue.

### Research/raw store

Parquet/object files for high-rate measurements and camera data, organised with immutable manifests/checksums.

Suggested research partition:

```text
research/<study_id>/<run_id>/
  manifest.json
  cs_observations.parquet
  imu.parquet
  camera_track.parquet
  labels.parquet
  video/
  calibration/
  split_manifest.json
```

## 5. Privacy

- Ball/device IDs are not player personal data by themselves but assignment links can be.
- Keep guest identity minimal.
- Separate research consent/data from ordinary operations.
- Raw video retention is opt-in/limited and documented.
- Cloud sync sends only required data.

## 6. Research split discipline

Prevent leakage:

- split by physical run/session/day/ball, not random rows;
- keep all samples from one trajectory in one split;
- hold out at least one Anchor layout/environment condition;
- report performance on unseen ball orientations and people/obstructions;
- freeze split manifests before model tuning;
- preserve a final untouched venue test set.
