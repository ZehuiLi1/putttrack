# PuttTrack Project Status

**As of:** 2026-09-09
**Active direction:** BLE + motion + physical NFC tee/cup; Channel Sounding deferred

This is the short, evidence-ranked project dashboard. Detailed decisions remain
in the architecture, ADR and hardware documents. Status labels mean:

- **Physical pass:** observed on the named hardware path;
- **Software pass:** executable tests pass, but the physical mechanism is absent;
- **Build-only pass:** firmware compiles/signs, but has not run on the target;
- **Hardware ready:** the prototype hardware exists and is ready to connect, but the integrated physical behavior is not yet validated;
- **Pending physical:** the next useful evidence requires physical integration or a real-world experiment;
- **Deferred:** deliberately outside the current MVP critical path.

## Current result

The repository has a reliable smart-Tag development baseline, a mechanically
assembled first research ball, a checked-in two-orientation stationary baseline,
a seven-episode exploratory/manual-floor capture set, a completed 86-capture
programmable-roller characterization, and reviewed no-lift, rolling-pickup,
pickup/carry, pickup/drop, gentle-putt, rail-collision and course-step batches.
It also has a powered NFC service plus System OFF cold-wake path and a complete
software-only one-hole scoring path.

**Hardware milestone (2026-09-09): the prototype hardware chain required for the
first real one-hole test is now prepared: NFC Tee + Smart Ball + IMU + optical
Cup.** This is an integration-ready milestone, not a physical-pass claim. The
next product gate is no longer hardware acquisition or component selection; it
is a real end-to-end automatic one-hole round using these four physical inputs.

The latest temporal analysis gives a promising pickup hypothesis, but there is
still no independently labelled/held-out action classifier or physically
automatic hole. The frozen research detector and raw-source evaluator are now
implemented and have exposed their failure modes. The largest remaining motion
validation gap is independent date/operator/Ball/surface evidence; the immediate
product uncertainty is whether the prepared Tee + Ball/IMU + Cup chain behaves
reliably as one system under real play.

| Area | Status | What is actually established | Next gate |
|---|---|---|---|
| nRF54L15 Tag firmware | Physical pass; recovery fault path pending | Confirmed `0.1.17`; battery voltage, NFC cold wake, healthy sensors, auto idle and SMP passed | Controlled R0 motion data; separately inject/reproduce sensor faults |
| Signed BLE OTA | Physical pass | Encrypted SMP upload, MCUboot test boot, confirmation and rollback-capable layout | Production controller authentication and release policy |
| Motion low power | Physical pass, current unmeasured | BMI270/stream/SPI stop at rest; ADXL367 INT1 wakes the Tag without polling; repeated wake/re-sleep passed | Measure whole-board current and battery pulse behavior |
| Multi-Tag identity | Software + physical pass | Capture locks full `DEVICE_ID`, address and boot/session continuity; `0.1.17` retains per-device scan name | Commission the second Tag only for a concrete two-ball test |
| NFC reader bench | Physical pass | ESP32-C3 + PN532 strictly decodes powered and cold-start nRF54L15 URIs; demand-loaded parser handles its 992 B advertised area | Integrate the prepared Tee into the one-hole chain; then measure real installed orientation/range if needed |
| NFC Tag/service | Physical pass | Confirmed `0.1.17`, 1.0 uH loop + provisional 220 pF pair, repeated >50 strict reads, complete-read counter and bounded 10 s BLE window | End-to-end Tee activation under real ball placement; tuning only if the installed test exposes a reliability problem |
| NFC System OFF wake | Physical pass | Explicit encrypted command, >60 s BLE absence, NFC reset reason, changed boot ID, BLE recovery and confirmed image verified | Repeated cold-wake/storage soak; keep explicit service state |
| Battery observation | Physical pass; current unmeasured | Internal VDD ADC reports 2.91--2.96 V; generic CR2032 OCV percentage is labelled estimated | Temperature/load characterization and current instrument |
| Bare-Tag motion data | Physical pass, limited scope | Stationary, handling and pickup datasets show generic motion separation and semantic overlap | Do not tune putt/roll logic from more hand-held Tag data |
| Research-ball mechanics/data | Physical pass; current same-session collection gate complete | Printed halves close fully. In addition to 86/86 roller captures, reviewed batches now cover 10 no-lift handling, 10 rolling pickup, 10 pickup/carry, 10 pickup/drop, 11 gentle putt, 10 rail collision and 11 course-step episodes. Labels remain operator-confirmed rather than video truth | Stop repeated same-environment capture; collect only failures exposed by integrated play plus an independent session/operator/Ball holdout |
| Sensor fault recovery | Healthy-path physical pass | A real assembled-ball ADXL367 boot-init fault was diagnosed; confirmed `0.1.17` retains retries, capture-generation invalidation, one guarded reboot and quarantine | Fault injection and ten sealed reset cycles |
| Motion analysis pipeline | Software/research pass; non-authoritative | The configuration-hashed frozen V0 evaluator runs directly from raw JSONL. Across 60 metric-eligible precision episodes it makes 41 definitive decisions (TP=20/TN=21/FP=0/FN=0) and returns 19 UNKNOWN; rail collisions expose gyro clipping. PG-DH-HSMM primitives and trainer/export integration are tested but have no validated production coefficients | Freeze and run a new-day/operator/second-Ball/surface holdout; prioritize integrated-play false strokes/collisions as the next targeted evidence |
| IMU research export | Software pass | The first 161-capture / 113,867-record archive and complete manifest are versioned; all newer reviewed batches preserve raw JSONL, analysis and provenance separately | Keep the historical archive immutable; review new captures into named experiment directories rather than committing live/duplicate `runs/` |
| Gameplay Engine / one-hole UI | Software pass | Deterministic, idempotent local gameplay and 1,000-round/20,000-fault soak | Connect the real Tee, Ball/IMU and Cup; run automatic one-hole rounds with real players |
| Tee/cup ingress | Hardware ready + software pass; integrated physical test pending | NFC Tee hardware, Smart Ball/IMU hardware and optical Cup hardware are prepared; identity/order/health checks and tee/cup evidence contracts exist in software | Bench E2E loop first, then real-lane rounds; measure false positives, missed events, duplicate events and latency |
| NFC-gated hole activation | Software pass | Fixed reader mapping, cross-session eligible-turn checks, one Ball/hole, epoch replay protection, active-idle and fail-safe leases; 500-Ball/18-hole invariant passes | Connect authenticated Ball command/ACK to physical Tee activation and verify session/hole isolation |
| Multi-receiver BLE | Software/research pass | Redundant reception contract and state-based research RF profiles; RSSI has no score/position authority | FTO review, connectionless event packet and multi-receiver RF/current trial after one-hole E2E passes |
| Pilot gateway | Not selected | XIAO nRF52840 USB HCI is a working development bridge | Select only after the physical one-hole test establishes real I/O, buffering and radio needs |
| Channel Sounding / Anchors | Deferred | Research assets retained | Reopen only on an explicit spatial gameplay or evidence trigger after the simple one-hole product path is proven |

