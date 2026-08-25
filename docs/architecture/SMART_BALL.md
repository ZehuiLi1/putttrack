# Smart Ball Architecture

## 1. Role

The smart ball is a **V1 augmentation** to an already-working optical venue.

It owns:

- physical Ball ID;
- NFC/NFCT participation;
- BLE identity/health/state transport;
- generic motion sensing;
- battery/firmware/device health.

It does **not** own:

- player identity;
- hole rules;
- route/zone authority;
- score;
- cup completion authority;
- final game outcome.

Bluetooth Channel Sounding is optional and is not required for V1 core play.

---

## 2. Stage decisions

| Stage | Hardware / purpose |
|---|---|
| NFCT bring-up | Bbo nRF54L15 + external 13.56 MHz FPC coil |
| Compact prototype | Nordic nRF54L15 Tag and/or Seeed XIAO nRF54L15 Sense for BLE/IMU/NFC integration experiments |
| EVT | Custom balanced core with nRF54L15, external NFC antenna, primary-cell A/B power path and 6-axis IMU |
| DVT | Reduce/qualify PMIC, sensor and RF options from measured benefit |
| Production | Qualified core/shell, manufacturing calibration/provisioning and signed firmware |

Nordic Tag remains valuable as an RF/CS research reference even though CS is not a V1 scoring dependency.

---

## 3. Why nRF54L15 remains the leading candidate

The reason is now broader than Channel Sounding:

- one SoC provides BLE plus NFCT and leaves CS available for future optional features;
- sufficient memory margin for product firmware, security and OTA;
- low-power System OFF operation supports a primary-cell architecture;
- Nordic development ecosystem and available Tag/Bbo hardware reduce bring-up risk;
- CS can be enabled later without changing the MCU if trajectory features become worthwhile.

The chip remains conditional on EVT RF-in-shell, impact, current and manufacturing tests.

---

## 4. Candidate V1 block diagram

```text
                 one primary cell
                       |
           +-----------+-----------+
           |                       |
    direct-power path         nPM2100 path
           |                       |
           +-----------+-----------+
                       |
                   nRF54L15
              +--------+--------+
              |        |        |
            NFCT      BLE      IMU rail
              |                   |
        NFC FPC coil           6-axis IMU

SWD/pogo + production test + battery/health test points
```

A second primary cell is not a baseline requirement. Add one only if measured service life cannot be met with an acceptable single-cell size and the mechanical-balance penalty is justified.

---

## 5. NFC / NFCT role

NFCT is a near-field session/identity mechanism, not a continuous positioning system.

Preferred use:

```text
ball in System OFF with NFCT wake enabled
        |
placed on Tee reader field
        |
NFCT wake
        |
Ball ID / near-field association
        |
BLE begins normal session transport
```

Ball hardware requires an external NFC antenna/coil connected to the nRF54L15 NFCT pins and tuned for the final mechanical environment.

Tee NFC may provide:

- deterministic physical Ball ID association;
- wake from System OFF;
- optional short session/bootstrap exchange.

A Hole NFC station may later identify the ball in a slowed/stopped return-chute read zone. It is optional because optical cup sensing already confirms entry.

NFC does not replace optical route/cup evidence.

---

## 6. BLE role

BLE is the normal ball-to-venue communication channel after wake.

V1 payloads may include:

- Ball ID / session alias;
- firmware/hardware revision;
- boot/session/sequence IDs;
- battery/health;
- generic motion state/events;
- selected diagnostic windows in Research Mode.

Avoid making continuous connected handover a V1 requirement where simple advertisements/event transport can satisfy the experience. The final BLE transport mode should be chosen from measured reliability and power data.

---

## 7. Motion sensor strategy

The first integrated prototype keeps a 6-axis IMU so the team can record and classify:

- impact;
- rolling;
- slowing/settling;
- stationary;
- pickup/carried;
- drop/bounce;
- unknown/ambiguous motion.

These are generic motion states. They may strengthen evidence but do not directly create score.

Because normal venue wake can be provided by Tee NFC, a dedicated always-on wake accelerometer is no longer automatically required. Compare:

1. NFC-only normal-session wake + 6-axis IMU powered after wake;
2. one IMU with low-power wake mode;
3. dual-sensor architecture only if service/transport use cases justify it.

Do not keep a second sensor simply because the CS-first architecture originally assumed motion wake.

---

## 8. Power architecture

### Primary-cell default

Start from one primary lithium cell.

Two candidate electrical paths must be compared on custom EVT hardware:

```text
A) cell -> nRF54L15 (+ separate/simple IMU load switch if needed)

B) cell -> nPM2100 -> nRF54L15
                 -> switched sensor rail
```

