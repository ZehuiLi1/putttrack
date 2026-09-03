# PuttTrack nRF54L15 Tag application

This is the repository-owned no-CS Ball firmware baseline. It keeps the proven
signed MCUboot + encrypted BLE SMP update path and adds raw Tag identity, health
and motion telemetry.

The custom GATT service is
`8f3a1000-6e7d-4b9a-a6e8-3f3f7d2c0001`:

- status, read/encrypted: `8f3a1001-6e7d-4b9a-a6e8-3f3f7d2c0001`;
- motion, read + notify/encrypted: `8f3a1002-6e7d-4b9a-a6e8-3f3f7d2c0001`.

Both records use little-endian binary protocol version 1. The Ball exports raw
generic measurements only. It does not contain player, hole or scoring rules.

The same data is available through encrypted custom mcumgr group `64` for the
XIAO USB HCI development bridge:

- command `0`: identity and health;
- command `1`: latest motion sample (compatibility/diagnostics);
- command `2`: latest 64-sample binary ring window encoded as hexadecimal text;
- command `3`: atomically freeze the latest 1024 samples (20.48 seconds);
- commands `4` through `19`: retrieve the 16 immutable 64-sample chunks from
  that frozen capture.

Confirmed firmware `0.1.17` provides three
remotely selectable power policies while preserving the signed OTA and
frozen-history protocol:

- `auto` (boot default): full 50 Hz dual-IMU capture while active, then enter
  idle after 30 seconds without measured motion;
- `research`: force ADXL367 and BMI270 to 100 Hz with the absolute-deadline
  50 Hz stream and 1024-sample history used for labelled experiments;
- `idle`: force the low-power wake-monitor path.

Idle disables both BMI270 paths, suspends SPI22, stops the motion stream and
places ADXL367 in hardware wake-up mode. The official board DTS omits the
interrupt property, but the official PCA20072 schematic routes ADXL367 INT1 as
`ADXL_IRQ` to nRF54L15 P0.03; the repository overlay declares that connection.
Referenced activity is established while still in measurement mode, INT1 maps
ACT only, and the MCU then waits on the GPIO event with no periodic sensor poll.
The 160 ms polling path remains only as a fail-safe if interrupt setup fails.
The ADXL367 wake timer remains at its reset-default approximately 12.5
samples/second for response time; no 181 nA sensor-current or board-battery-life
claim is made without measuring the actual build.

The active-to-idle detector uses a 0.3 m/s² ADXL367 sample-delta threshold plus
an independent 0.08 rad/s BMI270 gyro threshold. The acceleration threshold is
above every recorded stationary maximum (including CR2032 operation) while
remaining far below repeatedly measured handling/pickup changes. This prevents
isolated stationary sensor noise from restarting the 30-second idle timer.

Connectable advertising also follows the runtime state: active mode uses the
GAP fast-2 range (100–150 ms), while idle uses 2.0–2.5 seconds. Encrypted SMP
and OTA remain connectable in both states.

Connectable advertising uses delayed work with a 250 ms retry instead of a
single unchecked start attempt. This covers the documented transient
`-ENOMEM` condition while a previous BLE connection object is still being
recycled. Status exposes `adv_start_errors`; a nonzero value records recovered
start failures rather than silently leaving the Tag undiscoverable.

The physical `0.1.17` image is confirmed after battery-powered BLE OTA. It has
passed two repeatable ADXL367 INT1 wake/re-sleep cycles, extended idle without
false wakes, remote confirmation and a post-confirm reset/idle cycle. DAPLink
is therefore a commissioning and recovery tool, not part of ordinary
application updates or operation.

Firmware `0.1.17` advertises `PuttTrack-<first four DEVICE_ID bytes>` in its
scan response to distinguish multiple boards. This is only a selector: capture
must still lock the full encrypted `DEVICE_ID`.

Encrypted custom mcumgr writes select the policy: command `20` is `auto`, `21`
is `research`, `22` is `idle`, and NFC builds expose explicit System OFF command
`23`. Use:

