# Pickup precision phase 1E: putt-to-rail collision controls

## Scope

This immutable evidence set contains ten `putt_rail_collision` episodes. The
operator reported one putt, one collision with a fixed rail/wall and natural
settling without pickup after each visible GO cue. Planned strengths were three
light, four normal and three firm-but-natural putts.

Rail geometry, surface material and independent video truth were not recorded.
These episodes are hard false-pickup controls and are not stroke, cup or scoring
authority.

## Capture and quality result

- device ID: `f383571202836e6f`
- firmware: `0.1.17`
- source rate: 50 Hz
- captured episodes: 10
- continuity/metadata failures: 0
- quality: 0 `PASS`, 10 `WARN`, 0 `FAIL`
- ADXL367 clipping: 10/10 episodes, 97 total samples
- BMI270 accelerometer clipping: 0/10 episodes
- BMI270 gyroscope clipping: 10/10 episodes, 110 total samples

Every episode remains structurally usable, but neither ADXL367 nor BMI270 gyro
peak amplitude can be calibrated from this batch. BMI270 acceleration retained
full range in every episode. Gyro saturation itself is useful as a conservative
quality/state signal, not as an estimate of the true peak.

## Post-GO comparison with pickup holdout

| Feature | Pickup holdout, n=10 | Rail collision, n=10 | Interpretation |
|---|---:|---:|---|
| Accel-norm stdev (m/s²) | 1.474-4.864 | 2.532-6.438 | overlaps; not a pickup rule |
| Gyro RMS (rad/s) | 1.708-4.531 | 4.351-17.018 | boundary overlap; rail values partly clipped |
| Gyro peak (rad/s) | 6.934-17.385 | 37.326-60.461 | separated here, but every rail trace clipped gyro |
| Jerk peak (m/s³) | 318.272-1294.090 | 2279.330-5203.510 | separated in this setup |
| Active-sample fraction | 0.318-0.772 | 0.105-0.362 | mostly separated; small overlap |

The earlier apparent acceleration-variability gap between no-lift handling and
pickup does not survive this legitimate in-course collision class. A rule such
as "large acceleration variability means pickup" would produce false pickup
events.

The collision traces are shorter and more impulsive than pickup/carry in this
batch, while their angular motion and jerk are substantially stronger. This
supports a temporal multi-feature decision: pickup must show a sustained
post-transition handling/carry pattern, while a brief impact followed by
rolling/settling remains an in-course negative. Exact V0 vertical-impulse and
gyro-shape evaluation still requires the executable raw-feature evaluator.

## Files

- `manifest.json` provides episode identity and known provenance.
- `raw/` contains the original unmodified JSONL captures.
- `analysis/dataset_summary.csv` and `.json` contain deterministic features.
- `analysis/quality_report.json` records structural quality outcomes.
- `analysis/plots/` contains dependency-free per-episode traces.

Regenerate the derived analysis with:

```bash
python tools/analyze_motion_dataset.py \
  experiments/research_ball_r1_pickup_precision_1e_rail/manifest.json \
  --output-dir experiments/research_ball_r1_pickup_precision_1e_rail/analysis
```
