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

Until the motor controller protocol is integrated, synchronization is bounded
rather than falsely exact:

1. Start a phone/camera view that includes the ball and roller control/status.
2. Begin each run with at least 3 seconds stationary.
3. Use one visible/audible start cue, then execute exactly one motor profile.
4. End with at least 5 seconds stationary and freeze the Tag history
   immediately.
5. Store the video/cue reference and motor log beside the Tag run manifest.

Once controller timestamps are accessible, log them monotonically and estimate
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

Before the first run:

```bash
python tools/set_tag_power_mode.py research
```

After each profile and its final stationary period:

```bash
python tools/capture_tag_smp.py \
  --mode frozen \
  --expected-device-id f383571202836e6f \
  --label rolling \
  --notes "roller R1; CW; slow; carrier r1; repetition 01" \
  --output runs/roller-r1-cw-slow-r01.jsonl

python tools/analyze_tag_capture.py runs/roller-r1-cw-slow-r01.jsonl
```

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

## Information needed for controller integration

The software adapter can be implemented when these are known:

- motor controller board/model and its source repository or protocol;
- USB serial, BLE, Wi-Fi or other host interface;
- command syntax and speed units;
- roller diameter/contact layout;
- encoder availability and timestamp resolution;
- emergency-stop behavior.

Until then, the protocol above lets mechanical printing and firmware/data work
advance without inventing a controller API.
