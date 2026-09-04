# Tag labelled motion episode runbook

## Purpose

This runbook collects the physical labels needed to move from a validated
stationary diagnostic to a measured generic-motion FSM. It deliberately keeps
labels physical and technology-neutral. A capture is not a confirmed stroke,
cup event or scoring event.

Use firmware `0.1.7` or later and the XIAO nRF52840 USB HCI adapter. Keep the Tag
powered, the XIAO connected and DAPLink disconnected unless recovery is needed.

## Simplest field workflow

The primary operator interface is a loopback-only web page. Connect the Ball
and XIAO nRF52840, then run:

```bash
python3 tools/run_field_capture_ui.py
```

The browser opens `http://127.0.0.1:8765/`. Select the physical action and
repetition count, press **Prepare batch**, then use the single large button to
start each episode. The page shows countdown, GO, save/analysis progress and
the last sample result. The device panel uses actual Tag status responses to
show battery voltage, explicitly estimated state of charge, firmware, sensor
health, power/runtime state and IMU sampling state. Its batch charts plot
battery readbacks plus per-episode gyroscope peak/RMS values; continuity,
sequence gaps and clipping remain visible quality checks rather than being
hidden. No values are synthesized before a Tag response is received. It never
listens on the LAN, rejects a status response from the wrong device, rejects
concurrent captures and existing filenames, and automatically restores `auto`
mode after the final run, manual finish, failure, server shutdown or ten
minutes waiting between runs.

The command-line wrapper below remains the fallback when a browser is
inconvenient.

The XIAO remains an unmodified USB HCI bridge; do not add a start/stop button to
its controller firmware. Use the field-session wrapper instead. It switches the
Ball to `research` once, asks for one Enter press before each episode, performs
the three-second countdown and audible GO cue, freezes and analyzes the fixed
window automatically, and restores `auto` low power on normal exit, `q`, Ctrl-C
or a capture failure. A second/end press is intentionally not required.

For example, collect ten natural pickup/carry/place episodes with:

```bash
python3 tools/capture_field_session.py pickup_carry \
  --count 10 \
  --session-id s1 \
  --expected-device-id f383571202836e6f
```

Available profiles are `pickup_carry`, `handling`, `putt_gentle`,
`putt_normal`, `putt_firm` and `hand_roll`. Output names and repetition numbers
are generated automatically under `runs/`, and existing files are never
overwritten. Before each Enter press, arrange the camera and Ball and keep the
Ball still. After GO perform exactly one instructed action, then leave the Ball
untouched until the completion cue. Use `--start-index` to continue a partially
completed batch without reusing filenames.

## Preferred armed capture

Arrange the Ball, restraints, camera and safe travel path **before** starting
the command. The timed frozen workflow then:

1. validates the exact Tag identity and sensor health;
2. records the requested stationary countdown;
3. obtains a device-side motion sequence/time marker and prints `GO`;
4. waits a fixed action-plus-rest interval;
5. freezes the retained history automatically; and
6. emits only the requested pre-GO and post-GO interval.

This keeps setup motion and operator/chat delay outside the labelled window.
The combined countdown and episode duration is limited to 17 seconds so the
complete interval remains inside the Tag's 20.48-second retained history.

```bash
python tools/set_tag_power_mode.py research

python tools/capture_tag_smp.py \
  --mode frozen \
  --armed-countdown 3 \
  --episode-seconds 10 \
  --expected-device-id f383571202836e6f \
  --label rolling \
  --notes "roller R1; slow CW; act only after GO; finish with five seconds rest" \
  --output runs/rolling-r1-cw-slow-r01.jsonl

python tools/analyze_tag_capture.py runs/rolling-r1-cw-slow-r01.jsonl
python tools/set_tag_power_mode.py auto
```

`--episode-seconds` begins at `GO`, so it must include both the action and its
final stationary tail. Each armed file includes `tag_episode_marker` and
`tag_episode_window` records with device sequence/monotonic-time boundaries;
host timing is retained only as supporting provenance.

## Legacy post-action capture

