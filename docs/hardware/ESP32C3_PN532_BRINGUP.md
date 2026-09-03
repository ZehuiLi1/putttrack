# ESP32-C3 + PN532 reader bring-up

## Status

The powered reader path passed end-to-end through the assembled nRF54L15
research ball on 2026-09-03. This proves ESP32-C3-to-PN532 SPI, repeatable
NFC-A/Type 2 selection, strict PuttTrack URI decoding and correlation with the
nRF54L15 field/service-window telemetry. It does not prove System OFF wake,
useful installed range, final antenna tuning, metal tolerance or production
identity security.

## Bench configuration

| Item | Configuration |
|---|---|
| Reader controller | AirM2M CORE ESP32-C3 |
| Reader IC/module | PN532 V3-style module, powered at 3.3 V |
| PlatformIO board | `airm2m_core_esp32c3` |
| Framework | Arduino through `platformio/espressif32@6.13.0` |
| PN532 library | `adafruit/Adafruit PN532@1.3.4` |
| SPI mapping | SCK GPIO6, MISO GPIO10, MOSI GPIO3, SS GPIO2 |
| Host link | ESP32-C3 native USB Serial/JTAG with USB CDC application output |

GPIO2 is an ESP32-C3 strapping pin. The firmware drives SS high before starting
SPI, but application code cannot protect the earlier reset-sampling interval.
Use an approximately 10 kOhm pull-up to 3.3 V if the module/carrier does not
already provide a suitable idle level, and include repeated cold-start tests in
the hardware gate.

## Observed evidence

After correcting the PN532 interface switch from a non-SPI position to SPI,
the flashed firmware reported:

```json
{"event":"boot","app":"putttrack-pn532-reader"}
{"event":"spi_config","sck":6,"miso":10,"mosi":3,"ss":2}
{"event":"pn532_ready","chip":50,"firmware_major":1,"firmware_minor":6}
{"event":"scan_ready","technology":"NFC-A"}
```

Two separate NFC-A targets were exercised without publishing their raw UIDs:

| Target | Result |
|---|---|
| Non-Type-2 NFC-A card | at least 292 contiguous UID selections; Type 2 capability-container read correctly rejected |
| Blank NTAG213 | at least 344 contiguous UID selections; Type 2 container parsed and empty NDEF message reported |

The counters exceeded the firmware's 50-read stability target. No `scan_miss`
occurred in the retained observation windows. The blank NTAG result validates
the empty-message boundary, not Text/URI payload extraction.

The assembled nRF54L15 research ball then passed the strict URI path using its
26 mm, 1.0 uH loop and provisional C17/C19 = 220 pF network:

```json
{"event":"nfc_tag","consecutive_reads":50,"stable_target":50,"ndef_ok":true,"type2_advertised_bytes":992,"type2_loaded_bytes":60,"ndef_uri":"putttrack://service/tag/f383571202836e6f?fw=0.1.16","service_uri_ok":true,"device_id":"f383571202836e6f","firmware_version":"0.1.16"}
{"event":"stability_pass","reads":50}
```

The approximately 5 mm, parallel-loop placement continued well beyond the
50-read gate. Moving the reader away produced `tag_removed`; contemporaneous
encrypted Tag status showed 11 field-on and 11 field-off events. Raw RF UID is
omitted because it is diagnostic and non-authoritative.

## Firmware contract

The checked-in reader emits line-delimited JSON and supports both bring-up and
the repository's current nRF54L15 service identity formats:

- NFC Forum well-known Text Record containing `BALL_ID=PT-B001`;
- NFC Forum well-known URI Record containing
  `putttrack://service/tag/<opaque-device-id>?fw=<version>`.

For the URI form, the current build strictly requires an even-length 1–16 byte
hexadecimal `device_id` and a bounded `fw` value, normalizes the device ID and
emits `service_uri_ok=true`. Malformed PuttTrack service URIs fail explicitly;
ordinary non-PuttTrack URI records remain readable but emit
`service_uri_ok=false`. This stricter parser passed both the PlatformIO build
and physical nRF54L15 read on 2026-09-03. The RF
UID is retained for diagnostics but is not authoritative PuttTrack identity.
Plain NDEF can be copied and therefore does not authorize provisioning,
reassignment, secrets or firmware changes.

The nRF emulator advertises 992 bytes even though this service NDEF needs only
60 bytes. The reader therefore loads Type 2 pages on demand and bounds the
individual TLV/message to `PT_MAX_NDEF_BYTES`; it does not allocate or read the
entire advertised area on every scan.

## Reproduction

Build, upload and monitor from the repository root:

```powershell
pio run -d firmware/esp32c3_pn532_reader
pio run -d firmware/esp32c3_pn532_reader -t upload --upload-port COM3
pio device monitor -d firmware/esp32c3_pn532_reader --port COM3
```

The COM port is host-specific. The PN532 module must be in SPI mode before
power-up. IRQ and RSTO were not connected for this test.

## Remaining gates

1. Repeat cold-start and 0/10/20/30/40 mm distance/orientation sweeps away from
   and near representative metal.
2. Measure/retune the provisional 1.0 uH plus 220 pF/220 pF network in the final
   mechanical, battery and nearby-material stack.
3. Prove System OFF field wake separately; a powered read is not wake evidence.
4. Measure field-present and wake/service energy before adopting the path.
