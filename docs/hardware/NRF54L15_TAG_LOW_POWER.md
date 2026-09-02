# nRF54L15 Tag low-power baseline

## Scope

Firmware `0.1.13` is the confirmed adaptive-power baseline on the physical Tag.
It preserves MCUboot, signed BLE OTA, encrypted SMP, identity/health and
full-rate frozen history. Automatic idle, ADXL367 INT1 wake, repeated re-sleep,
confirmation and post-confirm reboot were exercised while powered from a
CR2032. This is a functional low-power validation, not a battery-life claim;
board-level current still has to be measured with a power profiler or current
meter.

## State model

| Policy/state | ADXL367 | BMI270 accel | BMI270 gyro | Motion stream | BLE advertising |
|---|---:|---:|---:|---:|---:|
| `research / active` | 100 Hz | 100 Hz | 100 Hz | 50 Hz | 100–150 ms |
| `auto / active` | 100 Hz | 100 Hz | 100 Hz | 50 Hz | 100–150 ms |
| `auto / idle` | wake-up mode / ACT INT1 | off | off | stopped | 2.0–2.5 s |
| `idle / idle` | wake-up mode / ACT INT1 | off | off | stopped | 2.0–2.5 s |

`auto` starts active. After 30 seconds without sufficient ADXL367 vector change
or BMI270 gyro activity it enters idle. Referenced activity is re-armed while
ADXL367 is still in measurement mode and allowed 160 ms to establish the
stationary reference. The firmware then maps ACT only to INT1, selects ADXL367
wake-up mode and blocks on the GPIO event instead of polling. The active ring is
cleared on wake so frozen history never combines an arbitrarily long idle
timestamp gap with 50 Hz data.

The upstream NCS v3.4.0 `nrf54l15tag` devicetree does not declare ADXL367 INT1,
but that omission is not the physical circuit. Nordic's official PCA20072
schematic shows ADXL367 U5 INT1 pin 5 on `ADXL_IRQ`, connected to nRF54L15
P0.03. The repository overlay supplies `int1-gpios = <&gpio0 3
GPIO_ACTIVE_HIGH>`. BMI270 INT1 remains on P1.04 but is not needed as the idle
wake source.

Version `0.1.13` intentionally leaves the ADXL367 `WAKEUP_RATE` field at its
reset-default approximately 12.5 samples/second to reduce motion-detection
latency. The datasheet's approximately 181 nA wake-up figure is specified at
1.5625 samples/second, not at this setting, and is a sensor-only value rather
than Tag board current. Slower 6.25/3.125/1.5625 sample/second variants should
be compared only after an inline-current setup is available, because their
lower current trades against up to 160/320/640 ms sampling intervals and can
delay or miss short ball motion.

## Remote control and observability

Encrypted custom mcumgr group 64 write commands are:

- 20: select `auto`;
- 21: select `research`;
- 22: select `idle`.

[`tools/set_tag_power_mode.py`](../../tools/set_tag_power_mode.py) applies a
policy and verifies the resulting status. Status reports policy, runtime state,
transition count, actual ODR/stream rates, idle timeout, wake polling interval,
interrupt/wake-mode flags, SPI suspend state, power-management errors,
configured advertising interval and whether battery telemetry is supported.

Battery telemetry is currently reported as unsupported. The SoC ADC exists,
but the official board description provides no verified coin-cell divider or
fuel-gauge channel. A percentage or millivolt value must not be inferred from
an unconnected ADC.

## v0.1.13 confirmed interrupt-wake baseline

The exact signed build has:

- signed BIN SHA-256:
  `a3332a3e05cb0ccfbf5ecfb943e42e7ff508ae21ea6b5290f606e0ffb6a92807`;
- first-install HEX SHA-256:
  `7d1ab95866134b940727f9188628cf24180155da92ddde225ec5687a9fd3a9a0`;
- MCUboot image digest:
  `ddededad6a34dda066d4f7471de4c1647ad2564a4b2856559c1f23a41aac40b18c5e6f0d12a28bb14254cd4983aee368fdf40ef8cd54e5af335ee57ececc223f`.

On physical device `f383571202836e6f`, powered by CR2032, it passed:

