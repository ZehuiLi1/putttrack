# PuttTrack Project Status

**As of:** 2026-09-04
**Active direction:** BLE + motion + physical tee/cup; Channel Sounding deferred

This is the short, evidence-ranked project dashboard. Detailed decisions remain
in the architecture, ADR and hardware documents. Status labels mean:

- **Physical pass:** observed on the named hardware path;
- **Software pass:** executable tests pass, but the physical mechanism is absent;
- **Build-only pass:** firmware compiles/signs, but has not run on the target;
- **Pending physical:** the next useful evidence requires hardware or enclosure work;
- **Deferred:** deliberately outside the current MVP critical path.

## Current result

The repository has a reliable smart-Tag development baseline, a mechanically
assembled first research ball, a checked-in two-orientation stationary baseline,
a seven-episode exploratory/manual-floor capture set, a completed 86-capture
programmable-roller characterization, ten recent pickup/carry episodes and ten
nominal putt episodes. It also has a powered NFC service plus System OFF
cold-wake path and a complete software-only one-hole scoring path. The latest
temporal analysis gives a promising pickup hypothesis, but there is still no
independently labelled/held-out action classifier or physically automatic hole.
The largest remaining uncertainty is high-precision pickup discrimination from
ordinary no-lift handling and rolling pickup; the next product uncertainty is
real tee/cup evidence.

| Area | Status | What is actually established | Next gate |
|---|---|---|---|
| nRF54L15 Tag firmware | Physical pass; recovery fault path pending | Confirmed `0.1.17`; battery voltage, NFC cold wake, healthy sensors, auto idle and SMP passed | Controlled R0 motion data; separately inject/reproduce sensor faults |
| Signed BLE OTA | Physical pass | Encrypted SMP upload, MCUboot test boot, confirmation and rollback-capable layout | Production controller authentication and release policy |
| Motion low power | Physical pass, current unmeasured | BMI270/stream/SPI stop at rest; ADXL367 INT1 wakes the Tag without polling; repeated wake/re-sleep passed | Measure whole-board current and battery pulse behavior |
| Multi-Tag identity | Software + physical pass | Capture locks full `DEVICE_ID`, address and boot/session continuity; `0.1.17` retains per-device scan name | Commission the second Tag only for a concrete two-ball test |
| NFC reader bench | Physical pass | ESP32-C3 + PN532 strictly decodes powered and cold-start nRF54L15 URIs; demand-loaded parser handles its 992 B advertised area | Distance/orientation/near-metal sweep |
| NFC Tag/service | Physical pass | Confirmed `0.1.17`, 1.0 uH loop + provisional 220 pF pair, repeated >50 strict reads, complete-read counter and bounded 10 s BLE window | Instrumented tuning/range/current |
| NFC System OFF wake | Physical pass | Explicit encrypted command, >60 s BLE absence, NFC reset reason, changed boot ID, BLE recovery and confirmed image verified | Repeated cold-wake/storage soak; keep explicit service state |
| Battery observation | Physical pass; current unmeasured | Internal VDD ADC reports 2.91--2.96 V; generic CR2032 OCV percentage is labelled estimated | Temperature/load characterization and current instrument |
| Bare-Tag motion data | Physical pass, limited scope | Stationary, handling and pickup datasets show generic motion separation and semantic overlap | Do not tune putt/roll logic from more hand-held Tag data |
| Research-ball mechanics/data | Physical pass; roller phase complete; field labels exploratory | Printed halves close fully. The formal roller set has 86/86 passing captures and 45,784 contiguous samples. Ten recent pickup and ten nominal-putt captures are complete, but two nominal putts are invalid, four are suspected collision mixtures and most dynamic putts clip the gyro range | Collect no-lift handling, rolling pickup, explicit collision/step and held-out operator/session truth |
| Sensor fault recovery | Healthy-path physical pass | A real assembled-ball ADXL367 boot-init fault was diagnosed; confirmed `0.1.17` retains retries, capture-generation invalidation, one guarded reboot and quarantine | Fault injection and ten sealed reset cycles |
| Motion analysis pipeline | Software pass; pickup hypothesis measured | Strict validation, deterministic features and fail-closed generic candidates. A post-hoc vertical-impulse + gyro-energy + axis-consistency rule separates all current usable pickup/roll/putt/tap episodes in-sample | Validate on no-lift controls, rolling pickup and separate-day/operator holdout before implementing gameplay authority |
| IMU research export | Software pass | A repeatable packager inventories 161 unique local raw files / 113,867 motion records, deduplicates content, separates invalid diagnostics, and adds manifests, units, checksums and model-analysis guidance | Keep raw `runs/` local; regenerate a reviewed archive after each labelled field batch |
| Gameplay Engine / one-hole UI | Software pass | Deterministic, idempotent local gameplay and 1,000-round/20,000-fault soak | Run against physical inputs and real players |
| Tee/cup ingress | Software pass | Identity/order/health checks; tee presence and two-stage cup completion contracts | Select/build mechanisms and measure false-positive/latency behavior |
| NFC-gated hole activation | Software pass | Fixed reader mapping, cross-session eligible-turn checks, one Ball/hole, epoch replay protection, active-idle and fail-safe leases; 500-Ball/18-hole invariant passes | Provision Ball credential, persist leases, then connect authenticated firmware commands |
| Multi-receiver BLE | Software/research pass | Redundant reception contract and state-based research RF profiles; RSSI has no score/position authority | FTO review, connectionless event packet and multi-receiver RF/current trial |
| Pilot gateway | Not selected | XIAO nRF52840 USB HCI is a working development bridge | Select Linux/ESP32-C6 only from measured BLE/I/O/buffering needs |
| Channel Sounding / Anchors | Deferred | Research assets retained | Reopen only on an explicit spatial gameplay or evidence trigger |

