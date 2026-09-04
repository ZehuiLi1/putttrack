# Pickup precision phase 1C-drop: pickup plus casual release

## Scope

This immutable evidence set contains ten successful `pickup_drop` episodes.
Every planned action started with the assembled Ball at rest, followed by a
natural pickup, 2–3 seconds of carrying and a casual release from normal low
hand height without throwing. The first episode was captured in the initial
session and the remaining nine in a continuation session; original filenames
are deliberately preserved.

The operator confirmed every action after a visible GO cue. Release height,
surface and independent video truth were not measured. The set is therefore
useful pickup-positive variation and release/landing exploration, but is not a
product-accuracy, free-fall-height or impact-severity ground truth set.

## Capture and quality result

- device ID: `f383571202836e6f`
- firmware: `0.1.17`
- source rate: 50 Hz
- successful captures: 10
- pre-GO/capture/metadata failures: 0
- sequence gaps: 0 in all episodes
- quality: 0 `PASS`, 10 `WARN`, 0 `FAIL`
- ADXL367 clipping: 10/10 episodes, 31 total samples
- BMI270 accelerometer clipping: 0/10 episodes
- BMI270 gyroscope clipping: 0/10 episodes

Every warning is caused only by expected ADXL367 ±2 g clipping during dynamic
motion. BMI270 retained full measurement range, so all ten captures remain
usable for the intended analysis.

## Exploratory findings

The pickup onset, rather than the later landing, is the gameplay-relevant
signal. Using a simple diagnostic onset rule, the first one-second segment of
these episodes has:

| Feature | `pickup_drop`, n=10 | Earlier `pickup_carry`, n=10 |
|---|---:|---:|
| Mean gyro norm (rad/s) | 2.010–4.097 | 1.874–3.528 |
| Gyro-axis consistency | 0.317–0.752 | 0.242–0.554 |
| Accel-norm stdev (m/s²) | 2.113–5.320 | 1.515–4.946 |

The overlap supports one shared pickup detector: a terminal drop must not be
required to recognize a pickup. Episode r07 reaches axis consistency `0.7516`,
just beyond the old post-hoc `<0.75` research boundary. This is useful evidence
that a hard one-feature cutoff is brittle; the frozen V0 threshold must not be
retuned from this inspected batch. The exact vertical-impulse V0 evaluator is
still required before a formal frozen-detector pass rate can be reported.

All ten episodes also contain an exploratory release pair: after the pickup
onset, BMI270 acceleration norm falls below `2 m/s²`, followed within 20–400 ms
by a `26.0–93.5 m/s²` acceleration peak. This is physically consistent with a
brief low-height release followed by landing, but operator labels—not IMU alone—
establish the action identity. Do not turn this diagnostic into scoring or
pickup authority.

`analysis/drop_signature_summary.csv` records the per-episode values. Its
diagnostic onset is the first point after GO+0.5 s with at least three active
samples in five, where active means `|accel_norm - 9.80665| >= 0.5 m/s²` or
`gyro_norm >= 0.25 rad/s`. The release candidate is selected after onset+1.5 s
from samples below `2 m/s²` by the largest acceleration peak in the following
0.4 s. These post-hoc constants describe this batch; they are not a classifier.

## Files

- `manifest.json` provides episode identity and known provenance.
- `raw/` contains the ten original, unmodified JSONL captures.
- `analysis/dataset_summary.csv` and `.json` contain deterministic generic
  whole-window features.
- `analysis/drop_signature_summary.csv` contains the documented exploratory
  onset/release measurements.
- `analysis/quality_report.json` records structural quality outcomes.
- `analysis/plots/` contains dependency-free per-episode traces.

Regenerate the standard derived analysis with:

```bash
python tools/analyze_motion_dataset.py \
  experiments/research_ball_r1_pickup_precision_1c_drop/manifest.json \
  --output-dir experiments/research_ball_r1_pickup_precision_1c_drop/analysis
```
