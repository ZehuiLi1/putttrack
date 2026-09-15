# XIAO nRF54L15 Sense Tag port

This board uses the same application (`main.c`, `pickup_shadow_v0.c`) as the Nordic
PCA20072 Tag, with a separate LSM6DS3TR-C backend, board overlay and configuration.
The bring-up demo in `../xiao_nrf54l15_sense_bringup` is a separate diagnostic image;
it does not implement the full Tag service or signed OTA.

## Hardware and data contract

- Board: `xiao_nrf54l15/nrf54l15/cpuapp`; tested Sense probe serial `D5F7A850`.
- Full hardware ID: `4d53cd7b5c288607`. Advertised name: `PuttTrack-4d53cd7b`.
- LSM6DS3TR-C: I2C30, address 0x6a, SDA P0.04, SCL P0.03, INT1 P0.02,
  supply enable P0.01. The application owns sensor register access and power sequencing.
- Active: accel 104 Hz / ±16 g; gyro 104 Hz / ±2000 dps. The application exports 50 Hz.
- Idle: accel 26 Hz / ±2 g, gyro off, latched slope-motion interrupt on INT1.
  This is not the ADXL367's low-power wake mode, and equivalent current consumption
  has not been demonstrated.
- VBAT: AIN7/P1.14, 2:1 divider, P1.15 enables the measurement circuit only while sampling.
  Voltage-derived Li-ion SOC is a **generic estimate**, not a calibrated gauge. The
  charger can drive the battery rail when powered by USB without a battery attached;
  `battery_presence_known=false` means voltage/SOC cannot prove a battery is installed.

### NFCT antenna wiring

The XIAO exposes the nRF54L15 differential NFC pins only as small back-side test
points: N1/TP19 is `P1.02/NFC1`, and N2/TP20 is `P1.03/NFC2`. The board has no
NFC tuning capacitors.

**Current XIAO bench baseline (user observation, 2026-09-15):** leave the two
external tuning capacitors disconnected. The user tested different ball
orientations and reported that each eventually reached stable NFC reading.
Preserve this working configuration for further angle/range measurements.
This observation does not establish immediate acquisition at every angle or
an optimum matching network for other coils/readers.

