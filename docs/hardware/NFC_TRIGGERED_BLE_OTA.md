# NFC-triggered BLE OTA service architecture

## Decision

Use NFC as a close-proximity service wake and identity-discovery mechanism. Use
BLE SMP to transport signed firmware, and retain MCUboot test boot, health
verification, confirmation and rollback. The current lab transport requires an
encrypted link but uses Just Works pairing; controller-authenticated management
is a production gate, not a capability of the present image.

This is **NFC-triggered BLE OTA**, not firmware transfer over NFC.

The first service station is the existing ESP32-C3 + PN532 reader connected to a
host computer or Venue Edge service process. The PN532 creates the NFC field and
reads the Ball's opaque service identity. The host decides whether an update is
required and performs the already validated BLE OTA flow. A future integrated
station may also run the BLE central and update client, but that is not required
for the first proof.

## Evidence boundary — 2026-09-03

| Path | Status | Meaning |
|---|---|---|
| ESP32-C3 to PN532 over SPI | Physical pass | Reader firmware and wiring are stable |
| PN532 to NFC-A card and blank NTAG213 | Physical pass | Real 13.56 MHz selection and Type 2 memory access passed repeatedly |
| PN532 to nRF54L15 NFC target | Powered physical pass | Strict service URI decoded and the 50-consecutive-read gate passed through the assembled Ball loop |
| nRF54L15 Type 2 service image | Physical pass | `0.1.16` passed guarded OTA, physical read, confirmation and post-confirm reset |
| One-shot 10 s NFC-to-fast-BLE window | Powered physical pass | Field counters correlated; duplicate edges were suppressed and the window closed without indefinite extension |
| Host service-touch/update planner | Software pass | URI/JSON identity cross-check, inventory/session/quarantine/version/hardware/release gates fail closed; it does not perform or authorize BLE OTA |
| nRF54L15 NFC wake from System OFF | Not yet tested | Supported upstream, but not proved on the PuttTrack hardware path |
| Signed BLE SMP OTA and MCUboot confirmation | Physical pass | Keep this as the firmware transport and recovery contract |
| ADXL367 interrupt wake and re-sleep | Physical pass | Keep motion wake as the gameplay/handling path |
| Whole-board current | Not measured | No battery-life or NFC power-saving claim is allowed yet |

The reader-side evidence is recorded in
[`ESP32C3_PN532_BRINGUP.md`](ESP32C3_PN532_BRINGUP.md). The Tag-side NFC and OTA
evidence is recorded in [`NRF54L15_TAG_NFC.md`](NRF54L15_TAG_NFC.md) and
[`NRF54L15_TAG_OTA_BASELINE.md`](NRF54L15_TAG_OTA_BASELINE.md).

## Responsibility split

```text
External service station                         Ball

ESP32-C3 + PN532                                 nRF54L15 + tuned NFC loop
  creates NFC field  --------------------------> NFC field detect / wake
  reads service URI  <-------------------------- Type 2 read-only NDEF
        |
        v
Host or Venue Edge
  validates device identity and desired version
        |
        +---------- BLE service link -----------> bounded service window
                    signed SMP image upload
                    MCUboot test boot
                    health check
                    confirm or rollback
```

The initial read-only URI contract is:

```text
putttrack://service/tag/<opaque-device-id>?fw=<version>
```

The RF UID and plain NDEF payload are discovery hints, not authoritative
credentials. The permanent player or session identity must never be placed in
the NFC payload.

## Service sequence

1. The Ball is in `SHIPPING`, deep service sleep or another policy state that
   permits proximity wake. BLE can be off in these states.
2. The PN532 produces an NFC field. The nRF54L15 records NFC as the wake reason
   and exposes the read-only service URI.
3. The Ball opens a short connectable BLE discovery window. Start with 10 seconds
   and extend it only after the approved service controller connects.
4. The reader reports the opaque device ID and current firmware version to the
   service controller. The controller checks inventory, hardware compatibility,
   assignment state, quarantine state and the desired signed release.
5. If no update is required, the controller does not connect and the Ball returns
   to its previous low-power state after the discovery timeout.
6. If an update is required, the lab controller establishes encrypted BLE
   management access. Production must additionally authenticate/authorize the
   service controller before extending a maintenance lease, capped initially at
   120 seconds per attempt. That lease extension is not implemented in `0.1.16`.
7. The controller uploads the signed image through SMP. MCUboot starts it in test
   mode. The application verifies boot, storage, sensors, BLE and watchdog health
   before confirmation.
8. A failed or unconfirmed image rolls back. Disconnect, timeout or malformed
   service traffic also returns the Ball to a safe low-power state.

Do not update a Ball during an active session. Service policy must reject or
explicitly quarantine it before opening an OTA transfer.

