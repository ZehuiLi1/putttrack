# nRF54L15 Tag + DAPLink bring-up

## Scope

This is the safe first-programming path for the Nordic nRF54L15 Tag through an
external CMSIS-DAP/DAPLink probe. It is separate from the Bbo/DK NCS v3.0.2
baseline.

## Important version split

- Bbo/DK comparison: keep NCS `v3.0.2` and
  `nrf54l15dk/nrf54l15/cpuapp` unchanged.
- Nordic Tag: use NCS `v3.4.0` or a later release that contains the
  `nrf54l15tag/nrf54l15/cpuapp` board definition.

Do not build Tag firmware with the DK board target. The SoC is the same, but the
board peripherals, sensors, antenna switch and pin assignments are not.

## Required wiring

Connect only these signals from the DAPLink probe to the Tag's documented SWD
test points/header:

| Probe | Tag | Note |
|---|---|---|
| VTref / VCC sense | Tag I/O supply | Voltage reference; do not assume it powers the Tag |
| GND | GND | Common ground is mandatory |
| SWDIO | SWDIO | Data |
| SWCLK | SWCLK | Clock |
| nRESET | nRESET | Strongly recommended for recovery/connect-under-reset |

Before connecting, measure the Tag target voltage and confirm the DAPLink I/O
level is compatible. Do not connect a probe power output when the Tag is already
powered unless the probe documentation explicitly permits that arrangement.
Start with a low SWD clock such as 1 MHz.

## Host tool choice

Use `probe-rs` for the first DAPLink attempt. Current probe-rs releases support
DAPLink and nRF54L15, including nRF54L unlock handling. Do not make pyOCD the
primary flashing path: there is a current reproducible nRF54L15 programming
failure report even though attach succeeds.

Install a current probe-rs release (at least the release that includes nRF54L15
support and unlock handling), then run the read-only preflight:

```bash
scripts/nrf54l15_tag/daplink_preflight.sh
```

The first connected setup was identified as:

- probe: `c251:f001:LU_2022_8888` (`CMSIS-DAP_LU`);
- probe-rs target: `nRF54L15`;
- read-only PART value at `0x00FFC31C`: `0x00054B15`.

This confirms the host-to-probe USB path and probe-to-Tag SWD path without
erasing or programming the Tag.

For the signed BLE update design that follows first commissioning, see
[`NRF54L15_TAG_OTA_BASELINE.md`](NRF54L15_TAG_OTA_BASELINE.md).

## Build

Run from an activated NCS environment that contains Tag board support:

```bash
west build --sysbuild -p always \
  -b nrf54l15tag/nrf54l15/cpuapp \
  nrf/samples/bluetooth/channel_sounding_ras_reflector \
  -d build/tag_ras_reflector
```

Locate the final merged HEX rather than guessing which child image to flash:

```bash
find build/tag_ras_reflector -name merged.hex -o -name zephyr.hex
```

For a sysbuild output, prefer the top-level merged image reported by the build.
Record its SHA-256 before programming.

## First flash

The repository helper is dry-run by default and refuses to select a probe
implicitly:

```bash
scripts/nrf54l15_tag/daplink_flash.sh \
  --probe '<selector from probe-rs list>' \
  --firmware /absolute/path/to/merged.hex
```

Review the printed command. To execute it:

```bash
scripts/nrf54l15_tag/daplink_flash.sh \
  --probe '<selector from probe-rs list>' \
  --firmware /absolute/path/to/merged.hex \
  --yes
```

The helper requests read-back verification. Do not use mass erase or recovery
on the first attempt. Those operations can destroy factory firmware,
provisioning or calibration data. If ordinary programming reports protection,
stop and preserve the complete log before considering recovery.

## Evidence to retain

- Tag label/hardware revision and clear photos of both sides;
- DAPLink product, firmware version and probe serial;
- measured target voltage and wiring photo;
- NCS version and sdk-nrf commit;
- board target and complete build command;
- final HEX SHA-256;
- probe-rs version, program/verify log and first boot log.