```bash
python tools/set_tag_power_mode.py auto
python tools/set_tag_power_mode.py research
python tools/set_tag_power_mode.py idle
```

The status response reports the requested policy, current active/idle state,
transition count, actual stream/IMU rates, interrupt/wake-mode flags, BMI270 SPI
suspend state, power-management error count, measured VDD in millivolts and a
generic CR2032 OCV percentage explicitly labelled as estimated. The battery
overlay follows Nordic's current nRF54L15 Tag sample; it does not claim precise
state of charge, current consumption or remaining runtime.

Firmware `0.1.17` additionally detects per-sensor failure streaks, invalidates
capture history across recovery, makes at most three local recovery attempts
and permits only one quiet/disconnected warm reboot before quarantine. Its SMP
health contract is fail-closed in the host capture tools while remaining
compatible with confirmed `0.1.13`. See
[`NRF54L15_TAG_SENSOR_RECOVERY.md`](../../docs/hardware/NRF54L15_TAG_SENSOR_RECOVERY.md).

The full-rate path explicitly runs both IMUs at 100 Hz ODR and exports an
absolute-deadline 50 Hz stream. The mcumgr status response also reports the
configured ODR/range and per-boot ADXL367 acceleration, BMI270 acceleration and
BMI270 gyroscope clipping counters. The frozen history decouples the physical
action from slow/retried BLE management reads: every chunk carries one capture
ID and is rejected by the host if its ID, index, bounds or sequence continuity
does not match.

Build with the same private signing key used for first commissioning:

```bash
SIGNING_KEY=/absolute/private/key.pem \
scripts/nrf54l15_tag/build_tag_app.sh
```

The BLE OTA input is
`build/nrf54l15-tag-app/nrf54l15_tag_app/zephyr/zephyr.signed.bin`.

An optional NFC service variant keeps the default configuration
unchanged and applies the NFCT pin overlay consistently to MCUboot and the
application:

```bash
SIGNING_KEY=/absolute/private/key.pem \
scripts/nrf54l15_tag/build_tag_nfc_service.sh
```

It exposes a read-only
`putttrack://service/tag/<opaque-device-id>?fw=<version>` Type 2 Tag URI and
opens one 10-second fast connectable-BLE discovery window on each NFC field
rising edge. Keeping a reader continuously present cannot extend the window.
Encrypted mcumgr status exposes NFC setup/field state, complete-read count,
window state, open count, suppressed-repeat count and dedicated NFC reset
reason. The confirmed physical NFC variant implements an explicit System OFF
experiment; automatic power policies never enter it. NFC field presence is not
authentication, and the variant does not replace BLE SMP or signed OTA.

The host command is dry-run by default and locks the full device ID. Add
`--execute` only after moving the NFC reader away:

```bash
python tools/enter_tag_system_off.py \
  --ble-address DA:88:62:A1:D3:40 --address-type random \
  --confirm-device-id f383571202836e6f
```

The external loop and C17/C19 matching network must pass the checks in
[`NRF54L15_TAG_NFC.md`](../../docs/hardware/NRF54L15_TAG_NFC.md).

Capture and inspect a stationary window through the XIAO adapter:

```bash
python tools/capture_tag_smp.py \
  --mode frozen --label stationary \
  --expected-device-id f383571202836e6f \
  --output runs/tag-stationary.jsonl
python tools/analyze_tag_capture.py runs/tag-stationary.jsonl
```

Select `research` before collecting a labelled full-rate episode. In `auto`,
the active ring is cleared on wake so a frozen record never mixes idle timing
with 50 Hz samples; it can initially contain fewer than 1024 samples.

For confirmed `0.1.17`, prefer `--ble-address`, the correct `--address-type`
and the expected full device ID. For legacy same-name images, keep other Tags off or pass
`--ble-address` and the correct `--address-type`. See
[`TAG_MULTI_DEVICE_IDENTITY.md`](../../docs/hardware/TAG_MULTI_DEVICE_IDENTITY.md).

`--mode snapshot` remains available for firmware `0.1.2` and older, but it is a
low-rate diagnostic path and must not be used for impact/rolling datasets.
