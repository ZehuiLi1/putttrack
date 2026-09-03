# Research Ball R1 manual-floor exploration

This dataset is the first assembled-ball motion comparison collected without
the programmable roller. It confirms that the physical capture path sees clear
differences between stationary, free rolling, pickup/carry and restrained
handling/taps. It is deliberately **not** final classifier calibration data.

## Evidence boundary

- The floor material, actual travel distance and ball speed were not measured.
- There is no independent video or action timestamp.
- The two roll strengths are subjective; their peak angular velocities must
  not be interpreted as a calibrated speed ordering.
- The medium-roll history does not contain a clean final stationary tail.
- The operator reports many restrained light taps, but the exact count and
  timestamps were not recorded. The history may also contain setup motion, so
  it is a repeated-tap episode rather than isolated per-impact ground truth.
- The immutable raw capture embeds the originally instructed phrase
  `exactly three light finger taps`; the operator corrected that statement
  immediately after capture. The manifest metadata is the authoritative
  correction and the raw record is intentionally not rewritten.
- The frozen captures are nevertheless immutable, identity-locked and suitable
  for pipeline, signal-separation and experiment-design work.

## Initial result

The six legacy frozen captures contain 1,024 contiguous dual-IMU samples over
approximately 20.46 seconds at 50 Hz. A seventh physical smoke test uses the
new timed ARMED window and contains 400 contiguous samples over 7.98 seconds,
matching the requested three-second pre-GO plus five-second post-GO interval to
one sample period. Every capture has 100% valid samples, zero sequence gaps, no
BMI270 clipping and no sensor, power-management, advertising or notification
error delta.

| Episode | Accel norm SD (m/s²) | Gyro RMS (rad/s) | Gyro max (rad/s) | Active fraction |
|---|---:|---:|---:|---:|
| stationary before | 0.010 | 0.003 | 0.005 | 0.000 |
| manual light roll | 1.095 | 4.467 | 21.438 | 0.531 |
| manual medium roll | 1.019 | 5.129 | 19.961 | 0.638 |
| stationary after | 0.011 | 0.003 | 0.005 | 0.000 |
| pickup/carry | 1.510 | 1.440 | 12.257 | 0.359 |
| restrained repeated taps | 3.723 | 2.680 | 14.988 | 0.759 |
| ARMED stationary smoke | 0.010 | 0.003 | 0.005 | 0.000 |

The two stationary checks before and after motion both pass with essentially
zero gyro activity. This rules out persistent gyro drift and provides no
evidence of continuing internal movement after the shell stops. The free-roll
episodes show substantially more sustained gyro energy than pickup/carry in
this small sample. The taps produce much larger acceleration/jerk peaks, but
the contaminated action boundaries prevent per-impact claims.

The ADXL367 clipped within the medium-roll and restrained-tap raw histories,
while the BMI270 remained within range. This supports the intended division of
responsibility: ADXL367 is the low-power wake sentinel; BMI270 is the active
motion measurement source.

## Provenance

Every capture came from device `f383571202836e6f`, boot
`eab45817668ee95c`, and confirmed firmware `0.1.17`.

| Capture | SHA-256 |
|---|---|
| `raw/stationary-pre-r01.jsonl` | `58bbc7ec7deb99088a44bf41c862c9b00728f58ef4b1fc863aa8934619d84f86` |
| `raw/roll-manual-light-r01.jsonl` | `c85593691850eee622f6e5b8ee02c17e4617598d11350d75d6eefccfd618674e` |
| `raw/roll-manual-medium-r01.jsonl` | `f10bb725c8416493b36849992d5eb4679b74fa4b6e9e55704ebf50ffe4d77d6a` |
| `raw/stationary-post-r01.jsonl` | `773c561727add22cb755ad793f7423ec254dc37d7edcf760ec7707b5d1c60654` |
| `raw/pickup-carry-r01.jsonl` | `25e3967efd5b56aa08a6e01cac693ac1a8971f74640481c579e3fa01cbbf7d16` |
| `raw/restrained-repeated-taps-r01.jsonl` | `8a02d252a2761246dcf5f591fed9de158cfc63f5e1fc2e67d64b3bb6ebb0dce9` |
| `raw/armed-stationary-smoke-r01.jsonl` | `156dabc150c147ceafe5f4d87444bdfb44246b2ae190d7c03099e93fa863c5de` |

Regenerate the derived reports with:

```bash
python tools/analyze_motion_dataset.py \
  experiments/research_ball_r1_manual_floor/manifest.json \
  --output-dir experiments/research_ball_r1_manual_floor/analysis
```

The next motion dataset should use the programmable roller and an action-ready
capture procedure so setup motion is excluded from the labelled interval.