The Tag continuously retains the latest 1024 source samples (20.48 seconds).
Perform the action, then immediately run the frozen capture command. The first
request atomically freezes the history; later BLE retries cannot change it. The
host reads 16 chunks and rejects mixed capture IDs, missing/reordered chunks,
incorrect bounds or source-sequence gaps.

```bash
python tools/capture_tag_smp.py \
  --mode frozen \
  --expected-device-id f383571202836e6f \
  --label pickup_carry \
  --notes "bare Tag; desk to hand and held for two seconds" \
  --output runs/pickup-carry-001.jsonl

python tools/analyze_tag_capture.py runs/pickup-carry-001.jsonl
```

`--mode window` remains useful for immediate stream diagnostics and
`--until-enter` remains available for interactive experiments, but repeated BLE
management connections can create gaps during long captures. Do not use that
path as the primary labelled-episode record when frozen history is available.

The output path is exclusive: the tool will not overwrite an existing episode.
`runs/` is intentionally ignored by Git because raw experiments can be large;
promote selected immutable evidence separately after review.

The commissioned Tag's full ID is `f383571202836e6f`. Always lock it for its
captures. It now runs confirmed `0.1.17`; keep any uncommissioned Tag powered
off or additionally pin `--ble-address` and `--address-type`; see
[`TAG_MULTI_DEVICE_IDENTITY.md`](TAG_MULTI_DEVICE_IDENTITY.md).

The command fails closed when a sensor is not ready, a pre-existing/new sensor
error is reported, a record is invalid, or the merged source sequence contains
a gap. Clipping is reported as an episode-local delta rather than treated as a
transport failure because a controlled impact may legitimately reach a sensor
rail; any clipped episode must be marked unsuitable for amplitude calibration.

Capture `PASS` means transport integrity, not that the operator action was
observed. The analyzer independently checks validated labels: `stationary` must
look stationary and `pickup_carry` must contain unmistakable generic activity.
Desk-bound `handling` may remain `UNCLASSIFIED` or become generic active motion,
but neither state identifies pickup or a stroke. The analyzer exits non-zero
and refuses canonical observation export when a validated label does not match
its allowed states.

The first two physical repetitions show why this boundary matters: stronger
desk handling overlaps natural pickup/carry in acceleration variability and
gyro RMS. Do not derive `PICKED_UP`, `CARRIED` or impact semantics from a generic
active result. Retain the physical label, and use independent tee/game context
plus a mechanically representative core before training or tuning action
classifiers.

## First episode set

Record at least these as separate files. Do not combine several labels into one
file during the first pass.

| Label | Physical action | Important control |
|---|---|---|
| `stationary` | untouched on a rigid desk | multiple orientations |
| `pickup_carry` | desk → hand → carry → place down | no rolling |
| `handling` | cable/board adjustment and ordinary touch | common false-stroke source |
| `impact_tap` | short controlled tap while restrained | do not damage the bare PCB |
| `rolling` | mechanically secured test core rolls on level surface | not meaningful with loose bare PCB |
| `settling` | rolling core naturally slows and stops | keep in same episode family as roll |
| `drop` | only inside a protective test core onto a safe surface | never drop the bare Tag |

For putter impact, rolling, settling and drop, first mount the board and power
source in a repeatable protective core. Loose PCB/battery motion produces labels
that will not transfer to a ball and risks hardware damage.

## Metadata discipline

For every episode, retain:

- label and unique filename;
- bare Tag versus test-core revision;
- surface and approximate orientation;
- action start cue or an independent video/time marker when available;
- firmware version, device ID and boot ID already written by the tool;
- any suspected clipping, cable movement, interruption or mislabel.

Never split adjacent windows from the same physical episode across train and
test. Split by complete session, mechanical build and day/operator where
possible.

## Acceptance before classification

An episode is usable only when:

- both IMUs are valid for the intended interval;
- sensor error bits are zero;
- sequence continuity and source timestamps are explicit;
- the observed sample rate is close to the intended rate;
- the action label is independently credible;
- clipping and mechanical setup are known rather than silently ignored.

Thresholds must come from the collected distributions. The current provisional
stationary gate is only a transport/sensor smoke check.