- signed BLE upload, digest match, unconfirmed test boot and rollback guard;
- automatic idle with `wake_poll_ms=0`, `wake_interrupt=true`,
  `adxl_wakeup_mode=true`, BMI270 at 0 Hz and SPI22 suspended;
- more than 80 seconds of initial idle without a false wake;
- two physical INT1 wake events, each restoring both 100 Hz IMUs, the 50 Hz
  stream, SPI22 and 100–150 ms advertising;
- two automatic returns to idle with transition counts progressing exactly
  `1 → 2 → 3 → 4 → 5` and no spontaneous extra transition;
- zero sensor, power-management, notification and advertising-start errors;
- remote image confirmation, reset with a new boot ID, and another successful
  automatic interrupt-idle transition.

Unconfirmed `0.1.12` proved the electrical interrupt path, but its second idle
cycle could re-enter active on stationary data because referenced activity was
re-armed after wake-up mode was selected. It was deliberately rejected and
rolled back. Version `0.1.13` establishes the reference in measurement mode,
waits two 12.5 Hz samples, maps ACT only, then selects wake-up mode.

## v0.1.11 confirmed battery baseline

The first CR2032 boot exposed a keep-awake threshold issue that external-power
tests did not reproduce consistently. A complete stationary battery-powered
record remained valid and gap-free at 50 Hz, but its ADXL367 sample-to-sample
delta crossed the former 0.15 m/s² keep-awake threshold five times in 20.46
seconds (maximum 0.182 m/s²). Those isolated noise events continually restarted
the 30-second idle timer even though the episode correctly analyzed as
stationary and BMI270 gyro stayed below 0.011 rad/s.

Across the repository's recorded stationary data, the largest ADXL367 delta is
below 0.3 m/s²; physically active handling and natural pickup records cross
0.3 m/s² repeatedly and also exercise the independent 0.08 rad/s gyro gate.
Firmware `0.1.11` therefore raises only the active keep-awake acceleration
threshold to 0.3 m/s². Idle wake remains the separately debounced 0.5 m/s²
condition.

The unconfirmed `0.1.10` test boot proved battery idle and slow-advertising SMP
access, but became undiscoverable after a later management connection closed.
The advertising worker had ignored `bt_le_adv_start()` errors and made no retry.
Zephyr documents `-ENOMEM` when a connectable advertiser is started before a
connection object is free. Version `0.1.11` uses delayable work, retries failed
starts after 250 ms, and exports `adv_start_errors` so a recovered transient is
observable. Pressing reset safely rolled the unconfirmed image back to
confirmed `0.1.9` and immediately restored BLE, independently confirming the
MCUboot recovery path.

The exact `0.1.11` build has:

- Flash: 180,336 / 696,176 bytes (25.90%);
- RAM: 207,063 / 262,144 bytes (78.99%);
- signed BIN SHA-256:
  `eaf1dccf463d9320f8d647d1c920b5977308c43e486db20a14eaac626e5e21cb`;
- first-install HEX SHA-256:
  `13d9ab96ec88eb4269cf02ee8b06f8cb0be8f5a118f683c54423faecda91e01e`;
- MCUboot image digest:
  `08d8686eae8a90277c2edcda9fbdfa1576f6fd0415dfe4bc63d2d0b5a20afce0ecfbea9f2de1300376c9ba4ce77660789b8d3c7b59c236a2097974daa2b67672`.

On the CR2032-powered physical Tag, the signed image passed:

- encrypted BLE upload from confirmed `0.1.9`, test selection and unconfirmed
  boot with boot ID `fa891facf20a5a30`;
- startup with both IMUs ready, 100 Hz sensor ODRs, a 50 Hz stream, fast
  advertising and zero sensor errors;
- automatic transition to idle, 12.5 Hz ADXL367, BMI270 off, stream stopped and
  1.0–1.2 second advertising;
- a complete 1024-sample/20.46-second idle diagnostic record with exact 50 Hz
  source timing before the transition, zero sequence gaps and full validity;
- six consecutive encrypted management connect/disconnect cycles while idle;
- physical motion wake to both 100 Hz IMUs, the 50 Hz stream and fast
  advertising, followed by an automatic return to idle;
- remote confirmation and reset, producing boot ID `3f0444cc602396d0` with
  `0.1.11` still active and confirmed;
- a post-confirm automatic idle transition and two more consecutive encrypted
  management reconnects in slow advertising;