nPM2100 is not required merely to power the nRF54L15. Its candidate value is:

- primary-cell energy utilisation/regulation;
- fuel-gauge / service-state support;
- switched peripheral rail;
- reset/watchdog/power-management integration.

Direct battery may win if it gives sufficient usable capacity, voltage stability, battery estimation and reliability with a lower BOM/area.

### NFC-wake constraint

If NFCT wake from System OFF is required during normal venue standby, the nRF54L15 must retain VDD. Do not use a PMIC state that removes SoC power and then expect NFCT to wake it.

### Measurement programme

Measure:

- System OFF with NFCT wake enabled;
- NFC field wake energy/latency;
- BLE advertisement/event energy;
- IMU active and idle energy;
- RF burst battery sag;
- service-life projection for representative daily rounds;
- direct versus nPM2100 usable battery capacity.

CS energy is measured separately as a V2 optional-feature cost.

---

## 9. NFC antenna strategy

V1 starts with **one ball-side NFC antenna** rather than two/three switched coils.

Reasons:

- nRF54L15 NFCT presents one antenna interface;
- multiple switched coils complicate tuning and wake behaviour;
- it is easier to keep the moving ball simple and solve orientation diversity at the powered Tee/Hole reader side if needed.

Prototype test matrix should cover:

- multiple FPC coil sizes;
- distance;
- 0–90 degree orientation;
- battery/PCB proximity;
- shell/potting/ferrite effects;
- read success and wake success.

If single-reader orientation dead zones are unacceptable, prefer Tee reader coil diversity before adding ball-side RF switching.

---

## 10. 2.4 GHz antenna strategy

For V1 BLE-only operation, prioritise a robust single production antenna path and simple mechanical/RF integration.

Nordic Tag dual antennas remain useful for CS research. A custom-ball dual-antenna design is only retained if BLE reliability or optional-CS tail-error tests prove enough value to justify switch/layout/calibration complexity.

Do not make dual antenna a V1 requirement by default.

---

## 11. Mechanical/core architecture

- target conventional golf-ball diameter/mass where practical for the venue product;
- keep centre of mass close enough to geometric centre to avoid perceptible roll bias;
- constrain battery/PCB as one robust core rather than independent impact masses;
- final cell connection should be impact-safe rather than a loose spring holder;
- potting/shell must be validated for NFC and 2.4 GHz detuning;
- provide production test access and reproducible Ball ID provisioning;
- validate water, UV, cleaning chemicals, temperature, repeated putter/wall impacts and roll bias.

The final battery size is selected together with mechanical balance, not from capacity alone.

---

## 12. Device identity and provisioning

Use an opaque `BALL_ID`, not the BLE MAC as the gameplay identity.

Venue Edge owns:

```text
BALL_ID -> PLAYER_ID -> SESSION_ID
```

The ball may store its provisioned device identity and calibration/service data, but does not store the player's profile or score rules.

V0 ordinary-ball gameplay may have `ball_id = null`; V1 NFC/BLE fills the identity field without changing the game-event model.

---

## 13. Firmware state machine

A V1 state model can be much simpler than the previous CS scheduler state machine:

```text
SHIPPING / SERVICE
       |
       v
SYSTEM_OFF
       |
       | NFC field (normal venue path)
       v
SESSION_INIT
       |
       v
READY
       |
     impact
       v
ACTIVE / ROLLING
       |
       v
SETTLING / STATIONARY
       |
 session end / timeout
       v
SYSTEM_OFF
```

Side states:

- `PICKED_UP / CARRIED`;
- `LOW_BATTERY`;
- `FAULT`;
- `SERVICE_DFU`;
- `QUARANTINED`.

CS-specific ranging states are added only when the optional CS feature is enabled.

---

## 14. Channel Sounding boundary

CS is an optional V2 capability, not a V1 identity/state requirement.

Research can continue using:

- Nordic nRF54L15 Tags;
- six Bbo nRF54L15 boards;
- raw Channel Sounding logging and advanced estimators.

A product feature may consume CS output only after measured accuracy, tail error, scheduling, power and user-value gates are met.

If CS is disabled or unhealthy, ordinary optical gameplay remains functional.

---

## 15. Immediate prototype sequence

1. Bbo + external FPC NFC coil: read/tag proof.
2. NFCT field wake from System OFF.
3. NFCT wake -> BLE Ball ID/state advertisement.
4. Nordic Tag/XIAO: IMU generic-state data collection.
5. Tee reader/session prototype.
6. Custom EVT: direct battery versus nPM2100 A/B.
7. Shell/NFC/2.4 GHz/mechanical tests.
8. Optional CS reintroduced only as a separate feature experiment.
