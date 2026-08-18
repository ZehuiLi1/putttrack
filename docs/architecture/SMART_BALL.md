# Smart Ball Architecture

## 1. Role

The ball is a low-power authenticated sensing/ranging endpoint. It owns physical device identity and measurements; it does not own player identity, hole rules, final position, score or game outcome.

## 2. Stage decisions

| Stage | Hardware |
|---|---|
| Research | Nordic nRF54L15 Tag remains the dual-antenna/multi-sensor RF reference; Seeed XIAO nRF54L15 Sense is an optional compact single-active-antenna/IMU prototype candidate for A/B testing |
| EVT | Custom balanced core with nRF54L15, candidate nPM2100 + CR2447, two antenna paths and both wake + 6-axis sensors |
| DVT | Reduced/qualified sensor and antenna set based on measured benefit |
| Production | Qualified PCB/core/shell, manufacturing calibration and signed firmware |

The XIAO candidate is not a replacement for the Nordic Tag reference by declaration. It must be compared under identical orientation, rolling, ground-proximity and multipath conditions.

## 3. Why nRF54L15 remains the leading candidate

- Official Bluetooth Channel Sounding support in the nRF54L family.
- One device handles BLE control, CS Reflector, motion processing, security and OTA.
- 1.5 MB NVM / 256 KB RAM provides enough margin for product firmware and secure update.
- Low radio and sleep current support a multi-year primary-cell target.
- Nordic Tag and SDK provide a direct reference path.

This decision is conditional on EVT power, RF-in-shell and multi-link scheduling tests.

## 4. Candidate block diagram

```text
          CR2447 primary cell candidate
                      |
                 nPM2100 candidate
                      |
                 regulated rail
                      |
        +-------------+-------------+
        |                           |
    nRF54L15                    sensor rail
        |                           |
        |              +------------+------------+
        |              |                         |
   RF switch       wake accelerometer         6-axis IMU
    /     \
Antenna A Antenna B

SWD/pogo + manufacturing test + battery/health test points
```

## 5. Sensor strategy

### Research/EVT

Retain two sensor classes:

- ultra-low-power wake/motion detector;
- six-axis IMU for impact, roll, pickup, drop and research labels.

The XIAO nRF54L15 Sense is useful as a compact motion/CS prototype because Seeed documents an onboard LSM6DS3TR-C 6-DOF IMU. The Bbo core-board package must not be treated equivalently: its inspected guide lists LSM6DS3TR-C on the separate Kit expansion board, not as a bare-core-board resource.

### DVT decision

Compare:

1. two-sensor architecture;
2. one modern IMU in wake-on-motion mode;
3. accelerometer-only production state classification;
4. optional high-g impact sensor if ±16 g saturation prevents reliable classification.

A sensor is removed only after power and event-classification evidence shows no material loss.

## 6. Antenna strategy

- Nordic nRF54L15 Tag is the reference for two identical 2.4 GHz antennas and NCS-managed antenna switching.
- XIAO nRF54L15/Sense documents switching between an onboard ceramic antenna and an external antenna. Treat the normal XIAO configuration as **one active antenna at a time** unless a CS-specific multi-path configuration is separately implemented and verified.
- A XIAO Sense Ball prototype is therefore valuable mainly as a compact single-active-path comparison against the Nordic dual-path Tag.
- EVT custom ball should include two experimentally distinct antenna orientations if space permits.
- Measure single vs dual path under random ball orientation, ground proximity, battery shielding, shell/potting and wet/dry conditions.
- Production dual antenna is retained only if P95 ranging/no-fix improvement justifies switch, layout and calibration cost.
- Perform per-antenna-path calibration and record path identity in every range observation.

The expected value of Ball-side diversity is primarily lower tail error/no-fix sensitivity while the Ball rotates; do not assume a large P50 improvement without data.

## 7. Power architecture

### Primary-cell default

A primary coin cell avoids nightly charging infrastructure, charging-coil mass, contact alignment, water ingress and charging-rack maintenance.

Candidate: CR2447 + nPM2100. This is not frozen until measured load profiles exist.

### Targets

- Minimum product service-life gate: 2 years under a conservative venue workload.
- Stretch target: 5 years.
- Do not claim the publicly reported Puttshack 7.5-year estimate as PuttTrack performance.
- Measure energy per CS procedure, per motion burst, per connection setup, per advertisement and per OTA/service action.