## Current product milestone

The project has crossed from **component preparation** into **system integration**.
The immediate V1 prototype is intentionally simple:

```text
NFC Tee
  -> identify/present Ball
  -> assign/arm session over BLE
  -> READY
  -> Smart Ball IMU confirms real strokes
  -> stroke count
  -> optical Cup confirms completion
  -> HOLE COMPLETE
```

For this gate, do **not** add Channel Sounding, localisation, bonus zones, complex
AI, a custom production Ball PCB, or an 18-hole deployment. Those are later
options. The next decision must be informed by a reliable physical one-hole
experience first.

## Critical path

```text
NFC Tee + Smart Ball/IMU + optical Cup hardware prepared
        -> connect all four physical components to the existing evidence/gameplay path
        -> 20-cycle bench end-to-end loop
        -> real mini-golf-lane one-hole play
        -> targeted false-stroke / collision / pickup fixes only
        -> 30 consecutive automatic real-hole rounds without manual score intervention
        -> decide whether the V1 product value is sufficient before localisation/custom-ball expansion
```

## Immediate order

1. **Freeze hardware acquisition for the MVP.** The required prototype chain is
   prepared; do not delay integration to buy more boards or redesign the final
   PCB.
2. Connect the physical NFC Tee, Smart Ball/IMU event path and optical Cup to the
   existing gameplay/evidence interfaces. NFC should establish Ball identity
   and activation context; BLE carries session/hole commands and Ball events.
3. Run a **20-cycle bench E2E test**: present Ball -> READY -> simulated/physical
   stroke -> stationary/next stroke -> Cup trigger -> HOLE COMPLETE -> reset.
   Remove duplicate-event, stale-session and reset faults before course testing.
4. Move the same system to **one real mini-golf lane**. Test normal putts,
   gentle putts, hard putts, rail collisions, repeated collisions, pickup,
   replacement, rough-surface rolling and real Cup entry.
5. Record a common timestamped event log containing at minimum session/hole/Ball
   identity, tee state, motion/impact decision, stroke count, cup state,
   event/sequence ID and end-to-end latency. Preserve raw IMU windows around
   disputed events.
6. Only tune motion logic against failures observed in integrated play. Do not
   reopen broad threshold search or collect more duplicate same-session data.
7. After the physical one-hole gate passes, decide whether the next value layer
   is gameplay features (bonus/hazard/challenge), multi-ball/multi-hole scaling,
   or spatial localisation.

## One-hole physical acceptance gate

These are **engineering targets for the next experiment**, not current measured
performance claims:

- **Tee:** at least 49/50 correct presentations in the installed configuration,
  with zero wrong-Ball or duplicate-session acceptance;
- **Stroke:** target at least 98/100 real putts correctly counted in the first
  integrated pass, while rail/wall collisions and pickup/replacement do not
  create extra strokes;
- **Cup:** target 100/100 real entries detected in the first formal Cup test,
  because this event has a dedicated physical sensor and should be near
  deterministic;
- **Whole hole:** 30 consecutive real rounds complete automatically from Tee
  presentation through HOLE COMPLETE without manual score intervention.

Passing this gate establishes **PuttTrack V1 as a working physical system
prototype**. It does not yet establish production reliability, final battery
life, multi-hole scaling, localisation accuracy or commercial readiness.

## Current stop line

The prototype hardware needed for the first automatic hole is prepared. The
next honest advance is therefore **physical integration evidence**, not another
component purchase or another speculative algorithm branch.

The following remain valid parallel research items, but none should delay the
one-hole test:

- an independent date/operator/Ball/surface holdout for the frozen motion work;
- current/power measurement;
- installed NFC range/orientation characterization if real Tee tests reveal a
  problem;
- targeted sensor fault injection.

Until the physical one-hole test is run, the repository must not mark the
integrated Tee + Ball/IMU + Cup chain as a Physical pass.
