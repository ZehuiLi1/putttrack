# Current Execution Plan — BLE + Motion First, Channel Sounding Deferred

**Status:** Active — M1 complete; M2 transport/development-board low-power
validated; M4 physical-ingress software boundary implemented

**Effective:** 2026-09-03

**Decision:** ADR-013

## 1. Current objective

Build a useful one-hole PuttTrack prototype without making Bluetooth Channel
Sounding (CS), Anchors or continuous XY localisation a dependency.

The active sensing path is:

```text
nRF54L15 Tag
  identity + health + generic motion + signed BLE OTA
                         |
                         v
BLE development gateway / Venue Edge
                         ^
                         |
physical tee + cup + feature sensors
                         |
                         v
confirmed semantic evidence -> Gameplay Engine -> hole screen / audit
```

CS research is retained in the repository but is not on the critical path.
This decision does not claim that motion alone can determine authoritative
position, cup entry or every valid stroke.

## 2. What is already complete

- Sensor-independent Gameplay Engine and evidence adapter.
- Local one-hole player-flow vertical slice.
- Evidence recording/replay foundation.
- nRF54L15 Tag SWD identification and complete RRAM/FICR/UICR backup.
- MCUboot with lab Ed25519 signing key and two application slots.
- Encrypted BLE SMP upload, test boot, confirmation and rollback-capable layout.
- Physical OTA update from `0.0.0` to `0.0.1`, followed by a second successful
  confirmed reboot.
- XIAO nRF52840 Sense running as a USB HCI controller for Mac development.
- Repository-owned Tag firmware `0.1.17` installed over BLE while powered from
  CR2032, remotely confirmed and verified after ordinary and NFC cold reboots.
- Multi-Tag capture now locks the full encrypted device ID plus boot/firmware,
  sequence/time and health-counter continuity. Confirmed `0.1.17` also exposes a
  per-device advertising suffix.
- A primary-source Trackaball review confirmed the relevance of distributed
  BLE reception, local buffering and state-sensitive radio operation. A
  hardware-neutral multi-receiver observation/aggregation contract is now
  implemented without granting RSSI position or scoring authority. Dynamic TX
  power remains research-only behind FTO and physical RF/current gates.
- Stable device ID, per-boot ID, health and encrypted raw motion telemetry.
- ADXL367 + BMI270 valid at a measured 50.0 Hz source rate with a 64-sample live
  window and an atomic 1024-sample/20.48-second frozen history.
- A real stationary run produced 170 contiguous samples over 3.38 s, zero
  sequence gaps, 100% sensor validity and a provisional `STATIONARY_CANDIDATE`.
- Three complete 1024-sample stationary frozen histories then reproduced that
  state over 20.46 seconds with zero gaps, zero active samples and zero clipped
  records. One used a physically tilted orientation and retained the same
  stationary result; its runtime route stayed `READY` at zero strokes.
- Firmware exports the configured stream/IMU ODR and range plus three per-boot
  clipping counters; the accepted run had zero clipping deltas.
- Automatic low power is verified on the battery-powered physical Tag: after
  30 seconds without measured activity, BMI270 and the 50 Hz stream stop,
  SPI22 is suspended, ADXL367 enters hardware wake-up mode, MCU polling stops,
  and connectable BLE advertising slows to 2.0–2.5 seconds. ADXL367 INT1 on
  nRF54L15 P0.03 repeatedly restored the 100 Hz IMUs, 50 Hz stream and fast
  advertising without DAPLink.
- Encrypted SMP and OTA remained reachable in idle. Six consecutive idle
  connect/disconnect cycles passed before confirmation, and two more passed
  after confirmation, reset and automatic idle. Advertising start errors and
  sensor errors remained zero.
