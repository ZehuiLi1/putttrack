# PuttTrack Project Status

**As of:** 2026-09-03  
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
assembled first research ball, a checked-in two-orientation stationary baseline
and a complete software-only one-hole scoring path. It does **not** yet have a characterized rolling/impact dataset or a
physically automatic hole. The largest remaining uncertainty is the IMU signal
while the assembled ball rolls and is struck; the next product uncertainty is
real tee/cup evidence.

| Area | Status | What is actually established | Next gate |
|---|---|---|---|
| nRF54L15 Tag firmware | Physical pass + recovery build-only | Confirmed `0.1.13`; `0.1.16` adds bounded sensor recovery and fail-closed health telemetry | Finish R0 data on `0.1.13`, then guarded unconfirmed `0.1.16` OTA test |
| Signed BLE OTA | Physical pass | Encrypted SMP upload, MCUboot test boot, confirmation and rollback-capable layout | Production controller authentication and release policy |
| Motion low power | Physical pass, current unmeasured | BMI270/stream/SPI stop at rest; ADXL367 INT1 wakes the Tag without polling; repeated wake/re-sleep passed | Measure whole-board current and battery pulse behavior |
| Multi-Tag identity | Software + build-only pass | Capture locks full `DEVICE_ID`, address and boot/session continuity; `0.1.16` retains per-device scan name | Commission the second Tag only for a concrete two-ball test |
| NFC reader bench | Physical pass + stricter parser build-only | ESP32-C3 + PN532 reads NFC-A/NTAG213 over the proven SPI path; strict service URI identity/version parser compiles | Read a known URI, then the powered nRF54L15 through the actual loop |
| NFC Tag/service | Software + build-only pass | Signed `0.1.16` Type 2 URI plus one-shot 10 s fast-BLE window; host planner fails closed on identity, session, quarantine, compatibility and release policy | Antenna identity, C17/C19 tuning, powered read, then NFC field/window regression |
| NFC System OFF wake | Pending physical | Architecture and test order are defined; no product claim | Attempt only after powered reads and ordinary handoff are reliable |
| Bare-Tag motion data | Physical pass, limited scope | Stationary, handling and pickup datasets show generic motion separation and semantic overlap | Do not tune putt/roll logic from more hand-held Tag data |
| Research-ball mechanics | Physical pass, limited | Printed halves close fully, carrier is restrained, and two distinct 1,024-sample assembled stationary captures passed with approximately 130° gravity-vector separation | Controlled impact/roll/settle/stop captures |
| Sensor fault recovery | Build-only pass | A real assembled-ball ADXL367 boot-init fault was diagnosed; `0.1.16` separates samples from fault episodes, retries, invalidates capture generations, allows one quiet reboot and then quarantines | Fault injection, ten sealed reset cycles, then guarded physical candidate test |
| Motion analysis pipeline | Software pass | Strict dataset/session validation, deterministic features and fail-closed generic candidates | Fit only from controlled in-ball episodes |
| Gameplay Engine / one-hole UI | Software pass | Deterministic, idempotent local gameplay and 1,000-round/20,000-fault soak | Run against physical inputs and real players |
| Tee/cup ingress | Software pass | Identity/order/health checks; tee presence and two-stage cup completion contracts | Select/build mechanisms and measure false-positive/latency behavior |
| Multi-receiver BLE | Software/research pass | Redundant reception contract and state-based research RF profiles; RSSI has no score/position authority | FTO review, connectionless event packet and multi-receiver RF/current trial |
| Pilot gateway | Not selected | XIAO nRF52840 USB HCI is a working development bridge | Select Linux/ESP32-C6 only from measured BLE/I/O/buffering needs |
| Channel Sounding / Anchors | Deferred | Research assets retained | Reopen only on an explicit spatial gameplay or evidence trigger |

## Critical path

```text
restrained research ball
        -> controlled impact/roll/settle captures
        -> measured generic motion FSM
        -> physical tee + independent cup evidence
        -> real automatic one-hole rounds
        -> gateway and custom-ball EVT decisions
```

NFC is a useful parallel service experiment while the ball is printing. It is
not allowed to delay the physical gameplay path and is not a replacement for
BLE transport, signed images or DAPLink recovery.

## Immediate order

1. Collect the roller and putter impact/roll/settle/stop episode matrix on
   confirmed `0.1.13`; the two-orientation stationary baseline is complete.
2. Build the simplest real tee-presence and independent entry-plus-occupancy cup
   mechanisms, then connect them to the implemented ingress.
3. In parallel, identify the NFC loop and tune C17/C19 in the actual mechanical
   stack; install the NFC candidate only for a guarded unconfirmed test.
4. Measure Tag current before changing advertising-off/System OFF policy or
   claiming battery life.
5. After the event packet and FTO gate exist, test two or more BLE receivers for
   diversity and loss reduction, not RSSI positioning.
6. Select the pilot gateway after those physical I/O, buffering and radio results.

## Current stop line

All high-value NFC work that can be proved without the antenna has reached the
build-only boundary. The research ball is now assembled, so motion work has
moved into physical characterization. The next honest advances require one of:

- a controlled assembled-ball rolling or impact episode;
- the documented NFC antenna/tuning network attached for a powered read;
- a chosen physical tee/cup test mechanism;
- a current-measurement instrument.

Until one of those is available, additional motion thresholds, battery-life
numbers, NFC wake claims or RSSI-position claims would be invented rather than
measured.