### Rechargeable path

Deferred. Revisit only if:

- primary-cell service life misses the minimum target;
- replacement/retirement economics are unacceptable;
- impact-safe charging architecture is demonstrated;
- an updated FTO review clears the final charging/activation combination.

## 8. Mechanical/core architecture

- Standard-ball design target: diameter >=42.67 mm, mass <=45.93 g where feasible.
- Use a concentric rigid inner carrier or symmetric multi-part core.
- Welded-tab cell or constrained interconnect; no removable spring holder.
- PCB and battery must not become independent impact masses.
- Control radial mass distribution and verify static/dynamic balance.
- Potting must support components while not detuning RF or trapping damaging stress.
- Provide a predictable RF window and avoid conductive pigment/fill around antennas.
- Environmental validation: water ingress, temperature cycling, UV, chemical cleaning, repeated impact and roll bias.

### Suggested mechanical gates

- centre-of-mass offset measured and correlated with roll bias;
- no reset/contact interruption in repeated putter/wall impact tests;
- RF sensitivity/TX degradation within agreed limit versus open reference;
- no visible shell/core migration after endurance;
- mass and diameter lot controls.

## 9. Device identity and provisioning

- Opaque `BALL_ID`, not BLE MAC address.
- Hardware serial and cryptographic device identity provisioned at manufacture/service.
- Assignment to player/session exists only on Venue Edge.
- Advertising should expose only the minimum discovery alias required; scoring identity is accepted only after authenticated association.
- Keep manufacturing calibration, service status and revocation state in Device Registry.

## 10. Firmware state machine

```text
MANUFACTURED
  -> SHIPPING
  -> STORAGE
  -> IDLE_UNASSIGNED
  -> ASSIGNED
  -> PRESENTED
  -> ARMED
  -> IMPACT
  -> ACTIVE_ROLLING
  -> SETTLING
  -> STATIONARY

side states:
  PICKED_UP
  CARRIED
  LOW_BATTERY
  FAULT
  SERVICE_DFU
  QUARANTINED
```

### State responsibilities

- `SHIPPING`: lowest possible current; authenticated service wake.
- `STORAGE`: periodic minimal health, no venue activity.
- `IDLE_UNASSIGNED`: discovery/health advertisement.
- `ASSIGNED`: session alias active; low-rate zone presence.
- `PRESENTED`: tee context observed; local RF cell association.
- `ARMED`: READY confirmed; motion and ranging prepared.
- `IMPACT`: high-rate IMU capture and immediate scheduler trigger.
- `ACTIVE_ROLLING`: rolling state and CS participation.
- `SETTLING`: reduced motion, final-position confirmation.
- `STATIONARY`: hold position confidence then lower radio rate.
- `PICKED_UP/CARRIED`: publish generic evidence, suspend rolling model.
- `LOW_BATTERY`: service warning; admission policy controlled by Edge.
- `FAULT`: safe minimal behavior and diagnostics.
- `SERVICE_DFU`: signed update under service control, never during a live stroke.

## 11. Ball-to-venue protocol boundary

Ball outputs:

- authenticated identity/session alias;
- boot ID, firmware/hardware version;
- monotonic timestamp + sequence;
- generic motion events/states;
- selected raw IMU windows in Research Mode;
- battery/health;
- CS Reflector participation and connection state.

Ball does not output `+points`, authoritative `stroke.confirmed`, hole ID or final XY.

## 12. OTA and recovery

- Signed images, rollback counter/policy and known-good recovery image.
- Updates at assignment/service station or controlled idle window.
- Do not update balls in an active session unless an emergency quarantine policy explicitly ends assignment.
- Failed update returns to previous image or service mode.
- Production debug access is protected; authenticated service unlock is preferred.

## 13. Revisit triggers

Re-evaluate nRF54L15/primary cell/two-antenna architecture if:

- CS field gates fail despite infrastructure/algorithm optimization;
- UWB becomes required;
- power projection remains below 2 years;
- shell RF detuning removes the expected benefit;
- dual antennas show negligible P95/no-fix improvement;
- a single IMU meets wake and classification goals at lower total cost/current.