- The first mechanically assembled ball closes fully and restrains the Tag. Two
  distinct post-reset stationary orientations each contained 1,024 contiguous
  dual-IMU samples over 20.46 seconds at exactly 50 Hz with zero error, gap or
  capture-time clipping deltas. BMI270 and ADXL367 independently measured about
  130° separation between their mean gravity vectors; the checked-in physical
  dataset is `experiments/research_ball_r0_stationary`. Before that reset,
  status exposed one ADXL367 boot-initialization
  failure that had been counted every 160 ms for almost the full 3.2-hour boot.
- Confirmed `0.1.17` detects consecutive failures, invalidates capture history
  across recovery, tries local reconfiguration three times, permits one
  quiet/disconnected warm reboot and quarantines recurrence. Host capture
  rejects unhealthy state or a recovery-generation change. The healthy path has
  passed on the assembled Ball; deterministic fault injection and sealed reset
  soak remain open.
- The physical capture converts to canonical `MotionObservation` and reaches the
  one-hole no-CS candidate policy. A real stationary observation was audited as
  `motion.stationary` with zero score/stroke mutation.
- A 502-sample, 10.02 s continuous hand-motion window separated cleanly from
  stationary as `ACTIVE_MOTION_CANDIDATE`; it reached the runtime as
  non-authoritative `motion.active` with the hole still `READY` and zero strokes.
- Episode-label consistency rejects two nominal pickup files in which no action
  was actually measured, preventing incorrect labels from entering analysis.
- A natural pickup/carry frozen history preserved 4.08 s pre-action rest, active
  samples from 4.08–7.80 s and 12.66 s post-action rest with zero gaps. Its
  canonical `motion.active` observation again produced no score mutation.
- A desk-bound ordinary handling/cable-adjustment control landed in the
  fail-closed motion dead band and was rejected by the runtime with zero score
  mutation, rather than being promoted to active motion or a stroke candidate.
- A second natural pickup/carry repetition remained generic active with zero
  gaps and zero clipped records. A second, stronger desk-handling repetition
  also became generic active and overlapped pickup intensity; its runtime route
  remained non-authoritative `motion.active`, `READY` and zero strokes. This
  demonstrates that motion intensity cannot safely identify pickup or impact.
- `IMPACT_CANDIDATE`/pickup/drop software paths remain pending until independent
  evidence; foreign/inactive Ball observations fail closed.
- Official PCA20072 revision 1.0.0 design files confirm an optional NFC route:
  P1.02/NFC1 and P1.03/NFC2 reach accessible pads and C17/C19 provide
  `TBD` tuning footprints. The default board DTS selects GPIO mode. The first
  research ball now has a 26 mm, 1.0 uH loop and provisional 220 pF values at
  C17/C19; powered PN532 reads and System OFF NFC cold wake passed, while final
  tuning/range/current remain unproved.
- The optional NFC Type 2 service variant passes a complete NCS v3.4.0 MCUboot +
  application build. Confirmed `0.1.17` retains the one-shot 10-second
  fast-BLE discovery window on an NFC field edge and exposes window/field
  diagnostics. Both generated images select NFCT pad mode; the signed OTA image
  verified and passed guarded BLE OTA, strict URI reads, field/window telemetry,
  field removal, NFC cold wake, automatic low-power return and post-confirm
  reset. Range, instrumented tuning and current remain physical gates.
- Nordic's official `nrf54l15_tag_v1.0.step` has been measured into a
  reproducible `33.10 × 33.00 × 8.48 mm` populated-board envelope. A
  conservative `34.0 mm × 9.2 mm` removable carrier keep-in and a controlled
  programmable-roller protocol are documented for the first research ball.
- A hardware-neutral `PhysicalSensorObservation` ingress now validates node
  health/debounce declaration, source ordering, Ball identity and active-hole
  context. Assigned tee presence can emit `tee.presented`; cup completion
  requires optical entry followed by PN532 confirmation of the exact active
  Ball within 3 seconds and an already-confirmed stroke. The policy, HTTP path,
  audit, idempotency and
  deterministic replay tests pass. The PN532 Tee plus optical-entry/PN532 Cup
  mechanism is selected but not yet physically validated.
