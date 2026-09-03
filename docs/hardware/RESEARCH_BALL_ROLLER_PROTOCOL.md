# Controlled research-ball roller protocol

## Purpose

The programmable roller is a controlled excitation source for the first
instrumented-ball dataset. It can establish repeatability, clipping, angular
rate response, transport continuity and settling behavior before free putting.
It does not prove that a movement was a valid stroke and it does not replace
free-roll or putter-impact trials.

Use the removable carrier defined in
[`NRF54L15_TAG_MECHANICAL_ENVELOPE.md`](NRF54L15_TAG_MECHANICAL_ENVELOPE.md).
Never rotate a loose PCB/cell or a ball connected to DAPLink.

## Required run metadata

Record one immutable run for each commanded profile:

```text
session_id, run_id, date_time, operator
firmware_commit, firmware_version, device_id, boot_id
ball_id, shell_revision, carrier_revision, total_mass_g
roller_revision, motor_controller, roller_diameter_mm
commanded_direction, commanded_speed, speed_unit
ramp_up_ms, hold_ms, ramp_down_ms, repetition
surface/contact_material, ball_start_orientation
encoder_present, measured_speed, slip_observed
video_or_sync_reference, notes, validity
```

If the roller has an encoder, preserve its timestamped raw speed rather than
only the final average. If it has no encoder, call the value `commanded_speed`,
not measured RPM. Mark every visible bounce, shell slip, roller slip or manual
touch; do not silently keep it as a clean run.

## Data contract and timing

Confirmed Tag firmware `0.1.17` in `research` policy records a 50 Hz output stream from
100 Hz ADXL367/BMI270 configuration and retains the latest 1024 samples
(20.48 seconds). Each captured sample already includes monotonic device time,
sequence, validity, sensor errors and both IMU vectors. The run manifest must
also retain ODR/range and episode-local clipping deltas.

The first controller adapter is implemented and physically passed on the
user's ZDT/张大头 Emm_V5 closed-loop driver over TTL UART. On 2026-09-04 it
returned firmware/hardware codes `1/120`, reported an 18.74--18.89 V bus, and
completed both +30 and -30 RPM three-second commands with acknowledged timeout
stops, final 0 RPM, disabled output and no stall flags. It records host-visible
command/ack events; synchronization remains bounded rather than falsely exact:

1. Start a phone/camera view that includes the ball and roller control/status.
2. Begin each run with at least 3 seconds stationary.
3. Use one visible/audible start cue, then execute exactly one motor profile.
4. End with at least 5 seconds stationary; the armed capture command freezes
   the Tag history automatically.
5. Store the video/cue reference and motor log beside the Tag run manifest.

Preserve its JSON command/status log beside each capture. Controller events currently use host
receive order rather than a shared Tag clock. Estimate
the controller-to-Tag offset with a repeatable sharp speed transition. Do not
assume host wall-clock equality. The 20.48-second Tag history means the complete
profile, including pre/post rest, should initially stay below about 17 seconds.

## First test matrix

Run tests in this order. Stop if the carrier loosens, the shell separates or
sensor errors appear.

| Stage | Profile | Variations | Initial repetitions | Question answered |
|---|---|---|---:|---|
| R0 | Stationary in idle roller | 3 ball orientations | 3 each | Does restraint itself add vibration/noise? |
| R1 | Slow ramp → steady → stop | CW and CCW | 5 each | Direction symmetry, sequence integrity, gross slip |
| R2 | Three steady speeds | CW and CCW, 3 orientations | 5 each | Gyro linearity/repeatability and clipping onset |
| R3 | Three ramp rates | same final speed | 5 each | Rolling-start vs impact-like transient separation |
| R4 | Coast/settle | motor-driven stop and free coast | 10 each | Candidate `ACTIVE_ROLLING → SETTLING → STATIONARY` timing |
| R5 | Repeat on second day | selected R1–R4 cases | 5 each | Session/mechanical repeatability |

Use low speeds first. For an ideal no-slip single contact, angular-speed ratios
can be predicted from the contact radii, but a multi-roller fixture depends on
its geometry and preload. Treat the theoretical ratio as a diagnostic only
until roller diameter, contact layout and encoder truth are recorded.

