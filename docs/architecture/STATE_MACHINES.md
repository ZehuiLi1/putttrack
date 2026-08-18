# Canonical State Machines

## 1. Ball

```text
MANUFACTURED -> SHIPPING -> STORAGE -> IDLE_UNASSIGNED
 -> ASSIGNED -> PRESENTED -> ARMED -> IMPACT -> ACTIVE_ROLLING
 -> SETTLING -> STATIONARY

side states:
 PICKED_UP / CARRIED
 LOW_BATTERY
 FAULT
 SERVICE_DFU
 QUARANTINED
```

Ball state is physical/operational and never equals score authority.

## 2. Anchor

```text
BOOT -> SELF_TEST -> REGISTERING -> SYNCING -> READY
 -> LINK_PREPARED -> CS_ACTIVE -> READY

side states:
 BUS_BUFFERING
 DEGRADED_RF
 UPDATE_STAGED -> UPDATING -> VERIFYING -> READY / ROLLBACK
 FAULT / QUARANTINED
```

An Anchor never emits game points.

## 3. Zone Gateway

```text
BOOT -> SELF_TEST -> REGISTERING -> SYNCING -> READY -> ACTIVE

side states:
 BUS_DEGRADED
 EDGE_OFFLINE_BUFFERING
 UPDATE_STAGED -> UPDATING -> VERIFYING -> READY / ROLLBACK
 FAULT / QUARANTINED
```

## 4. Hole/gameplay

```text
AVAILABLE
 -> DETECTED_CHECKING
 -> READY
 -> PLAYING
 -> PLAYER_COMPLETE
 -> AVAILABLE (next unfinished player)
 -> GROUP_HOLE_COMPLETE
 -> NEXT_HOLE

side states:
 EVIDENCE_PENDING
 DEGRADED
 ASSISTED_PLAY
 PAUSED
 FAULT
```

Only confirmed semantic evidence advances authoritative gameplay state.

## 5. Session

```text
CREATED
 -> CHECK_IN
 -> BALLS_ASSIGNED
 -> READY_FOR_COURSE
 -> ACTIVE
 -> ACT_1_COMPLETE (optional 9-hole product boundary)
 -> ACTIVE_ACT_2
 -> ROUND_COMPLETE
 -> RESULT_SYNC_PENDING
 -> CLOSED

side states:
 PAUSED
 ABANDONED
 OPERATOR_REVIEW
```

## 6. Evidence candidate

```text
OBSERVED
 -> VALIDATING
 -> PENDING_MORE_EVIDENCE
 -> CONFIRMED -> GAMEPLAY_EVENT
             \-> REJECTED
             \-> EXPIRED
             \-> OPERATOR_REVIEW -> CONFIRMED/REJECTED
```

## 7. Track

```text
NO_FIX
 -> INITIALISING (robust WLS)
 -> TRACKING (asynchronous range EKF)
 -> DEGRADED
 -> REACQUIRING
 -> TRACKING / NO_FIX

motion modes:
 STATIONARY
 ROLLING
 IMPACT_TRANSIENT
 PICKUP_CARRY
```

## 8. Update job

```text
CREATED -> ELIGIBILITY_CHECK -> STAGED -> APPLYING -> VERIFYING
 -> COMPLETE
 -> ROLLBACK -> COMPLETE_PREVIOUS
 -> QUARANTINED
```

No device class updates during an incompatible active-play window.

## 9. Fault lifecycle

```text
DETECTED -> CLASSIFIED -> DEGRADED/PENDING
 -> AUTOMATIC_RECOVERY
 -> RECOVERED
 or OPERATOR_ACTION -> RECOVERED
 or QUARANTINED/PAUSED
```

Every transition records actor/source, reason, time, affected authority and player-facing state where applicable.