- A fail-closed `HoleActivationAuthority` now treats NFC as a bounded proximity
  request, checks the flexible cross-session set of eligible active Balls,
  enforces one Ball per hole and one
  hole per Ball, increments a hole epoch, and models explicit-end plus bounded
  fail-safe System OFF. Its 500-Ball/18-hole test holds exactly 18 active leases.
  Production Ball credential verification and firmware activate/end commands
  remain gates; current Just Works encryption is not called authentication.
- The deterministic no-CS one-hole software soak completed 1,000 four-player
  rounds with 20,000 injected identity/order/premature-cup/retry faults and zero
  invariant failures. This closes the software-only soak gate; ADR-009's
  physical 1,000-round/mechanism reliability gate remains open. See
  [`verification/NO_CS_ONE_HOLE_SOAK.md`](verification/NO_CS_ONE_HOLE_SOAK.md).

## 3. Active milestones

### M1 — Native PuttTrack Tag firmware

Replace the generic SMP sample application with a repository-owned application
while preserving the proven MCUboot/SMP partition and signing configuration.

Minimum firmware surface:

- stable opaque device ID, boot ID, firmware/hardware version and sequence;
- reset reason, uptime and health;
- battery/voltage observation where the board exposes a valid measurement path;
- encrypted BLE management and signed OTA;
- explicit research/service mode; no gameplay rules or score in the Ball.

**Exit:** repository-owned image boots, reports identity/health, updates over BLE
and remains confirmed after a second reboot.

**Result:** Passed initially with `0.1.13` on 2026-09-02 and remains passed with
confirmed `0.1.17` after guarded OTA, battery observation and NFC System OFF
cold wake on 2026-09-03.

### M2 — Tag sensor bring-up and raw capture

Bring up the devices already enabled by the NCS v3.4.0 Tag board definition:

- ADXL367 low-power accelerometer over I2C;
- BMI270 accelerometer/gyroscope over SPI;
- BME688 only as optional environmental/debug context, not a gameplay sensor.

Start with polling and conservative rates, then add interrupt/FIFO operation.
Every capture records ODR, range, clipping counters, monotonic timestamp,
sequence and dropped-sample count. Preserve raw windows outside the gameplay
event log.

**Exit:** stationary, pickup, putter impact, rolling and settling episodes can be
captured and replayed without gaps being silently hidden.

**Current result:** two distinct assembled-ball stationary orientations,
unmistakably active generic motion and two
natural pickup/carry episodes with pre/post rest pass through atomic
frozen-history capture and replay. Two ordinary handling controls also fail
closed at the semantic boundary: one remains unclassified and the stronger one
becomes only generic active. Putter impact, rolling and settling still require
labelled physical episodes. The current bare Tag is suitable for
transport/sensor validation, not final instrumented-ball thresholds.
The development-board power state machine is also verified. Although upstream
DTS omits the property, the official PCA20072 schematic connects ADXL367 INT1
to P0.03. The repository overlay declares it, and confirmed firmware uses ACT-
only hardware wake with no MCU polling while BMI270, SPI22 and streaming are
off. The final Ball PCB should retain this route and reserve INT2 if practical.

### M3 — Generic motion evidence V0

Implement the deterministic ladder already defined in the IMU research plan:

- `STATIONARY`;
- `IMPACT_CANDIDATE`;
- `ACTIVE_ROLLING`;
- `SETTLING`;
- `PICKED_UP/CARRIED`;
- `DROP/FREE_FALL_CANDIDATE` where evidence supports it.

The Ball emits generic observations/candidates. Venue Edge combines these with
game state and independent physical sensors before producing
`stroke.confirmed`, `cup.confirmed` or feature evidence.

**Exit:** labelled held-out sessions meet the agreed per-class and false-stroke
gates; adjacent windows from one episode are not split across train/test.

