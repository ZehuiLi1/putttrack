# nRF54L15 Tag System OFF and battery validation

**Status:** physical pass on 2026-09-03 with confirmed firmware `0.1.17`

## Established result

The assembled CR2032-powered research ball passed an explicit NFC cold-wake
cycle without DAPLink:

1. encrypted BLE preflight locked device ID `f383571202836e6f`, verified NFC
   health and confirmed that no reader field was present;
2. custom mcumgr command `23` acknowledged a 2-second delayed System OFF;
3. BLE remained unavailable for more than 60 seconds after the delay;
4. approaching the ESP32-C3/PN532 caused the nRF54L15 to reset from System OFF;
5. the reader strictly decoded
   `putttrack://service/tag/f383571202836e6f?fw=0.1.17` and passed 50
   consecutive reads;
6. encrypted status reported `nfc_system_off_wake=true`, one complete NDEF read,
   healthy sensors and zero sensor, NFC, advertising or power-management errors;
7. the boot ID changed from `ae42b6ce63db585a` before power-off to
   `eab45817668ee95c` after NFC wake;
8. MCUboot still reported `0.1.17` active and confirmed, with `0.1.16` retained
   as the inactive image.

The application reads the nRF reset-reason register before Zephyr clears it and
exposes the dedicated NFC wake result. This distinguishes an NFC cold wake from
a reset, battery insertion or ordinary idle wake.

## Safety and product policy

System OFF is never entered automatically. It requires an encrypted BLE write,
an exact device-ID preflight, healthy NFC initialization and absence of an NFC
field. The checked-in host tool defaults to a read-only dry run; `--execute` is
required to issue the command. An NFC field arriving during the delay cancels
entry. The Reset button remains the physical recovery path.

This is appropriate for shipping, storage or explicit service state. It is not
yet the normal stationary gameplay state: System OFF resets the application and
only NFC wake has been validated. The existing idle policy remains responsible
for motion readiness through ADXL367 INT1.

## Communication boundary

The NFC endpoint is a read-only Type 2 NDEF service record, not a general
bidirectional application transport. The PN532 sends NFC-A/Type-2 commands and
the Tag returns the NDEF payload; `NFC_T2T_EVENT_DATA_READ` confirms completion
on the Tag. Configuration, status, power control and signed OTA remain
bidirectional encrypted BLE SMP operations. Firmware is not transferred by NFC.

## Battery observation

Firmware `0.1.17` adopts Nordic's NCS v3.4.0 nRF54L15 Tag fuel-gauge overlay:
SAADC samples VDD internally and the composite fuel gauge maps voltage through
a generic CR2032 open-circuit-voltage table. Physical readings were:

| State | Voltage | Reported estimate |
|---|---:|---:|
| active BLE/IMU | 2,912--2,923 mV | 66--71% |
| idle/light load | 2,936--2,957 mV | 75--82% |

The load-dependent rebound is expected for a coin cell and demonstrates why
the percentage is explicitly reported as `battery_soc_estimated=true`.
`battery_voltage_mv`, sample validity and the underlying error code remain the
primary diagnostics. This is enough for coarse low-battery policy after
temperature/load characterization; it is not a precision state-of-charge or
remaining-runtime claim.

## Still open

- whole-board current in active, idle, NFC sense, field-present and System OFF;
- CR2032 pulse droop across temperature and cell age;
- final low-battery warning/recovery thresholds;
- antenna range/orientation and instrumented 13.56 MHz tuning;
- repeated cold-wake soak and long-duration storage test.

Nordic documents System OFF NFC sensing as an nRF54L15 wake source. Current
measurement on the Tag requires the documented supply-current measurement
path and suitable instrumentation; behavior and voltage telemetry do not prove
current consumption or battery life.

Primary sources:

- [Nordic nRF54L15 System OFF](https://docs.nordicsemi.com/r/bundle/ps_nrf54l15/page/pmu.html-unique_1139880052)
- [Nordic nRF54L15 reset reasons](https://docs.nordicsemi.com/r/bundle/ps_nrf54l15/page/chapters/power-and-clock/reset/doc/reset.html-register.resetreas)
- [Nordic nRF54L15 Tag power supply](https://docs.nordicsemi.com/r/bundle/ug_nrf54l15_tag/page/ug/nrf54l15_tag/power_supply.html)
- [Nordic nRF54L15 Tag current measurement](https://docs.nordicsemi.com/r/bundle/ug_nrf54l15_tag/page/ug/nrf54l15_tag/measure_ampmeter.html)
