# XIAO nRF54L15 Sense bench firmware

Standalone commissioning image for the Seeed XIAO nRF54L15 **Sense**. Build
against NCS v3.4.0 using board `xiao_nrf54l15/nrf54l15/cpuapp`; the SDK board
already defines the Sense IMU at I2C30 address 0x6a and its power regulator.
The SDK's `st,lsm6dsl` driver is used for the onboard LSM6DS3TR-C.

- Accelerometer ±16 g and gyroscope ±2000 degrees/s, both configured at 104 Hz.
- Application reads at 50 Hz, prints a diagnostic sample at 10 Hz. These reads
  are not FIFO/data-ready synchronized acquisition and are not a research dataset.
- Serial JSON at 115200 baud via onboard CMSIS-DAP UART. Acceleration values are
  micro-m/s² and angular velocity values are micro-rad/s: divide each by 1e6.
- Once-per-second status includes device ID, sample/error counts and NFC field
  on/off/read counters. A failed fetch does not emit an old motion sample.
- `xiao02` explicitly enables the IMU/MIC supply in the application after an
  off interval, waits for power to settle, checks WHO_AM_I (0x6a), and initializes
  the deferred sensor driver. Status includes `imu_init_error` and `imu_chip_id`;
  zero runtime read errors alone do not establish sensor health.
- BLE name `PT-XIAO-<first four ID bytes>`; dedicated diagnostic service
  `8f3a2000-6e7d-4b9a-a6e8-3f3f7d2c0001`, read-only JSON characteristic
  `8f3a2001-6e7d-4b9a-a6e8-3f3f7d2c0001` (bench diagnostics, no encryption).
- NFC Type 2 URI `putttrack://service/tag/<device-id>?fw=xiao02`, compatible
  with the PN532 reader. NFC uses P1.02/NFC1 and P1.03/NFC2. Verify the actual
  antenna and tuning network before attaching; a successful initialization is
  not proof of RF operation. Field counters are reported outside NFC callbacks.

This image is for USB-powered bench validation. It does not implement the old
Ball's ADXL367/BMI270 protocol, pickup detector, battery estimation, low-power
policy or signed OTA. Keep the old Ball as the comparison baseline.

## Build and program

In an activated NCS v3.4.0 terminal, from the repository root:

```sh
west build --sysbuild -p always -b xiao_nrf54l15/nrf54l15/cpuapp \
  firmware/xiao_nrf54l15_sense_bringup -d build/xiao-sense-bringup
```

Confirm the intended probe with `probe-rs list`. Program only the XIAO's
explicit probe ID; the commissioning session used `2886:0066:D5F7A850`:

```sh
probe-rs download --chip nRF54L15 --probe 2886:0066:D5F7A850 --verify \
  build/xiao-sense-bringup/xiao_nrf54l15_sense_bringup/zephyr/zephyr.elf
probe-rs reset --chip nRF54L15 --probe 2886:0066:D5F7A850
```

## Validation

Check serial `imu_ready=true`, `sensor_errors=0`, increasing samples, and
approximately 9.81 m/s² total acceleration at rest. Read the BLE diagnostic
characteristic and match its full device ID to serial. Disconnect and reconnect
to verify advertising recovery. With a connected NFC loop and powered PN532,
check field/read counters and decoded identity, then repeat placement trials.

## Physical commissioning — 2026-09-11

- Probe `D5F7A850`, PART readback `0x00054b15`, device ID `4d53cd7b5c288607`.
- Before programming, backed up the 1,560,576-byte application RRAM region to
  `runs/xiao_D5F7A850_before_bringup.bin`. This is not a backup of UICR or the
  separate SAMD11 debug-probe firmware.
- Final image programmed and readback-verified by probe-rs. ELF SHA-256:
  `0d7ba7245069db91190e7ede1184e0d8458041febf162502455ac3d6a9d8bea7`.
- IMU initialized; 15-second capture produced 150 motion lines and 15 status
  lines, with zero sensor read errors and no dropped/malformed motion lines.
  Two Bluetooth stack warning lines were retained separately from JSON data.
- Twelve complete BLE JSON status reads across two connections passed exact
  schema and full device identity checks. ATT long reads freeze a response at
  offset zero so updates cannot splice two different status records together.
- Observed acceleration norm median 10.214 m/s², range 9.786–11.211 m/s².
  Placement/motion was not controlled; these values demonstrate live data,
  not sensor accuracy or completed calibration. Six-face accelerometer and
  stationary gyro bias calibration remain outstanding.
- NFC library initialization returned zero. User confirmed no NFC loop is
  attached: RF reads, placement reliability and wake behavior are untested.
- Evidence: `runs/xiao_sense_serial_validation.jsonl`,
  `runs/xiao_sense_ble_validation.json`,
  `runs/xiao_sense_validation_summary.json`, and
  `runs/xiao_sense_firmware_manifest.json`.

## Startup repair and stationary check — 2026-09-12

On a subsequent USB-powered startup, `xiao01` reported `imu_ready=false` and
zero samples over serial and BLE; an MCU reset restored operation. The previous
warm-reset commissioning pass did not establish cold-start reliability.

`xiao02` removes automatic IMU driver initialization and the duplicate GPIO hog.
It starts the IMU/MIC regulator off, waits 100 ms, explicitly enables it, waits
for supply settling, checks WHO_AM_I, then calls `device_init`. This targets the
observed startup dependency; it does not claim a measured rail timing diagnosis.
The underlying regulator's boot-on initialization path does not apply its
startup delay when it regards the rail as already enabled.

Three MCU resets with application-controlled sensor power sequencing passed;
all reported WHO_AM_I 0x6a, successful initialization and zero sensor read errors.
Twelve complete BLE status reads across two connections also passed. Firmware
hash is retained in `runs/xiao_sense_firmware_manifest_xiao02.json`.

The user confirmed a stationary placement. After initial samples were excluded,
228 samples gave mean angular velocity [0.550, -2.029, 0.315] degrees/s, standard
deviation [0.580, 0.187, 0.706] degrees/s, and mean acceleration norm
10.142 m/s². These are uncorrected observations, not calibration coefficients;
six-face scale/offset calibration and repeated stationary gyro measurements
remain necessary. No automatic bias correction was applied.
Evidence: `runs/xiao_startup_20260912_105526_summary.json` and its raw JSONL,
plus `runs/xiao_sense_ble_validation_xiao02.json`.
