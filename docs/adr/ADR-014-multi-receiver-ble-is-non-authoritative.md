# ADR-014 — Multi-receiver BLE is redundant evidence, not position authority

**Status:** Accepted

**Date:** 2026-09-03

## Context

The no-CS MVP needs reliable Ball identity/event delivery and a way for an
upstream tee adapter to correlate physical presence with a provisioned Ball.
Puttshack/World Golf Systems primary sources describe distributed Bluetooth
beacons, more than one receiver observing a Ball, RSSI proximity, local Ball
history, dynamic transmit power and central aggregation.

RSSI is strongly affected by antenna orientation, enclosure/battery detuning,
people, multipath and transmit-power changes. A receiver hearing a Ball is not
proof that the Ball occupies a particular tee, feature or cup. The relevant WGS
patent claims also create an explicit FTO gate around some movement/proximity
power-control and tee mechanisms.

## Decision

1. Add a connectionless Ball event/health path that may be observed by several
   registered receivers; keep encrypted connected BLE for configuration,
   detailed history, diagnostics and signed OTA.
2. Record each receiver's own device/boot/sequence/time separately from the
   Ball device/boot/radio sequence and payload digest.
3. Include actual TX power with every receiver report used for RSSI/path-loss
   analysis.
4. Aggregate identical Ball packets for delivery diversity and research only.
   Receiver quorum grants neither continuous position nor Gameplay authority.
5. Continue to require physical tee/cup/feature evidence plus assigned Ball and
   game context for authoritative semantic events.
6. Keep state-based TX-power values research-only until FTO, controller,
   coverage, current, coexistence and many-Ball tests pass.
7. Use decentralized packet-keyed jitter for the first collision experiment;
   do not assume a patent-described server resend algorithm is required.

## Consequences

Positive:

- one missed receiver does not necessarily lose a Ball event;
- packet provenance supports real multi-Gateway experiments;
- TX-power metadata prevents obvious RSSI comparison errors;
- the existing no-CS authority boundary remains intact;
- detailed raw IMU need not be streamed to every receiver.

Costs and limits:

- a new connectionless packet format and receiver firmware are still needed;
- receivers require clock/identity/installation calibration;
- redundant reception increases Edge traffic and storage unless deduplicated;
- RSSI may remain useful only for coarse diagnostics or zones;
- dynamic TX power can reduce OTA/service reach if state transitions fail;
- production mechanisms remain subject to FTO and regulatory review.

## Validation

- unknown Ball devices and receiver identities fail closed;
- mixed packet keys, duplicate receiver reports and late observations fail;
- two or more receiver reports deduplicate to one non-authoritative packet set;
- changed TX power is explicit in every observation;
- one-, two- and many-Ball shell tests measure delivery, current and adjacent-
  hole leakage;
- a nearby non-tee Ball cannot satisfy the physical tee authority gate;
- connected service/OTA remains reachable in every permitted operating state.

## Revisit trigger

Revisit if calibrated physical tests show that one receiver is sufficient for
delivery, RSSI provides a bounded valuable zone result, dynamic power has no
measured energy/coexistence benefit, or FTO excludes a proposed mechanism.
