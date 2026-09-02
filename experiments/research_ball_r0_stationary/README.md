# Research Ball R0 stationary baseline

This is the first checked-in physical dataset from the mechanically assembled
two-half Research Ball. It is an integrity and static-noise baseline, not a
putt, roll or impact classifier calibration set.

## Physical result

- Both captures contain 1,024 contiguous dual-IMU samples over 20.46 seconds at
  50 Hz.
- Both captures have 100% valid samples, no sequence gaps, no capture-time
  clipping deltas and no sensor, power-management, advertising or notification
  error deltas.
- Both pass the provisional `STATIONARY_CANDIDATE` check with zero active
  samples.
- The BMI270 mean gravity vectors are `[4.737806, 2.844800, -8.248991]` and
  `[-4.536869, 5.124098, 6.798837]` m/s², an angular separation of 131.128°.
- The ADXL367 mean gravity vectors independently show 129.663° separation.
  This confirms that orientation 2 is not a duplicate of orientation 1.

The approximately 2.9% difference between the two BMI270 gravity-vector norms
is useful calibration evidence, but two arbitrary orientations are not enough
to fit bias/scale. A controlled six-face calibration can be added later if
classification accuracy proves sensitive to it.

## Provenance

Both captures came from opaque device ID `f383571202836e6f`, boot ID
`8881f66bd3ff32f0`, and confirmed firmware `0.1.13`. The raw files are immutable:

| Capture | SHA-256 |
|---|---|
| `raw/stationary-o1-r01.jsonl` | `9f4e45f69fe07991a9c0f6f55339e17bf1d5d3e2491b6c90364e9ed2617a2898` |
| `raw/stationary-o2-r01.jsonl` | `db87ffd8feb16a676779c6c567dc7ba0dc269345d75b3ea1d6c33a4445750258` |

Regenerate the derived reports with:

```bash
python tools/analyze_motion_dataset.py \
  experiments/research_ball_r0_stationary/manifest.json \
  --output-dir experiments/research_ball_r0_stationary/analysis
```

The next high-value dataset is controlled `impact_tap`, `rolling`, `settling`
and final `stationary` episodes using the programmable roller and independent
video/time references.
