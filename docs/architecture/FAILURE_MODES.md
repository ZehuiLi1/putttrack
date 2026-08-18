# Failure and Degraded-Operation Matrix

## Principles

1. Fail conservatively for score.
2. Preserve the player journey where evidence remains authoritative.
3. Show a specific human recovery action.
4. Never hide gaps, duplicates or manual correction.
5. Degrade by feature/authority, not by pretending confidence is unchanged.

| Failure | Detect | Automatic degradation | Recovery | Player-facing | Score authority |
|---|---|---|---|---|---|
| One geometry Anchor lost | heartbeat/stale ranges/bus health | track with remaining 3/4 if covariance gate passes | retry, power/bus reset, swap node | usually no interruption; subtle degraded flag only if needed | spatial features allowed only if confidence passes |
| Two geometry Anchors lost | no observations/health alarms | no authoritative 2D fix; retain generic motion and physical sensors | pause affected spatial features; replace nodes | clear hole degraded/pause message | no geometry-only bonus/hazard; cup may use independent policy/review |
| Reference/fifth Anchor lost | health alarm | return to four-node baseline | normal maintenance | no interruption | unchanged if four-node gate passes |
| CS multipath/confidence collapse | residuals, estimator disagreement, covariance, no-fix | increase Anchor set/rate, reacquire, reject outliers | reposition player/clear obstruction/operator review | `Checking ball position`; avoid technical error | hold scoring-critical spatial event |
| Ball low battery | voltage/fuel gauge/service projection | lower noncritical telemetry; finish current action if safe | replace/quarantine after action | staff/service message, not mid-stroke panic | block new assignment below threshold |
| Ball dies mid-hole | disconnect/health timeout | preserve committed strokes/features; use physical evidence/manual continuation policy | issue replacement ball and audited reassignment | clear assistance flow | no inferred missing events; operator resolves |
| Wrong ball at tee | authenticated ID vs session | refuse arming | tell owner/required ball | specific colour/number/name guidance | no mutation |
| Duplicate packet/event | event ID/sequence seen | ignore exact duplicate | none | invisible | idempotent; no second score |
| Late/out-of-order observation | source time/sequence/reorder window | apply to tracker only within bounded lag; otherwise audit-only | none or review | invisible unless evidence pending | completed score not silently rewritten |
| Ball IMU failure | self-test/stuck data/inconsistent motion | position-only tracking; disable IMU-dependent stroke policy | replacement/service | hole may continue with adjusted policy or pause | stroke requires alternate independent evidence/review |
| Cup sensor stuck active | health/dwell/self-test | mark sensor unavailable; use secondary evidence only if validated | inspect/reset/replace | `Cup sensor checking`; operator path | conservative hold/review; no single CS point completion |
| Cup sensor missing/no edge | health/expected sequence | alternate evidence candidate and timeout | retry/inspect/operator confirm | short pending state | no automatic completion unless alternate policy passed prevalidated gate |
| Tee sensor failure | health/presence inconsistency | CS/local proximity can propose candidate but not automatic READY unless fallback policy is validated | reset/replace/operator arm | clear assisted-start flow | no stroke before authoritative arming |
| Feature sensor failure | heartbeat/edge plausibility | disable that bonus/hazard or use geometry only if configured and validated | repair later | show feature unavailable; normal hole remains | never guess feature result |
| Zone Gateway restart | heartbeat/boot ID | field nodes buffer; Edge marks zone reacquiring | restore config/schedule, replay by event ID | brief checking state if active | no duplicates; pending events reconcile |
| Zone Gateway total loss | uplink/health timeout | affected holes pause or run only explicitly independent features | spare swap, config restore | clear hole unavailable/reroute | Edge does not invent observations |
| Edge process restart | process health | Gateway buffers; HMI reconnects | replay operational event log, restore projections | short reconnecting state | committed state recovered idempotently |
| Edge server loss | host/UPS monitoring | Gateways buffer but cannot authoritatively score new events | boot warm spare/restore image | controlled venue pause | no new score authority until Edge restored |
| Hole display offline | WebSocket/heartbeat | ring/audio continues; operator tablet fallback | reboot/swap display | visual fallback/attendant direction | gameplay continues if player state is unambiguous |
| WAN/cloud unavailable | sync health | local operation and queue | automatic resync | no impact; optional `sync pending` at end | local result remains authoritative |
| Firmware mismatch | capability/version registry | quarantine node or use compatible subset | update/rollback/replace | hole degraded only if necessary | incompatible node evidence rejected |
| Partial OTA | update state/health verifier | rollback/quarantine; maintain healthy cohort | retry in maintenance window | no active-round update | no evidence from failed version |
| RS-485 branch fault | bus errors/current/fuse | second branch and unaffected holes continue | isolate branch, inspect cable/node | affected hole only | feature authority follows surviving evidence |
| 24 V zone supply fault | voltage/health | UPS/other zones continue | fuse/PSU repair | zone unavailable/reroute | no synthetic events |
| Power loss | UPS/mains monitoring | orderly Edge shutdown if possible; field state buffered | restore, reconcile devices/sessions | resume/restart policy visible | event log and IDs prevent duplicate score |
| Camera failure | camera health | research GT/replay unavailable | repair/recalibrate | no production gameplay impact | none, because camera not production XY authority |
| Database degraded/full | DB/queue/storage monitoring | stop accepting new sessions before corruption; retain in-memory/queued observations only per policy | free storage/failover/restore | controlled pause | never continue unpersisted authoritative score beyond defined safety window |
| Operator mistaken correction | audit review | no automatic concealment | compensating audited event by authorized role | corrected result transparent if relevant | history preserves both actions |

## Degradation levels

```text
NORMAL
DEGRADED_NONCRITICAL       feature/replay/analytics reduced
DEGRADED_LOCALISATION      position confidence reduced; critical geometry held
ASSISTED_PLAY              operator confirms selected events
HOLE_PAUSED                no safe scoring authority
ZONE_PAUSED
VENUE_PAUSED
```

The current level is explicit in Edge state and HMI. A lower level never silently advertises normal confidence.

## Recovery testing

Every release stage must inject:

- process/device restarts;
- one/two Anchor loss;
- bus disconnect/reconnect;
- duplicate/out-of-order replay;
- stuck/missing cup and tee sensors;
- WAN loss;
- failed update/rollback;
- low/dead ball;
- disk/full database conditions.

Exit evidence includes player-facing screenshots, authoritative event replay and proof that score did not mutate incorrectly.