## Critical path

```text
completed roller characterization
        -> labelled free impact/roll/settle captures
        -> measured generic motion FSM
        -> physical tee + independent cup evidence
        -> real automatic one-hole rounds
        -> gateway and custom-ball EVT decisions
```

NFC is a useful parallel service experiment while the ball is printing. It is
not allowed to delay the physical gameplay path and is not a replacement for
BLE transport, signed images or DAPLink recovery.

## Immediate order

1. Validate pickup precision first: collect strict no-lift touch/rotate/slide
   controls, rolling-pickup episodes and a separate-day/operator holdout. Keep
   the provisional detector research-only; see
   [`PICKUP_DETECTION_STATUS_20260904.md`](research/PICKUP_DETECTION_STATUS_20260904.md).
2. Build one Tee PN532 and one Cup optical-entry + PN532 identity rig, then
   connect them to the implemented activation and evidence policies.
3. In parallel, characterize NFC range/orientation and the provisional 1.0 uH
   plus 220 pF pair; cold wake has passed, but close reads are not final tuning.
4. Measure Tag current before changing advertising-off/System OFF policy or
   claiming battery life.
5. After the event packet and FTO gate exist, test two or more BLE receivers for
   diversity and loss reduction, not RSSI positioning.
6. Select the pilot gateway after those physical I/O, buffering and radio results.

## Current stop line

Powered NFC service identity, bounded handoff, battery voltage and System OFF
cold wake have passed. The research ball is assembled, roller characterization
is closed, and a pickup detector now has an encouraging in-sample hypothesis.
The primary work is independent false-positive/holdout validation and physical
gameplay characterization. The next honest advances require one of:

- strict no-lift handling and rolling-pickup batches, followed by a separate
  session/operator holdout;
- an independently labelled assembled-ball free roll, putter impact, collision
  or cup episode;
- an instrumented NFC range/tuning/current experiment;
- a chosen physical tee/cup test mechanism;
- a current-measurement instrument.

Until one of those is available, additional motion thresholds, battery-life
numbers, NFC wake claims or RSSI-position claims would be invented rather than
measured.
