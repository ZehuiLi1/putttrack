# Tag labelled motion episode runbook

## Purpose

This runbook collects the physical labels needed to move from a validated
stationary diagnostic to a measured generic-motion FSM. It deliberately keeps
labels physical and technology-neutral. A capture is not a confirmed stroke,
cup event or scoring event.

Use firmware `0.1.7` or later and the XIAO nRF52840 USB HCI adapter. Keep the Tag
powered, the XIAO connected and DAPLink disconnected unless recovery is needed.

## Capture command

The Tag continuously retains the latest 1024 source samples (20.48 seconds).
Perform the action, then immediately run the frozen capture command. The first
request atomically freezes the history; later BLE retries cannot change it. The
host reads 16 chunks and rejects mixed capture IDs, missing/reordered chunks,
incorrect bounds or source-sequence gaps.

```bash
python tools/capture_tag_smp.py \
  --mode frozen \
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