The repository implements this advisory decision boundary in
`putttrack.service`: it cross-checks the URI against the reader's redundant JSON
fields and can only return reject, no-update or offer-signed-update. An offer is
not BLE authorization and never bypasses controller credentials or MCUboot.

## Power-state policy

| State | Wake source | BLE policy | Purpose |
|---|---|---|---|
| `SHIPPING` | NFC service field | Off until a bounded service window | Commissioning and activation |
| `STORAGE` | NFC and policy-approved motion/health sources | Prefer off; periodic health only if evidence requires it | Shelf and between-session life |
| `IDLE_UNASSIGNED` | Motion and service touch | Low-duty discovery only if venue UX requires it | Assignment readiness |
| Gameplay states | ADXL367/motion and venue radio policy | BLE available for identity, telemetry and control | Normal play |
| `SERVICE_DFU` | Entered by approved NFC/BLE handoff | Connected only for bounded maintenance | Signed update and diagnostics |
| `QUARANTINED` | Explicit service/recovery action | No gameplay advertising | Fault containment |

NFC does not save Ball energy by itself. The saving comes only if firmware policy
can remove periodic BLE advertising from states that do not otherwise need it.
The current physical Tag already slows idle advertising to 2.0–2.5 seconds, so
the value of replacing that state with NFC-capable System OFF must be demonstrated
with whole-board measurements.

Measure at least:

- current idle policy with 2.0–2.5 second BLE advertising;
- NFC-capable System OFF without a field present;
- field-present wake and URI read energy;
- an NFC-triggered BLE window with no update;
- a complete signed OTA, test boot and confirmation;
- false/repeated-field energy and return-to-sleep behavior.

Do not convert those measurements into a service-life claim until duty cycle,
battery pulse capability, self-discharge and enclosure temperature are included.

## Security and abuse controls

- NFC field presence proves proximity only; it is not authentication.
- Keep signed-image verification, version policy, hardware compatibility checks,
  encrypted BLE and MCUboot rollback. Add authenticated controller authorization
  before treating the service path as production-ready.
- Do not accept identity reassignment, secrets or unsigned update instructions
  solely from a copied NDEF record.
- Apply wake-rate limiting and bounded windows so a continuously presented reader
  cannot keep the Ball awake indefinitely.
- Record wake reason, reader/service transaction ID, image digest, result and
  rollback reason in the service audit trail.
- Retain SWD/DAPLink and a known-good full image for commissioning and recovery.

The nRF54L15 supports NFC Type 2 and Type 4 Tag operation, but not NFC
Reader/Writer operation. Type 2 read-only is intentionally selected for the first
proof because it is sufficient for discovery and avoids a larger bidirectional
NFC command protocol. Revisit Type 4/TNEP only if a later requirement cannot be
met through the production-authorized BLE service channel.

## Hardware constraints

- The Ball requires a documented 13.56 MHz loop connected to `NFC1/NFC2`.
- Do not guess matching capacitor values. Tune with the actual antenna, leads,
  PCB, battery and enclosure present.
- Test orientation, distance, nearby metal and repeated cold start before treating
  a powered desktop read as an installed-product result.
- The externally powered PN532 service station may poll continuously; its power
  consumption is not Ball battery consumption.

## Implementation and acceptance order

1. Install the signed nRF54L15 Type 2 candidate as an unconfirmed test image and
   complete a powered read through the actual external NFC loop. **Passed with
   `0.1.16` on 2026-09-03.**
2. Correlate reader field presentation with Tag field-on/field-off counters.
   **Passed with 11 balanced field-on/off events before reset.**
3. Implement the bounded NFC-to-BLE window without System OFF and repeat BLE,
   sensor, motion-wake and guarded OTA checks. **Healthy-path physical pass;
   deliberate sensor fault injection remains separate.**
4. Complete one end-to-end NFC wake -> identity read -> BLE signed OTA -> health
   check -> confirm flow.
5. Prove NFC wake from System OFF separately, including reset reason, false wakes,
   timeout and repeated wake/re-sleep behavior.
6. Measure the current cases above and make a documented go/defer decision on
   disabling idle advertising in each product state.

The first product-shaped station can use one PN532 for check-in/assignment and a
second PN532 as a maintenance/OTA activation reader. One physical reader may also
serve both roles through host software modes; dedicated hardware is an operations
choice, not a protocol requirement.

## Primary references

- [Nordic nRF Connect SDK NFC feature support](https://github.com/nrfconnect/sdk-nrf/blob/main/doc/nrf/releases_and_maturity/software_maturity.rst)
- [Nordic NFC System OFF wake sample](https://github.com/nrfconnect/sdk-nrf/blob/main/samples/nfc/system_off/src/main.c)
- [Nordic general power optimization guidance](https://github.com/nrfconnect/sdk-nrf/blob/main/doc/nrf/test_and_optimize/optimizing/power_general.rst)
- [PuttTrack signed staged OTA decision](../adr/ADR-012-signed-staged-ota.md)