## Capture workflow

### Motor bring-up before inserting the Ball

The ESP32-C3 can run PN532 SPI and the motor UART together. The safe mapping and
commands are maintained in
[`../../firmware/esp32c3_pn532_reader/README.md`](../../firmware/esp32c3_pn532_reader/README.md):

```text
Emm R/A/H -> ESP32-C3 GPIO4 (ESP RX; physically confirmed)
Emm T/B/L -> ESP32-C3 GPIO5 (ESP TX; physically confirmed)
Emm Gnd   -> ESP32-C3 GND
```

GPIO11 is prohibited because it is the ESP32-C3 `VDD_SPI` pin by default. With
the ball removed and the motor power switch in reach, the first gate is
read-only:

```bash
python3 tools/control_roller_motor.py --port /dev/cu.usbmodem1101 probe
python3 tools/control_roller_motor.py --port /dev/cu.usbmodem1101 status
```

The empty-fixture gate physically passed in both directions on 2026-09-04. To
repeat it after any wiring, firmware or mechanical change, use 30 RPM for three
seconds:

```bash
python3 tools/control_roller_motor.py --port /dev/cu.usbmodem1101 run \
  --rpm 30 --seconds 3 --confirm-clear
```

Verify direction, automatic stop, explicit `stop`, and `disable` before placing
the assembled Ball in the fixture. The firmware issues `STOP + DISABLE` on MCU
boot and enforces a one-shot arm token and run deadline. Those controls cannot
stop a separately powered driver if the ESP32 loses power, so a reachable motor
power switch is mandatory until a hardware fail-safe `EN` interlock exists.

### Tag capture

Before the first run:

```bash
python tools/set_tag_power_mode.py research
```

After the Ball and roller are fully arranged, start one bounded capture. Act
only after the terminal prints `GO`; the 10-second post-GO interval must contain
the complete motor profile and final stationary period:

```bash
python tools/capture_tag_smp.py \
  --mode frozen \
  --armed-countdown 3 \
  --episode-seconds 10 \
  --expected-device-id f383571202836e6f \
  --label rolling \
  --notes "roller R1; CW; slow; carrier r1; repetition 01" \
  --output runs/roller-r1-cw-slow-r01.jsonl

python tools/analyze_tag_capture.py runs/roller-r1-cw-slow-r01.jsonl
```

The script writes a device-side GO marker and crops out setup motion as well as
BLE freeze/readback delay. Countdown plus post-GO duration may not exceed 17
seconds. If a motor profile cannot fit, shorten it or implement synchronized
controller markers rather than weakening the retained-history bound.

Do not reuse filenames or overwrite failed runs. A failed run remains useful
evidence when its validity reason is explicit.

## Acceptance for moving to free-roll tests

The roller phase passes when:

- the core is rigid and no internal cell/PCB movement is visible or audible;
- at least 95% of planned R1–R4 runs have zero sequence gaps and sensor errors;
- same-profile traces are repeatable across orientation and direction, with
  deviations explained by measured slip/contact changes;
- clipping onset is reported rather than hidden;
- rolling, powered stop/coast and post-stop intervals can be marked from
  independent controller/video evidence;
- no threshold is promoted into product firmware from one session alone.

Then collect level-surface free rolls, gentle putter strikes, wall/ball
collisions and cup sequences. Split evaluation by complete session and
mechanical revision, never by adjacent windows from the same run.

## Remaining controller facts

The protocol, host interface, pin mapping and empty-fixture bidirectional
30 RPM/3 s stop gate are physically confirmed. The
remaining physical metadata cannot be inferred in software:

- roller diameter/contact layout;
- whether reported closed-loop motor RPM matches roller RPM under load;
- encoder timestamp resolution, if raw encoder samples are exposed;
- direction sign relative to the fixture;
- measured slip and the final hardware emergency-stop/`EN` behavior.

Do not label motor RPM as ball angular velocity until roller diameter, contact
geometry and slip have been measured.