**Current result:** deterministic features, canonical observation conversion and
the fail-closed one-hole candidate router are implemented. Stationary and
clearly active generic motion have physical data and a deliberately wide
diagnostic separation. Pickup and desk handling already overlap at generic
activity intensity, so action-type thresholds and calibrated confidence remain
intentionally absent; physical context must resolve action semantics.

### M4 — No-CS physical one-hole vertical slice

Replace simulation endpoints incrementally:

1. assigned Ball identity and BLE presence;
2. physical tee presence for READY;
3. Tag motion candidate for stroke;
4. physical feature switch/beam where the hole requires a narrow feature;
5. physical cup sensor for completion;
6. operator correction and audit retained as recovery.

No continuous XY position is promised in this milestone. Broad geometry-based
bonus zones are disabled or replaced with explicit physical sensors.

**Exit:** complete real one-hole rounds with zero manual scoring in the normal
path, conservative handling of ambiguous evidence and no duplicate/cross-ball
score mutations.

**Current result:** step 3's non-authoritative ingress, audit, idempotency and
Ball isolation are wired. The software side of steps 1–2 and 5 is now wired as
a fail-closed physical ingress: tee requires correlated assigned-Ball identity,
and cup requires entry plus occupancy while the active Ball is already PLAYING.
Motion still cannot confirm a stroke on its own. Real BLE identity correlation,
tee/cup mechanisms, feature hardware and physical false-positive/latency tests
remain. See
[`hardware/PHYSICAL_TEE_CUP_INGRESS.md`](hardware/PHYSICAL_TEE_CUP_INGRESS.md).
The same boundary has passed a seeded 1,000-round software fault-injection soak;
this is not a substitute for physical sensor trials.

### M5 — Gateway, enclosure and service evidence

- Keep the XIAO nRF52840 Sense as a development USB HCI adapter for now.
- Do not make DAPLink part of normal operation; retain it for recovery.
- Evaluate a Linux BLE gateway or ESP32-C6 only after the Tag telemetry contract
  and one-hole I/O count are known. ESP32-C3 is acceptable for a small BLE/Wi-Fi
  experiment, but C6 gives more future protocol headroom; neither is selected
  as production Gateway yet.
- Build a repeatable instrumented-ball core before treating bare-Tag IMU
  thresholds as product evidence.
- Treat NFC as a bounded service/provisioning experiment, not a gameplay or OTA
  transport dependency. After the antenna and C17/C19 matching values are
  identified, prove NDEF read first, NFC-to-BLE service wake second and System
  OFF wake last. See
  [`hardware/NRF54L15_TAG_NFC.md`](hardware/NRF54L15_TAG_NFC.md).

## 4. Explicitly deferred

The following remain useful research assets but do not block M1–M5:

- Bbo Initiator/Reflector bring-up;
- Channel Sounding capture and five-Anchor rig;
- range calibration, multilateration and asynchronous range-domain EKF;
- connected-CS airtime/energy and 20/40/80-ball scheduling simulation;
- dual-antenna CS optimisation and connectionless CS/PAwR;
- UWB comparison triggered only by a later positioning requirement.

Do not delete the parsers, fixtures, contracts or historical ADRs. They preserve
option value and can be reactivated without contaminating the active MVP path.

## 5. Product capability boundary without CS

The near-term prototype can support:

- ball assignment and recognition;
- READY from physical tee presence plus assigned-ball context;
- generic impact/motion candidates;
- physically instrumented bonus/hazard features;
- physical cup completion;
- automatic deterministic score, UX and audit;
- BLE health, service and OTA.

It cannot honestly claim:

- continuous ball XY;
- geometry-only feature crossing;
- trajectory reconstruction;
- reliable final resting position from IMU alone;
- automatic discrimination of every putter strike from every collision without
  independent context and measured validation.

## 6. CS revisit triggers

Re-open the CS track only when at least one is true:

- the locked gameplay requires broad spatial zones or trajectory-dependent
  scoring that physical sensors cannot provide economically;
- operator recovery remains too frequent because independent position evidence
  is missing;
- the Bbo/Tag rig is ready and a bounded experiment can answer a specific
  product decision;
- venue economics show that localisation infrastructure is cheaper or more
  reliable than instrumenting the required physical features;
- a later UWB/CS comparison is justified by measured MVP limitations.

## 7. Immediate order

1. ~~Freeze and document the working OTA baseline.~~ Complete.
2. ~~Create the repository-owned Tag application with identity/health and SMP.~~
   Complete (initially `0.1.13`; currently `0.1.17` confirmed on the physical
   Tag).
3. ~~Bring up ADXL367 and BMI270 with a raw BLE capture path.~~ Complete for
   polling/live-window/frozen-history research capture.
4. ~~Record clearly active and natural pickup/carry bare-Tag baselines.~~
   Complete with two natural pickup and two ordinary-handling repetitions. The
   overlap is a measured reason not to set semantic action thresholds from
   intensity. Defer impact/rolling/settling until an appropriate restrained or
   ball-core setup.
5. ~~Implement and physically validate adaptive development-board power.~~
   Complete functionally in battery-powered `0.1.17`, including event-driven
   ADXL367 INT1 wake, repeated wake/re-sleep, slow-advertising access and
   post-confirm reset. Measured coin-cell current remains a separate gate.
6. ~~Make capture safe before a second Tag is powered.~~ Complete: full
   `DEVICE_ID` locking, address pinning, boot/session continuity and strict
   malformed/error handling are implemented. Confirmed `0.1.17` provides a
   human-readable short-ID advertising suffix.
7. ~~Build and characterize a repeatable, restrained research-ball core.~~
   Complete for this revision with 86 gap-free roller captures covering speed,
   direction, clipping and powered acceleration/deceleration boundaries. Next
   record independently labelled putter impact, free rolling, settling and
   post-stop episodes, then extend the implemented
   feature extractor into the measured deterministic generic-motion FSM; do not
   invent action thresholds from additional bare-Tag hand movement.
8. Connect physical tee and cup evidence to the existing one-hole vertical
   slice using a Tee PN532 plus Cup optical-entry/PN532 identity pair, and
   complete an automatic real one-hole path.
9. ~~Prove the NFC identity, bounded BLE handoff and System OFF cold wake.~~
   Complete on `0.1.17`. Next integrate the accepted NFC-gated hole activation
   policy; BLE remains the encrypted lab transport, while production controller
   authentication and KMU-backed Ball credentials remain gates.
10. Decide the pilot gateway and feature-sensor I/O from measured needs.
11. After FTO review, test the documented connectionless multi-receiver BLE
    ladder with explicit TX-power metadata. Do not treat receiver RSSI as
    authoritative position. See
    [`research/PUTTSHACK_TRACKABALL_TECH_REVIEW.md`](research/PUTTSHACK_TRACKABALL_TECH_REVIEW.md).

The repeatable research-ball carrier and roller phase are complete. The roller
may now remain off-site; continue field capture metadata and episode discipline
with the Ball and XIAO nRF52840 according to
[`hardware/TAG_MOTION_EPISODE_RUNBOOK.md`](hardware/TAG_MOTION_EPISODE_RUNBOOK.md).

## 8. Current priority decision

The highest-value next work is real, independently labelled putt/free-roll/
settle data. It attacks the largest unmeasured Ball risk and prevents
the motion FSM from being tuned to hand-held development-board behavior.

The next product-value milestone is physical Tee/Cup integration because it
turns the existing software vertical slice into a real, automatic one-hole
experience. The selected simple shape is one fixed PN532 at Tee and one
optical-entry plus PN532 identity pair at Cup. NFC-gated activation is now an
accepted software policy; physical reader geometry and authenticated Ball
commands remain to be proved.
