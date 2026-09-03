# ADR-015 — NFC gates simple per-hole Ball activation

**Status:** Accepted

**Date:** 2026-09-03

## Context

The venue must be easy for players and attendants, keep unused Balls asleep and
prevent neighbouring holes from accepting one another's Ball events. A normal
venue may have hundreds of people or a large Ball inventory, while only one
player Ball per ordinary hole needs active-play radio and IMU service.

The physical nRF54L15 research Ball has proved read-only Type 2 NFC, a bounded
BLE discovery window and NFC wake from System OFF. Its current BLE laboratory
pairing is encrypted Just Works and therefore does not authenticate the
controller against an active man-in-the-middle. The NDEF identity can also be
copied. Neither fact should add player-visible setup, but neither may be hidden
by calling proximity authentication.

## Decision

1. The normal unassigned Ball state is System OFF with NFC sensing only. Motion
   does not activate an unassigned Ball.
2. Each Tee has one fixed PN532-class reader mapping, such as
   `tee-pn532-H07 -> H07`. This is installation configuration, not daily player
   configuration.
3. A Tee read creates a ten-second `ACTIVATION_PENDING` request. NFC establishes
   proximity and Ball identity discovery only; it grants no gameplay authority.
4. Venue Edge checks inventory, an open assignment, the hole's currently
   eligible Ball set and one-Ball-per-hole / one-hole-per-Ball exclusivity.
   Eligibility may span different groups/sessions; `session_id` determines score
   ownership, not physical admission to an otherwise available Tee. Course mode
   may still require the Ball's next legal hole, or deliberately allow free-play
   routing. The first authorized Ball locks the hole. A separately authenticated
   Ball/controller exchange must match the device observed by NFC before Edge
   issues `(session_id, hole_id, epoch)`.
5. During a valid turn the Ball uses two power levels:
   - measured motion selects full active sampling and the active radio policy;
   - ordinary stationary time selects `ACTIVE_IDLE`, retaining ADXL367 interrupt
     wake while BMI270/high-rate streaming sleep.
6. Ordinary stationary time never ends a live turn by itself. The Ball enters
   NFC-only System OFF after an authenticated explicit end, or as a fail-safe
   when both motion and Edge authority contact have been absent beyond their
   limits. A separate hard maximum bounds any stuck activation.
7. Cup completion requires two distinct physical observations on the current
   hole: an optical/beam entry edge followed by PN532 confirmation of the exact
   active Ball. They may share one ESP32 controller but must have distinct sensor
   identities. Only the completed semantic event ends the lease.
8. Hole `epoch` increments on every activation. Commands or observations from an
   old epoch fail closed. A local allow-list is an efficient first filter, not a
   cryptographic control.
9. Player names, passwords, Anchor lists, scores, firmware and configuration are
   never written through NFC. The player action remains: place the Ball on the
   Tee.

## Initial timing values

These are configurable pilot starting points, not final product measurements:

| Policy | Initial value | Result |
|---|---:|---|
| NFC activation window | 10 s | no valid authorization returns to System OFF |
| Active-to-ADXL idle | 30 s stationary | matches proven `0.1.17`; does not end the turn |
| Edge authority offline | 2 min | used only together with long inactivity |
| Inactive System OFF | 30 min | fail-safe when authority is also offline |
| Hard activation limit | 4 h | contains a stuck lease regardless of motion |

Edge heartbeats keep a legitimately stationary live turn in `ACTIVE_IDLE`.
Cup confirmation, an operator end, session abandonment or round completion ends
it immediately. Timing must be calibrated from real course duration and failure
tests before production.

## Security boundary

For the pilot, NFC cloning is a low-priority threat compared with accidental
cross-hole association, stale state and sensor errors. The architecture still
does not trust NDEF identity alone because the additional checks cost the player
nothing.

The checked-in activation policy consumes a `VerifiedBallAuthorization` result;
it does not manufacture that result from a BLE address or encrypted Just Works
link. Production must provision a unique Ball credential and verify a fresh,
Ball-bound challenge. nRF54L15 KMU/PSA-backed provisioning is the preferred
implementation candidate. Per-round/per-hole key derivation is only required if
connectionless application packets need their own MAC; it is not automatically
required for every connected BLE message.

## Operational result

For an 18-hole ordinary course, the authority can hold at most 18 live hole
leases even if 500 registered Balls exist. Brief service/activation windows are
additional but do not receive gameplay authority. The invariant depends on Edge
transactional persistence and explicit release/recovery, not RF range.

The only fixed installation mapping visible to staff is reader-to-hole (and the
normal device inventory). Players configure no passwords, keys or Anchors.

## Implemented evidence

`putttrack.venue.HoleActivationAuthority` now provides:

- strict reader and immutable device inventory mapping;
- open-session assignment and cross-session eligible-turn checks;
- bounded NFC pending requests;
- external verified-credential boundary;
- per-hole and per-Ball exclusivity;
- monotonic hole epochs and consumed-token rejection;
- explicit end, active-idle, offline-plus-inactivity and hard-timeout decisions;
- a strict fixed-installation JSON loader.

Tests cover wrong Ball/reader/hole, copied NFC identity without matching verified
device, expired and reused activation tokens, stale epochs, explicit end,
stationary-with-heartbeat behavior and 500 registered Balls constrained to 18
active leases. This is software policy evidence; production credential
provisioning, persistent transactions and physical Tee/Cup timing remain open.

## Consequences

Positive:

- the player experience is one physical action at the Tee;
- unused and waiting Balls ignore motion and remain NFC-only;
- active Balls retain reliable next-stroke wake without running the full IMU;
- RF cross-hearing cannot by itself cross-assign gameplay;
- one ESP32 may run the Cup optical input and PN532 without weakening the
  two-sensor rule.

Costs and remaining gates:

- two fixed NFC readers per ordinary hole are the direct Tee-plus-Cup design;
- PN532 Cup range/orientation must pass through the real cup geometry after the
  Ball settles, especially near metal;
- production Ball credentials and controller authentication must be provisioned;
- Edge leases must move from the reference in-memory policy to transactional
  local persistence and audited recovery;
- Ball firmware still needs authenticated activate/end commands and automatic
  pending-timeout return to System OFF before this becomes physical product
  behavior.

## Primary references

- [Bluetooth Core Security Manager — Just Works authentication properties](https://www.bluetooth.com/wp-content/uploads/Files/Specification/HTML/Core_v6.3/out/en/host/security-manager-specification.html)
- [Nordic nRF54L Series application-key provisioning](https://docs.nordicsemi.com/r/bundle/nrfutil/page/nrfutil-device/guides/provisioning_keys.html/provisioning-keys-for-the-nrf54l-series)
- [Nordic nRF54L15 KMU provisioning](https://docs.nordicsemi.com/r/bundle/ps_nrf54l15/page/kmu.html-concept_provision)
