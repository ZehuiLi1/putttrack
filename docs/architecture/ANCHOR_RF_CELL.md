# Anchor and RF-Cell Architecture

## 1. Decision

PuttTrack uses fixed powered Anchors as Bluetooth Channel Sounding Initiators and the Smart Ball as Reflector. Research starts with five identical Bbo nRF54L15 boards plus a spare as the controlled baseline, then compares candidate fixed-antenna implementations only after that baseline is reproducible. Production starts from four geometry Anchors per ordinary RF cell and adds a fifth reference/elevated Anchor only when measured tail-error or availability gains justify it.

The inspected Bbo vendor package is registered at [`../hardware/bbo-nrf54l15dk/`](../hardware/bbo-nrf54l15dk/). It supports Phase-0 bring-up but does not prove production performance.

## 2. Why four is the production baseline

- Three non-collinear distances are the mathematical minimum for 2D position when ball height is constrained.
- A fourth observation gives overdetermination, residual checks and survival of one bad range.
- A fifth node can improve NLOS/tail behavior, but adds airtime, wiring, calibration, update and fault-management cost.
- Quantity alone cannot repair poor geometry; placement and line-of-sight matter more.

## 3. Research configurations

```text
M1: 3 selected perimeter Anchors
M2: 4 perimeter Anchors
M3: 4 perimeter + ground centre E
M4: 4 perimeter + elevated/reference R
M5: best-4-of-5
M6: weighted/robust 5
```

The fifth-node decision is based on P95/no-fix improvement and obstruction resilience, not average error alone.

Suggested keep threshold for production R:

- >=20% improvement in representative P95 position error; or
- >=50% reduction in no-fix/degraded intervals; or
- clear recovery of a scoring-critical blind region that cannot be solved by moving the four baseline Anchors.

### Research hardware progression

| Stage | Fixed node | Purpose | Decision status |
|---|---|---|---|
| A0 | Bbo nRF54L15DK | homogeneous vendor-supported CS baseline/debug node | KEEP for Phase 0 |
| A1 | Seeed XIAO nRF54L15 with controlled external 2.4 GHz FPC installation | compare antenna placement/enclosure/serviceability against Bbo baseline | CANDIDATE; measurement required |
| A2 | custom powered Anchor | 24 V/field-bus/qualified RF implementation | DEFER until A0/A1 + venue gates |

Changing the development board must not change geometry, truth points, procedure configuration or analysis definitions during an A/B comparison.

## 4. Placement rules

- Surround the playable region where practical; avoid nearly collinear geometry.
- Record true 3D coordinates. Ball Z is approximately constrained, but Anchor height affects measured slant range.
- Prefer controlled elevated placements with line-of-sight over a vulnerable ground-centre node.
- Avoid placing all antennas behind the same obstruction plane.
- Treat moving metal, water, decorative steel, walls and likely player body positions as RF design inputs.
- Preserve service access and stable orientation after installation.
- Conduct a site RF survey in final enclosures, not only bare-board tests.

## 5. Antenna architecture

### Research

- Bbo board RF is the single-feed baseline documented in `docs/hardware/bbo-nrf54l15dk/HARDWARE_EVIDENCE.md`.
- Record Bbo board orientation explicitly because the moving target and near-ground environment can expose directional/tail behavior.
- XIAO nRF54L15 + external FPC is an **Anchor candidate comparison**, mainly to test whether controlled antenna placement away from board/cable/metal improves installation consistency or error tails. It is not yet a production decision.
- Seeed documents switching between the XIAO onboard ceramic and external antenna; do not equate that ordinary selection example with a proven multi-path CS implementation.
- Nordic nRF54L15 Tag remains the moving-target dual-antenna reference.
- Record Anchor and Ball antenna/path/orientation in datasets.

### Production Anchor

Start with one well-designed fixed antenna because the Anchor does not rotate and can be installed/calibrated deliberately. Evaluate dual/switching antenna only if measured NLOS/tail improvement exceeds added RF switch, layout and calibration cost.

Use:

- validated 2.4 GHz reference/module layout;
- enclosure RF window;
- controlled ground clearance;
- installation jig for orientation;
- per-device/per-installation calibration.

## 6. Production Anchor block diagram

```text
24 V input
  -> fuse/reverse/transient protection
  -> isolated or protected DC/DC
  -> nRF54L15 / qualified module
       -> stable HFXO/LFXO
       -> RF matching + antenna
       -> watchdog/health
       -> signed bootloader
       -> local observation buffer
  -> isolated/protected RS-485
  -> status/service interface
```

## 7. Anchor firmware responsibilities

- authenticated startup and self-test;
- register with Zone Gateway;
- maintain assigned Ball links according to schedule;
- initiate one CS procedure at a time;
- extract/publish available IFFT/PBR, phase-derived and RTT observations;
- preserve quality/channel/antenna/procedure metadata;
- timestamp at acquisition, not USB/Edge receive time;
- report RF/clock/power/temperature/connection health;
- buffer observations through short bus outages;
- accept signed staged firmware/config updates;
- fail silent for score: never fabricate a distance or feature event.

## 8. Observation contract

Every range observation includes:

- schema version;
- device/boot/firmware IDs;
- zone/hole/RF-cell context;
- ball and Anchor opaque IDs;
- source monotonic timestamp and sequence;
- connection/procedure/subevent identifier;
- estimator values and units;
- antenna path;
- RSSI and quality fields;
- channel map/config digest;
- status flags and calibration version.

## 9. Calibration

Calibration layers:

1. factory board/RF calibration;
2. antenna-path and FAE-related calibration where exposed;
3. installed Anchor coordinate/height/orientation;
4. per-Anchor affine/range residual model;
5. optional environment/region bias model, introduced only after baseline evidence.

Replacing an Anchor invalidates only its calibration/version, not course/game rules.

## 10. Fault behavior

- one Anchor lost: tracker may continue with three if geometry/confidence passes;
- intermittent Anchor: weight/reject observations and raise maintenance alert;
- clock drift: quarantine observations outside sync policy;
- firmware mismatch: do not schedule scoring-critical ranging until compatibility passes;
- bus outage: bounded local buffer, then explicit gap marker;
- RF anomaly: preserve diagnostics and switch to degraded scoring policy.

## 11. Shared Anchors

Adjacent holes may share an elevated or boundary Anchor only if all of the following pass:

- geometry remains acceptable for each playable region;
- CS scheduling for simultaneous active balls remains bounded;
- one shared-node fault does not disable both holes' authoritative scoring;
- cabling and maintenance are simpler, not merely cheaper on BOM;
- calibration/course association remains unambiguous.

Shared Anchors are a site optimization, not the baseline research assumption.
