# ESP32-C3 + PN532 reader bring-up

## Status

The powered reader-side path passed its first bench bring-up on 2026-09-01/02.
This proves ESP32-C3-to-PN532 SPI operation and repeatable NFC-A/Type 2 Tag
selection. It does not yet prove a read from an nRF54L15 NFC target, NFC field
wake, useful installed range, metal tolerance or production identity security.

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
`service_uri_ok=false`. This stricter parser passed a PlatformIO build on
2026-09-03 but has not replaced the physically exercised reader image. The RF
UID is retained for diagnostics but is not authoritative PuttTrack identity.
Plain NDEF can be copied and therefore does not authorize provisioning,
reassignment, secrets or firmware changes.

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

1. Write and read a known NTAG213 Text/URI NDEF payload.
2. Repeat cold-start and 0/10/20/30/40 mm distance/orientation sweeps away from
   and near representative metal.
3. Read the actual nRF54L15 Tag/XIAO payload through the external 13.56 MHz loop.
4. Correlate PN532 field presence with nRF54L15 field-on/field-off counters.
5. Prove System OFF field wake separately; a powered read is not wake evidence.
6. Measure field-present and wake/service energy before adopting the path.
