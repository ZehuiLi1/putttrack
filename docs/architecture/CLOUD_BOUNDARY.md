# Cloud Boundary and Offline Operation

## 1. Principle

The venue is authoritative for a live round. Cloud improves the product but is not required to recognise a ball, score a hole, display results locally or recover an ordinary fault.

## 2. Local-only critical path

The following must work with WAN disconnected:

- check-in from cached/local booking code or operator-created guest session;
- ball assignment and recognition;
- CS scheduling, localisation and motion/evidence processing;
- gameplay/scoring and leaderboard;
- tee/hole display and audio;
- operator review/correction;
- local persistence, replay and device health.

## 3. Cloud-owned capabilities

- booking/payment integration;
- optional persistent player account and history;
- loyalty/rewards;
- cross-venue leaderboards and seasonal challenges;
- fleet analytics and remote diagnostics;
- signed release/config catalogue;
- backup and reporting;
- support case evidence explicitly approved for upload.

## 4. Synchronisation model

```text
Venue event/outcome
 -> local commit
 -> outbound queue with idempotency key
 -> cloud acknowledgement
 -> queue completion
```

Rules:

- local completed-round score is not overwritten by cloud race conditions;
- every sync object has local ID, schema version, revision and content hash;
- retries are safe and ordered per aggregate where required;
- cloud booking/account updates may be cached inbound but cannot mutate an active score without an explicit local command/event;
- conflicts are surfaced to operator/support rather than silently merged.

## 5. WAN outage UX

Players should normally see no interruption. Optional online-only features can show `sync pending` after the round. Booking lookup falls back to local cache/code/operator creation. Rewards/history synchronize later.

## 6. Security boundary

- Edge initiates outbound cloud connections by default.
- Remote support is time-bound, authenticated and audited.
- Cloud release metadata is verified locally; devices accept only signed images.
- Personal data uploaded is minimized and separated from raw research measurements.

## 7. Recovery

The outbound queue survives Edge restart. On reconnection, sync resumes without duplicate booking, reward or result creation. Monitoring alerts when queue age/size exceeds policy.
