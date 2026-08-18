# Venue Edge Architecture

## 1. Decision

The Venue Edge is the authoritative runtime for local sessions, localisation, evidence, gameplay, scoring, presentation and audit. Production V1 uses a **modular monolith deployed as a small number of supervised processes**, not an early fleet of microservices.

## 2. Why modular monolith

The dominant risks are state consistency, radio scheduling, event ordering, recovery and field diagnostics—not raw CPU scale. A single venue with at most one high-rate active ball per ordinary hole can be supported by a modern mini PC without distributed-service complexity.

Benefits:

- one transactional authority for game state;
- simple local deployment/recovery;
- low latency between localisation, evidence and gameplay;
- clear module boundaries that can be split later;
- easier replay and audit.

## 3. Recommended process layout

```text
putttrack-io
  Gateway sessions, device ingress, scheduling commands, protocol adapters

putttrack-core
  Registry, assignments, course config, calibration, localisation,
  tracking, motion, evidence fusion, gameplay, scoring and audit

putttrack-web
  Check-in, hole screens, WebSocket/SSE, operator/admin API

PostgreSQL (pilot/production)
Raw Research Recorder (optional process)
Cloud Sync worker
```

For the lab, the same modules may run in one Python process with SQLite/WAL.

## 4. Logical modules

### Device Registry

Authoritative opaque IDs, hardware/firmware versions, credentials, installation mapping, calibration and service state.

### Session and Assignment

Owns `BALL_ID -> PLAYER_ID -> SESSION_ID`, course/product selection and current group/hole state.

### Course Configuration

Versioned geometry, feature definitions, score curves, HMI content and sensor-confirmation policies. Rules never live in ball firmware.

### Measurement Ingestion

Validates schemas, device identity, sequence, timestamps, calibration version and quality metadata. Stores raw/evidence references.

### Localisation and Tracking

Asynchronous range-domain EKF, snapshot robust WLS for initialisation/reacquisition, track confidence and zone/handoff state.

### Motion Ingestion

Receives generic motion states and selected raw windows. Does not make hole-specific production score decisions.

### Evidence Fusion

Converts measurement candidates into semantic events using versioned policies and raw-evidence references.

### Gameplay Engine

Existing deterministic/idempotent authority for hole/session/scoring transitions.

### Presentation Hub

Publishes derived UI state and short notices. It cannot mutate score.

### Operator Console

Health, pending evidence, replay and explicit audited correction/quarantine/update actions.

### Update Manager

Release compatibility, staged rollout, maintenance windows, rollback and device quarantine.

### Cloud Sync

Outbound idempotent queue and inbound non-authoritative booking/config/release data.

## 5. Persistence model

### Operational store

Production recommendation: PostgreSQL on the Edge server.

Store:

- devices and calibration versions;
- sessions/players/assignments;
- course/rule versions;
- append-only semantic/gameplay events;
- materialized current state;
- score/audit/operator actions;
- health summaries and sync queue.

### Raw/research store

Use Parquet/object files organised by experiment/venue/date with metadata rows in the operational database:

- raw CS/IQ/quality where retained;
- range observations;
- raw IMU windows;
- camera trajectories/video references;
- model/training split manifests.

### Retention

- gameplay/audit: venue/legal/business retention policy;
- raw production measurements: short rolling window unless attached to an incident;
- research data: immutable dataset versions with checksums;
- camera: opt-in/limited retention consistent with privacy policy.

## 6. Event sourcing boundary

Do not event-source every radio sample. Use:

- append-only immutable records for semantic evidence/gameplay/operator/cloud sync;
- time-series/raw files for high-rate measurements;
- materialized state for current UI and operations.

Every authoritative score must be reproducible from semantic events and course-rule version.

## 7. Local availability

- systemd/containers supervise the small process set;
- UPS supports Edge and core network;
- restart restores from committed event/store state;
- Gateway replay is idempotent;
- health service detects stale devices/processes;
- warm spare server/image and tested restore procedure are preferred over an early HA cluster.

## 8. Performance budget

Initial engineering budget:

- confirmed evidence to HMI: <=500 ms;
- local observation ingestion: bounded queue with <50% steady-state resource use at venue-load simulation;
- localisation track target: >=5 Hz for each active ball, higher only if justified;
- Edge CPU/memory steady state <60% under 80-ball simulation;
- database fsync/commit policy must not lose authoritative events on normal restart.

## 9. API boundaries

- Gateway protocol: authenticated observations, sensor events, health and schedule commands.
- Internal module contracts: typed/versioned domain objects, not ad-hoc dicts.
- HMI: WebSocket/SSE snapshots/notices plus REST for check-in/operator actions.
- Cloud: idempotent outbound records with local IDs/version and explicit acknowledgement.

## 10. Future split triggers

Split a module into an independent service only if one of these is demonstrated:

- independent scaling/resource isolation;
- fault containment not achievable in process/module form;
- separate release cadence/ownership;
- security trust boundary;
- language/runtime requirement;
- multi-venue central function.

Do not split merely to imitate cloud architecture patterns.