System OFF follow-up (2026-09-15): the user also observed failed NFC-wake
verification when USB was supplied by a power bank. The capture includes new
boots with Zephyr reset flags 32 (`RESET_DEBUG`) and 0 (no reported cause), as
well as successful NFC wakes with flag 128. These are not all one failure mode.
Changing the USB source does not isolate the onboard debugger: the Seeed
[Sense schematic](https://files.seeedstudio.com/wiki/XIAO_nRF54L15/Getting_Start/nRF54L15_Sense_Schematic.pdf)
shows a USB-powered SAMD11 supply and an onboard SWD connection to the nRF54L15.
Its involvement is a hypothesis, not established from the reset flags alone.
USB/power-bank tests must not be treated as debugger-isolated tests; a future
BAT-powered, USB-disconnected comparison is needed, together with checking
power continuity and retaining per-attempt wake evidence. Evidence:
`runs/nfc_web_20260915_025112.recognition.jsonl`.

The following two-220 pF C0G/NP0 network is a **historical PCA20072 reference**
for the 26 mm, approximately 1.0 uH research loop, not a required XIAO wiring step:

```text
                         26 mm / about 1.0 uH loop
                    +------------- coil -------------+
                    |                                |
XIAO N1 / TP19 -----+                                +----- XIAO N2 / TP20
                    |                                |
                 220 pF                           220 pF
                 C0G/NP0                          C0G/NP0
                    |                                |
                    +------------ XIAO GND ---------+
```

The capacitors are not polarized. Leaded C0G/NP0 parts may be used for the bench
prototype so no 0402 soldering is required: join one capacitor to each NFC pad,
join their other leads together, and run that common point to the XIAO header GND
or back-side TP3. Keep the N1/N2 leads short. Do not place the loop directly
against the battery or another metal surface. The 220 pF values reproduce the
working PCA20072 starting network; final values still require testing in the
assembled ball at 13.56 MHz.

Firmware 0.2.6 enables a read/write Type 4 service, explicit System OFF
experiment and a direct owner-migration command.
It never enters System OFF automatically. The identity-locked management command
starts a two-second guarded delay; after BLE disappears, a PN532 field must wake
the XIAO and read `putttrack://service/tag/4d53cd7b5c288607?fw=0.2.6`.

Protocol 1 is the original ADXL367 + BMI270 Tag. Protocol 2 is the single-IMU XIAO.
The encrypted GATT UUIDs, packet sizes, group 64 management commands, units and
history layout are unchanged. In protocol 2 the legacy `adxl_*` and `bmi_accel_*`
slots contain the **same LSM6DS3TR-C acceleration sample**, and `bmi_gyro_*` is the
LSM gyro. Their flags and error bits refer to logical channels, not two chips.
SMP and host exports expose `sensor_layout="lsm6ds3tr-c-single"`. Capture sessions
reject mixed protocols, including history chunks. The legacy dual-sensor dataset
packager rejects protocol 2 instead of silently applying ADXL clipping limits or
mixing XIAO recordings into the old training dataset.

## Current device state (2026-09-14)

The physical XIAO is running signed firmware 0.2.6, uploaded, test-booted,
confirmed and reboot-verified entirely through the Mac native CoreBluetooth path.
The upload resumed from offset 53,248 after one lost BLE response instead of
restarting the image. Earlier nRF52840 HCI validation covered rollback and
bad-signature rejection; that controller is now a recovery tool rather than a
routine OTA dependency.

The final readback reports device ID `4d53cd7b5c288607`, firmware 0.2.6,
`sensor_health="healthy"`, zero sensor errors/faults/recovery attempts,
`capture_safe=true`, BLE security level 2 and `power_policy="auto"`. Automatic
idle entry, physical motion-interrupt wake and a complete USB power-cycle cold
start have been verified. Firmware 0.2.6 reports `nfc_enabled=true`,
`nfc_setup_error=0`, `nfc_migration_transport="ndef_type4_command"` and
`system_off_supported=true` after a confirmed reboot.
Battery-only cold start still needs a dedicated test. With the tuned external
antenna attached, the PN532 read the Type 4 identity, delivered one direct
migration command and woke the XIAO from System OFF.

Firmware 0.2.4 increased the persistent BLE bond capacity from one to two. The
validated nRF52840 HCI controller and Mac native CoreBluetooth host are both bonded.
Firmware 0.2.6 replaces the timing gesture with a single writable Type 4 NDEF
command containing the exact device ID and a fresh 16-byte nonce. A valid command
clears the old bonds and opens a 60-second fast BLE takeover window; the last
nonce is rejected if repeated. The signed image is installed and confirmed. RF
validation passed through the PN532, followed by a new encrypted Mac BLE claim.

## Capabilities and validation

| Capability | Implementation | Hardware evidence / remaining check |
|---|---|---|
| Stable identity, encrypted status / motion | Shared Tag implementation | Full ID and encrypted status read verified |
| 50 Hz notifications | Single-IMU backend | 301 consecutive valid frames, no sequence gap |
| Ring history / frozen chunks | Shared 1024-sample history | 329 frozen samples retrieved and decoded |
| Auto / research / forced idle policies | Shared policy plus LSM configuration | Forced idle, research resume, automatic idle and physical motion wake verified |
| Sensor fault handling | Shared bounded retries / health / recovery, LSM power cycle | Recovery path builds; injected-fault test pending |
| Pickup shadow | Shared non-authoritative detector | Runs on device; accuracy unvalidated for this IMU/board |
| Battery rail / estimated SOC | XIAO divider and generic Li-ion OCV curve | ADC returned a voltage; battery presence, SOC accuracy and current consumption unvalidated |
| NFC service record / bounded BLE discovery | Writable Type 4 NDEF identity service | PN532 read UID `5FD9D8FC248EBB` and the exact 0.2.6 service URI |
| NFC-authorized computer migration | Exact-ID NDEF command, fresh nonce, bond reset and 60-second BLE window | RF command, bond reset and encrypted Mac reclaim passed |
| NFC System OFF experiment | Shared explicit management command | No BLE advertisements for 12 seconds in System OFF; PN532 wake set reset reason 128 and `nfc_system_off_wake=true` |
| Signed BLE OTA / trial / rollback | MCUboot, two application slots, separate XIAO signing key | 0.2.6 full upload/test/confirm/reboot completed through Mac native SMP; earlier negative paths verified by HCI |
| Persistent BLE pairing | NVS settings outside OTA slots, loaded before advertising | nRF52840 HCI bond re-encryption verified across all OTA resets |
| Mac native BLE | CoreBluetooth GATT/SMP path, resumable upload and live notification capture | Full 212,328-byte 0.2.6 OTA and confirmed reboot verified |

Initial motion/history evidence is in `runs/xiao_full_validation_020.json`. The
completed 0.2.2 cycle is recorded in `runs/xiao_ota_validation_022.json`; the
installed 0.2.3 NFC candidate is recorded in `runs/xiao_nfc_candidate_023.json`;
the native Mac pairing and OTA-management transition is recorded in
`runs/xiao_mac_native_ble_024.json`; the first full native upload is recorded in
`runs/xiao_mac_native_ota_025.json`.
The full-cycle record supersedes the partial evidence in
`runs/xiao_ota_upload_021.json`.

## Build and install

Use NCS v3.4.0 and an **XIAO-specific** Ed25519 key outside this repository. Do not
reuse the original Tag key: otherwise a validly signed image for the wrong board
could be accepted. The local lab key is at
`/Users/pp/Documents/PuttTrackKeys/lab_xiao_sense/mcuboot-ed25519-lab.pem`.
Back it up securely; losing it prevents signing updates for this bootloader.

```sh
SIGNING_KEY=/absolute/path/to/xiao-ed25519.pem bash scripts/nrf54l15_tag/build_xiao_sense.sh
```

Outputs in `build/xiao-sense-tag/`:

- `first_install.hex`: MCUboot plus signed application, for initial SWD installation.
- `nrf54l15_tag_app/zephyr/zephyr.signed.bin`: application OTA payload.

The application and signing versions are both configured in `xiao_sense.conf` and
must be advanced together. The 68 KiB bootloader, two 696 KiB slots and 64 KiB
settings partition match the established Tag OTA layout. Routine OTA never writes
the settings partition. Ordinary first-install flashing is **not** a factory reset
of the inactive slot or settings. In this migration an old swap trailer caused
MCUboot to restore an older application after a successful SWD verification.
For a deliberate lab baseline reset, initialize both application slots (including
their trailers), merge the bootloader and signed primary image, and leave the
settings partition at 0x16d000 untouched. The generated local artifact is
`build/xiao-sense-tag-v0.2.0/baseline_reset_slots.hex`. Verify the active image hash
**after reboot**, not just the SWD write. Do not use this reset image for routine OTA.

```sh
probe-rs download --chip nRF54L15 --probe 2886:0066:D5F7A850 --verify --binary-format hex build/xiao-sense-tag/first_install.hex
probe-rs reset --chip nRF54L15 --probe 2886:0066:D5F7A850
```

The original bring-up backup is `runs/xiao_D5F7A850_before_bringup.bin` (application
RRAM only, not UICR or the SAMD11 USB bridge). The full Tag firmware reports over
BLE; the enumerated USB UART no longer prints the bring-up JSON stream.

## BLE management and OTA

Routine OTA uses the native BLE adapter through `tools/manage_tag_ble.py`. The
XIAO BLE nRF52840 Sense running Zephyr HCI UART remains available for low-level
recovery. The validated recovery controller is serial
`B3589A7EF1E63E51` on `/dev/cu.usbmodem1101`; the target uses random address
`D8:3E:E7:05:33:DA`. Keep `runs/xiao_nrf52840_hci_bonds.json` to reuse the bond
after target resets. The native Mac path below remains useful for the UI tools,
but its CoreBluetooth pairing cache is less observable during OTA testing.

```sh
nrfutil mcu-manager ble --hci-serial-port /dev/cu.usbmodem1101 --timeout 30 \
  image-list --address D8:3E:E7:05:33:DA --address-type random \
  --device-db runs/xiao_nrf52840_hci_bonds.json
```

Install project hardware extras (`python -m pip install -e '.[hardware]'`).
All commands first read the **encrypted full hardware ID** and check it before
writing settings or images. An optional `--address` accepts a macOS peripheral UUID
(or a BLE address on other platforms); it does not replace the hardware-ID check.
The macOS lookup can recover a cached peripheral even when the OS retains a link
and it stops advertising. Pairing is encrypted Just Works, as in the original lab
Tag; this is not an authenticated/MITM-resistant commissioning workflow.

```sh
python tools/manage_tag_ble.py --device-id 4d53cd7b5c288607 status
python tools/manage_tag_ble.py --device-id 4d53cd7b5c288607 research
python tools/manage_tag_ble.py --device-id 4d53cd7b5c288607 idle
python tools/manage_tag_ble.py --device-id 4d53cd7b5c288607 auto
python tools/manage_tag_ble.py --device-id 4d53cd7b5c288607 images
python tools/manage_tag_ble.py --device-id 4d53cd7b5c288607 upload build/xiao-sense-tag/nrf54l15_tag_app/zephyr/zephyr.signed.bin
python tools/manage_tag_ble.py --device-id 4d53cd7b5c288607 test IMAGE_HASH_FROM_IMAGES
python tools/manage_tag_ble.py --device-id 4d53cd7b5c288607 reset
```

After reconnecting, verify the expected version, healthy sensor status and the
**active** image hash. Confirm only that running image:

```sh
python tools/manage_tag_ble.py --device-id 4d53cd7b5c288607 confirm ACTIVE_IMAGE_HASH
```

Upload does not select an image, reboot or confirm automatically. Reset an
unconfirmed trial to test rollback. An upload-file SHA-256 identifies the transfer;
the `images` command returns the MCUboot TLV image hash (64-byte SHA-512 in this
Ed25519 NCS configuration), which is the hash used for test/confirm commands.

A pre-persistence test firmware can leave macOS with an obsolete bond. If macOS
reports “Peer removed pairing information”, forget that XIAO pairing once and
re-pair. The final firmware stores pairing keys in NVS; normal OTA/reboots should
not require forgetting it again. Do not erase all Bluetooth devices or turn off
system Bluetooth as a firmware-repair shortcut.

## Move ownership to another computer

Firmware 0.2.6 accepts one identity-locked Type 4 NDEF command through PN532.
The host generates a fresh random nonce; the Ball verifies the command version,
its complete hardware device ID and nonce encoding before clearing old BLE bonds.
The new computer then has 60 seconds of fast advertising in which to establish
its own encrypted bond.

On the new computer, connect its ESP32-C3/PN532 and run:

```sh
python tools/prepare_tag_migration.py \
  --device-id 4d53cd7b5c288607 \
  --port /dev/cu.usbmodem...
```

Keep the Ball on the PN532 while the tool reads its identity and writes the command.
The tool rejects another Ball or malformed service URI, then establishes and
verifies the new encrypted BLE connection.
This deliberately invalidates the old computer and nRF52840 bonds. Do not run it
during a field session. Until the XIAO antenna is attached and this command passes
physically, keep the nRF52840 recovery controller.

## Unified experiment UI

The field UI defaults to the Mac native BLE controller and automatically opens the
sole Espressif USB serial device as the PN532 reader. It displays BLE identity,
encryption, sensor health, runtime state, NFC reader readiness, consecutive NFC
reads and the parsed service URI on one page. Native capture subscribes directly
to the 50 Hz motion characteristic and preserves the device sequence/time marker,
operator GO acknowledgement, identity lock and final continuity checks.

```sh
./.venv/bin/python tools/run_field_capture_ui.py \
  --transport native \
  --expected-device-id 4d53cd7b5c288607 \
  --nfc-port auto
```

Use `--transport hci --hci-port /dev/cu.usbmodem...` only for recovery or explicit
controller comparison. The PN532 panel remains independent of the selected
BLE transport. An XIAO without its external tuned loop will leave the reader ready
but cannot produce a PuttTrack NFC identity.

## Temporary NFC read indicator (0.2.7)

The XIAO configuration enables `CONFIG_PUTTTRACK_NFC_READ_LED`. Its onboard
user LED (`led0`, active-low P2.00) lights for approximately 150 ms when the
Type 4 library reports `NFC_T4T_EVENT_NDEF_READ` (reading the last NDEF byte).
Repeated reads are limited to one flash per second. Workqueue handlers drive
the LED without blocking the NFCT callback; System OFF turns it off.

This indicates a tag-side NDEF read event, not just field detection, reader-side
CRC success, or a BLE connection. SMP status reports `nfc_read_led_enabled`,
`nfc_read_led_error`, and `nfc_read_led_pulses`. Disable this option for final
power measurements. Original Tag NFC firmware 0.1.21 also enables this feature,
using its own `led0` (blue, active-low P2.09).

## Sources

- [Seeed hardware and power guide](https://wiki.seeedstudio.com/xiao_nrf54l15_sense_getting_started/)
- [Seeed Sense schematic](https://files.seeedstudio.com/wiki/XIAO_nRF54L15/Getting_Start/nRF54L15_Sense_Schematic.pdf)
- [ST LSM6DS3TR-C datasheet](https://www.st.com/resource/en/datasheet/lsm6ds3tr-c.pdf)
- [Zephyr image management protocol](https://docs.zephyrproject.org/latest/services/device_mgmt/smp_groups/smp_group_1.html)