- zero sensor errors and `adv_start_errors=0` throughout the accepted checks.

The retry path was not artificially fault-injected, so zero advertising-start
errors does not prove the transient itself was forced. It does show that the
previous disconnect/reconnect failure did not recur through the guarded OTA,
idle, wake, confirmation and reboot sequence. Firmware `0.1.11` therefore
replaces `0.1.9` as the confirmed physical baseline.

## v0.1.9 confirmed build and physical evidence

The final adaptive-advertising image built with:

- Flash: 180,248 / 696,176 bytes (25.89%);
- RAM: 207,024 / 262,144 bytes (78.97%);
- signed BIN SHA-256:
  `f9ee5819b0206c6e4523df658116c01b218b64af10654d6a3557b4bd061e9e01`;
- first-install HEX SHA-256:
  `fd8be0087a89131fe007ce84253279a1f87a786462a968307c5b71fb3166444c`.
- MCUboot image digest:
  `398dd5667d0eae7987346f60b88cd0c4a4f7f022853a05e75eac8ba310004a6e9ad0535458725b9f64b5d71d3e3dc7b12e952fdebf4dd1f60c6cbe175bf94a1b`.

On the physical Tag, the exact signed BIN passed:

- encrypted BLE upload and unconfirmed MCUboot test boot;
- startup in `auto / active` with both IMUs ready, zero sensor errors, 100 Hz
  sensor ODRs, a 50 Hz stream and 100–150 ms advertising;
- a complete research-mode frozen record of 1024 samples over 20.46 seconds at
  exactly 50 Hz, with zero sequence gaps, errors or clips;
- forced active/idle transitions with the reported hardware rates changing as
  specified in the table above;
- automatic idle after 30 seconds at rest;
- a fresh encrypted SMP and image-list connection while using 1.0–1.2 second
  idle advertising;
- physical motion wake from transition count 3 to 4, restoring both 100 Hz
  IMUs, the 50 Hz stream and fast advertising;
- a 792-sample, 15.82-second wake record with no gaps and full sensor validity;
- remote image confirmation and a further reboot, after which `image-list`
  still reported `0.1.9` active and confirmed with a new boot ID and zero
  startup errors.

The wake action clipped the ADXL367's intentionally narrow ±2 g wake range in
17 samples, while the BMI270 ±16 g acceleration and ±2000 dps gyro paths did
not clip. This is acceptable for a wake detector and also demonstrates why the
BMI270 remains the full-rate motion sensor.

## v0.1.8 intermediate test-boot evidence

The signed `0.1.8` intermediate candidate built with:

- Flash: 179,936 / 696,176 bytes (25.85%);
- RAM: 207,016 / 262,144 bytes (78.97%);
- signed BIN SHA-256:
  `692dcdb3d56db35576bd4dbc7ec8d7b051c931b990da3aec8206cbc2f8ceaa43`;
- MCUboot image digest:
  `4511d914e33a4ffaf8f5c863bbc93fc3f2e6e7ba0338997d37db7a737a73ee7c65c51f555235b0c54b7ebbe66c92b071d997fc9d99068165fdd20c31b7444d6b`.

During the first unconfirmed test boot:

- stable device ID and a new boot ID were reported;
- both sensors initialized with zero errors;
- forced `research -> idle -> research` changed the reported hardware rates as
  expected;
- research mode returned a complete 1024-sample, 20.46-second, 50 Hz frozen
  record with zero sequence gaps and zero sensor errors;
- default `auto` entered idle after 30 seconds of physical rest;
- encrypted SMP remained reachable while idle.

This intermediate image was deliberately left unconfirmed and successfully
rolled back to `0.1.7` after discovering that its BLE advertising still used
the original fast interval. That rollback is additional evidence that the
MCUboot safety path remains functional. Version `0.1.9` adds adaptive BLE
advertising. Version `0.1.11` became the confirmed polling correction baseline;
`0.1.13` is the current confirmed interrupt-wake baseline.
Measured coin-cell current remains required before making a battery-life claim.

## Coin-cell safety

The official board documentation warns not to apply external 3.3 V to the Tag
while a CR2032 is inserted. Keep external/SWD power during firmware validation;
then remove external power before inserting the battery. DAPLink can be stored
for recovery after the confirmed image survives a further reboot.
